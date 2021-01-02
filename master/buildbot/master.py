# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members


import os
import signal
import socket

from twisted.application import internet
from twisted.internet import defer
from twisted.internet import task
from twisted.internet import threads
from twisted.python import failure
from twisted.python import log

import buildbot
import buildbot.pbmanager
from buildbot import config
from buildbot import monkeypatches
from buildbot.buildbot_net_usage_data import sendBuildbotNetUsageData
from buildbot.changes.manager import ChangeManager
from buildbot.data import connector as dataconnector
from buildbot.db import connector as dbconnector
from buildbot.db import exceptions
from buildbot.machine.manager import MachineManager
from buildbot.mq import connector as mqconnector
from buildbot.process import cache
from buildbot.process import debug
from buildbot.process import metrics
from buildbot.process.botmaster import BotMaster
from buildbot.process.users.manager import UserManagerManager
from buildbot.schedulers.manager import SchedulerManager
from buildbot.secrets.manager import SecretManager
from buildbot.status.master_compat import Status
from buildbot.util import check_functional_environment
from buildbot.util import service
from buildbot.util.eventual import eventually
from buildbot.wamp import connector as wampconnector
from buildbot.worker import manager as workermanager
from buildbot.www import service as wwwservice


class LogRotation:

    def __init__(self):
        self.rotateLength = 1 * 1000 * 1000
        self.maxRotatedFiles = 10


class BuildMaster(service.ReconfigurableServiceMixin, service.MasterService):

    # multiplier on RECLAIM_BUILD_INTERVAL at which a build is considered
    # unclaimed; this should be at least 2 to avoid false positives
    UNCLAIMED_BUILD_FACTOR = 6

    def __init__(self, basedir, configFileName=None, umask=None, reactor=None, config_loader=None):
        super().__init__()

        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor

        self.setName("buildmaster")

        self.umask = umask

        self.basedir = basedir
        if basedir is not None:  # None is used in tests
            assert os.path.isdir(self.basedir)

        if config_loader is not None and configFileName is not None:
            raise config.ConfigErrors([
                "Can't specify both `config_loader` and `configFilename`.",
            ])
        if config_loader is None:
            if configFileName is None:
                configFileName = 'master.cfg'
            config_loader = config.FileLoader(self.basedir, configFileName)
        self.config_loader = config_loader
        self.configFileName = configFileName

        # flag so we don't try to do fancy things before the master is ready
        self._master_initialized = False
        self.initLock = defer.DeferredLock()

        # set up child services
        self._services_d = self.create_child_services()

        # db configured values
        self.configured_db_url = None

        # configuration / reconfiguration handling
        self.config = config.MasterConfig()
        self.config_version = 0  # increased by one on each reconfig
        self.reconfig_active = False
        self.reconfig_requested = False
        self.reconfig_notifier = None

        # this stores parameters used in the tac file, and is accessed by the
        # WebStatus to duplicate those values.
        self.log_rotation = LogRotation()

        # local cache for this master's object ID
        self._object_id = None

        # Check environment is sensible
        check_functional_environment(self.config)

        # figure out local hostname
        try:
            self.hostname = os.uname()[1]  # only on unix
        except AttributeError:
            self.hostname = socket.getfqdn()

        # public attributes
        self.name = ("{}:{}".format(self.hostname, os.path.abspath(self.basedir or '.')))
        if isinstance(self.name, bytes):
            self.name = self.name.decode('ascii', 'replace')
        self.masterid = None

    @defer.inlineCallbacks
    def create_child_services(self):
        # note that these are order-dependent.  If you get the order wrong,
        # you'll know it, as the master will fail to start.

        self.metrics = metrics.MetricLogObserver()
        yield self.metrics.setServiceParent(self)

        self.caches = cache.CacheManager()
        yield self.caches.setServiceParent(self)

        self.pbmanager = buildbot.pbmanager.PBManager()
        yield self.pbmanager.setServiceParent(self)

        self.workers = workermanager.WorkerManager(self)
        yield self.workers.setServiceParent(self)

        self.change_svc = ChangeManager()
        yield self.change_svc.setServiceParent(self)

        self.botmaster = BotMaster()
        yield self.botmaster.setServiceParent(self)

        self.machine_manager = MachineManager()
        yield self.machine_manager.setServiceParent(self)

        self.scheduler_manager = SchedulerManager()
        yield self.scheduler_manager.setServiceParent(self)

        self.user_manager = UserManagerManager(self)
        yield self.user_manager.setServiceParent(self)

        self.db = dbconnector.DBConnector(self.basedir)
        yield self.db.setServiceParent(self)

        self.wamp = wampconnector.WampConnector()
        yield self.wamp.setServiceParent(self)

        self.mq = mqconnector.MQConnector()
        yield self.mq.setServiceParent(self)

        self.data = dataconnector.DataConnector()
        yield self.data.setServiceParent(self)

        self.www = wwwservice.WWWService()
        yield self.www.setServiceParent(self)

        self.debug = debug.DebugServices()
        yield self.debug.setServiceParent(self)

        self.status = Status()
        yield self.status.setServiceParent(self)

        self.secrets_manager = SecretManager()
        yield self.secrets_manager.setServiceParent(self)
        self.secrets_manager.reconfig_priority = 2000

        self.service_manager = service.BuildbotServiceManager()
        yield self.service_manager.setServiceParent(self)
        self.service_manager.reconfig_priority = 1000

        self.masterHouskeepingTimer = 0

        @defer.inlineCallbacks
        def heartbeat():
            if self.masterid is not None:
                yield self.data.updates.masterActive(name=self.name,
                                                     masterid=self.masterid)
            yield self.data.updates.expireMasters()
        self.masterHeartbeatService = internet.TimerService(60, heartbeat)
        self.masterHeartbeatService.clock = self.reactor
        # we do setServiceParent only when the master is configured
        # master should advertise itself only at that time

    # setup and reconfig handling

    _already_started = False

    @defer.inlineCallbacks
    def startService(self):
        assert not self._already_started, "can only start the master once"
        self._already_started = True

        # ensure child services have been set up. Normally we would do this in serServiceParent,
        # but buildmaster is used in contexts we can't control.
        if self._services_d is not None:
            yield self._services_d
            self._services_d = None

        log.msg("Starting BuildMaster -- buildbot.version: {}".format(buildbot.version))

        # Set umask
        if self.umask is not None:
            os.umask(self.umask)

        # first, apply all monkeypatches
        monkeypatches.patch_all()

        # we want to wait until the reactor is running, so we can call
        # reactor.stop() for fatal errors
        d = defer.Deferred()
        self.reactor.callWhenRunning(d.callback, None)
        yield d

        startup_succeed = False
        try:
            yield self.initLock.acquire()
            # load the configuration file, treating errors as fatal
            try:
                # run the master.cfg in thread, so that it can use blocking
                # code
                self.config = yield threads.deferToThreadPool(
                    self.reactor, self.reactor.getThreadPool(),
                    self.config_loader.loadConfig)

            except config.ConfigErrors as e:
                log.msg("Configuration Errors:")
                for msg in e.errors:
                    log.msg("  " + msg)
                log.msg("Halting master.")
                self.reactor.stop()
                return
            except Exception:
                log.err(failure.Failure(), 'while starting BuildMaster')
                self.reactor.stop()
                return

            # set up services that need access to the config before everything
            # else gets told to reconfig
            try:
                yield self.db.setup()
            except exceptions.DatabaseNotReadyError:
                # (message was already logged)
                self.reactor.stop()
                return

            yield self.mq.setup()

            # the buildbot scripts send the SIGHUP signal to reconfig master
            if hasattr(signal, "SIGHUP"):
                def sighup(*args):
                    eventually(self.reconfig)
                signal.signal(signal.SIGHUP, sighup)

            # the buildbot scripts send the SIGUSR1 signal to stop master
            if hasattr(signal, "SIGUSR1"):
                def sigusr1(*args):
                    eventually(self.botmaster.cleanShutdown)
                signal.signal(signal.SIGUSR1, sigusr1)

            # get the masterid so other services can use it in
            # startup/reconfig.  This goes directly to the DB since the data
            # API isn't initialized yet, and anyway, this method is aware of
            # the DB API since it just called its setup function
            self.masterid = yield self.db.masters.findMasterId(
                name=self.name)

            # mark this master as stopped, in case it crashed before
            yield self.data.updates.masterStopped(name=self.name,
                                                  masterid=self.masterid)

            # call the parent method
            yield super().startService()

            # We make sure the housekeeping is done before configuring in order to cleanup
            # any remaining claimed schedulers or change sources from zombie
            # masters
            yield self.data.updates.expireMasters(forceHouseKeeping=True)

            # give all services a chance to load the new configuration, rather
            # than the base configuration
            yield self.reconfigServiceWithBuildbotConfig(self.config)

            # Mark the master as active now that mq is running
            yield self.data.updates.masterActive(name=self.name,
                                                 masterid=self.masterid)

            # Start the heartbeat timer
            yield self.masterHeartbeatService.setServiceParent(self)

            # send the statistics to buildbot.net, without waiting
            self.sendBuildbotNetUsageData()
            startup_succeed = True
        except Exception:
            f = failure.Failure()
            log.err(f, 'while starting BuildMaster')
            self.reactor.stop()

        finally:
            if startup_succeed:
                log.msg("BuildMaster is running")
            else:
                log.msg("BuildMaster startup failed")

            yield self.initLock.release()
            self._master_initialized = True

    def sendBuildbotNetUsageData(self):
        if "TRIAL_PYTHONPATH" in os.environ and self.config.buildbotNetUsageData is not None:
            raise RuntimeError(
                "Should not enable buildbotNetUsageData in trial tests!")
        sendBuildbotNetUsageData(self)

    @defer.inlineCallbacks
    def stopService(self):
        try:
            yield self.initLock.acquire()
            if self.masterid is not None:
                yield self.data.updates.masterStopped(
                    name=self.name, masterid=self.masterid)
            if self.running:
                yield self.botmaster.cleanShutdown(
                    quickMode=True, stopReactor=False)
                yield super().stopService()

            log.msg("BuildMaster is stopped")
            self._master_initialized = False
        finally:
            yield self.initLock.release()

    @defer.inlineCallbacks
    def reconfig(self):
        # this method wraps doConfig, ensuring it is only ever called once at
        # a time, and alerting the user if the reconfig takes too long
        if self.reconfig_active:
            log.msg("reconfig already active; will reconfig again after")
            self.reconfig_requested = True
            return

        self.reconfig_active = self.reactor.seconds()
        metrics.MetricCountEvent.log("loaded_config", 1)

        # notify every 10 seconds that the reconfig is still going on, although
        # reconfigs should not take that long!
        self.reconfig_notifier = task.LoopingCall(
            lambda: log.msg("reconfig is ongoing for {} s".format(self.reactor.seconds() -
                                                                  self.reconfig_active)))
        self.reconfig_notifier.start(10, now=False)

        timer = metrics.Timer("BuildMaster.reconfig")
        timer.start()

        try:
            yield self.doReconfig()
        except Exception as e:
            log.err(e, 'while reconfiguring')
        finally:
            timer.stop()
            self.reconfig_notifier.stop()
            self.reconfig_notifier = None
            self.reconfig_active = False
            if self.reconfig_requested:
                self.reconfig_requested = False
                self.reconfig()

    @defer.inlineCallbacks
    def doReconfig(self):
        log.msg("beginning configuration update")
        changes_made = False
        failed = False
        try:
            yield self.initLock.acquire()
            # Run the master.cfg in thread, so that it can use blocking code
            new_config = yield threads.deferToThreadPool(
                self.reactor, self.reactor.getThreadPool(),
                self.config_loader.loadConfig)
            changes_made = True
            self.config_version += 1
            self.config = new_config

            yield self.reconfigServiceWithBuildbotConfig(new_config)

        except config.ConfigErrors as e:
            for msg in e.errors:
                log.msg(msg)
            failed = True

        except Exception:
            log.err(failure.Failure(), 'during reconfig:')
            failed = True

        finally:
            yield self.initLock.release()

        if failed:
            if changes_made:
                log.msg("WARNING: reconfig partially applied; master "
                        "may malfunction")
            else:
                log.msg("reconfig aborted without making any changes")
        else:
            log.msg("configuration update complete")

    def reconfigServiceWithBuildbotConfig(self, new_config):
        if self.configured_db_url is None:
            self.configured_db_url = new_config.db['db_url']
        elif (self.configured_db_url != new_config.db['db_url']):
            config.error(
                "Cannot change c['db']['db_url'] after the master has started",
            )

        if self.config.mq['type'] != new_config.mq['type']:
            raise config.ConfigErrors([
                "Cannot change c['mq']['type'] after the master has started",
            ])

        return super().reconfigServiceWithBuildbotConfig(new_config)

    # informational methods
    def allSchedulers(self):
        return list(self.scheduler_manager)

    def getStatus(self):
        """
        @rtype: L{buildbot.status.builder.Status}
        """
        return self.status

    # state maintenance (private)
    def getObjectId(self):
        """
        Return the object id for this master, for associating state with the
        master.

        @returns: ID, via Deferred
        """
        # try to get the cached value
        if self._object_id is not None:
            return defer.succeed(self._object_id)

        # failing that, get it from the DB; multiple calls to this function
        # at the same time will not hurt

        d = self.db.state.getObjectId(self.name,
                                      "buildbot.master.BuildMaster")

        @d.addCallback
        def keep(id):
            self._object_id = id
            return id
        return d

    def _getState(self, name, default=None):
        "private wrapper around C{self.db.state.getState}"
        d = self.getObjectId()

        @d.addCallback
        def get(objectid):
            return self.db.state.getState(objectid, name, default)
        return d

    def _setState(self, name, value):
        "private wrapper around C{self.db.state.setState}"
        d = self.getObjectId()

        @d.addCallback
        def set(objectid):
            return self.db.state.setState(objectid, name, value)
        return d
