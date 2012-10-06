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
import datetime

from zope.interface import implements
from twisted.python import log, components, failure
from twisted.internet import defer, reactor, task
from twisted.application import service

import buildbot
import buildbot.pbmanager
from buildbot.util import datetime2epoch, ascii2unicode
from buildbot.status.master import Status
from buildbot.changes import changes
from buildbot.changes.manager import ChangeManager
from buildbot import interfaces
from buildbot.process.builder import BuilderControl
from buildbot.db import connector as dbconnector, exceptions
from buildbot.mq import connector as mqconnector
from buildbot.data import connector as dataconnector
from buildbot.www import service as wwwservice
from buildbot.schedulers.manager import SchedulerManager
from buildbot.process.botmaster import BotMaster
from buildbot.process import debug
from buildbot.process import metrics
from buildbot.process import cache
from buildbot.process.users.manager import UserManagerManager
from buildbot import monkeypatches
from buildbot import config

########################################

class LogRotation(object):
    def __init__(self):
        self.rotateLength = 1 * 1000 * 1000 
        self.maxRotatedFiles = 10

class BuildMaster(config.ReconfigurableServiceMixin, service.MultiService):

    # frequency with which to reclaim running builds; this should be set to
    # something fairly long, to avoid undue database load
    RECLAIM_BUILD_INTERVAL = 10*60

    # multiplier on RECLAIM_BUILD_INTERVAL at which a build is considered
    # unclaimed; this should be at least 2 to avoid false positives
    UNCLAIMED_BUILD_FACTOR = 6

    def __init__(self, basedir, configFileName="master.cfg", umask=None):
        service.MultiService.__init__(self)
        self.setName("buildmaster")

        self.umask = umask

        self.basedir = basedir
        if basedir is not None: # None is used in tests
            assert os.path.isdir(self.basedir)
        self.configFileName = configFileName

        # flag so we don't try to do fancy things before the master is ready
        self._master_initialized = False

        # set up child services
        self.create_child_services()

        # configuration / reconfiguration handling
        self.config = config.MasterConfig()
        self.reconfig_active = False
        self.reconfig_requested = False
        self.reconfig_notifier = None

        # this stores parameters used in the tac file, and is accessed by the
        # WebStatus to duplicate those values.
        self.log_rotation = LogRotation()

        # local cache for this master's object ID
        self._object_id = None

        # figure out local hostname
        try:
            self.hostname = os.uname()[1] # only on unix
        except AttributeError:
            self.hostname = socket.getfqdn()

        self.master_name = "%s:%s" % (self.hostname,
                os.path.abspath(self.basedir or '.'))

    def create_child_services(self):
        # note that these are order-dependent.  If you get the order wrong,
        # you'll know it, as the master will fail to start.

        self.metrics = metrics.MetricLogObserver()
        self.metrics.setServiceParent(self)

        self.caches = cache.CacheManager()
        self.caches.setServiceParent(self)

        self.pbmanager = buildbot.pbmanager.PBManager()
        self.pbmanager.setServiceParent(self)

        self.change_svc = ChangeManager(self)
        self.change_svc.setServiceParent(self)

        self.botmaster = BotMaster(self)
        self.botmaster.setServiceParent(self)

        self.scheduler_manager = SchedulerManager(self)
        self.scheduler_manager.setServiceParent(self)

        self.user_manager = UserManagerManager(self)
        self.user_manager.setServiceParent(self)

        self.db = dbconnector.DBConnector(self, self.basedir)
        self.db.setServiceParent(self)

        self.mq = mqconnector.MQConnector(self)
        self.mq.setServiceParent(self)

        self.data = dataconnector.DataConnector(self)
        self.data.setServiceParent(self)

        self.www = wwwservice.WWWService(self)
        self.www.setServiceParent(self)

        self.debug = debug.DebugServices(self)
        self.debug.setServiceParent(self)

        self.status = Status(self)
        self.status.setServiceParent(self)

    # setup and reconfig handling

    _already_started = False
    @defer.inlineCallbacks
    def startService(self, _reactor=reactor):
        assert not self._already_started, "can only start the master once"
        self._already_started = True

        log.msg("Starting BuildMaster -- buildbot.version: %s" %
                buildbot.version)
        
        # Set umask
        if self.umask is not None:
            os.umask(self.umask)

        # first, apply all monkeypatches
        monkeypatches.patch_all()

        # we want to wait until the reactor is running, so we can call
        # reactor.stop() for fatal errors
        d = defer.Deferred()
        _reactor.callWhenRunning(d.callback, None)
        yield d

        try:
            # load the configuration file, treating errors as fatal
            try:
                self.config = config.MasterConfig.loadConfig(self.basedir,
                                                        self.configFileName)
            except config.ConfigErrors, e:
                log.msg("Configuration Errors:")
                for msg in e.errors:
                    log.msg("  " + msg)
                log.msg("Halting master.")
                _reactor.stop()
                return
            except:
                log.err(failure.Failure(), 'while starting BuildMaster')
                _reactor.stop()
                return

            # set up services that need access to the config before everything
            # else gets told to reconfig
            try:
                yield self.db.setup()
            except exceptions.DatabaseNotReadyError:
                # (message was already logged)
                _reactor.stop()
                return

            self.mq.setup()

            if hasattr(signal, "SIGHUP"):
                def sighup(*args):
                    _reactor.callLater(0, self.reconfig)
                signal.signal(signal.SIGHUP, sighup)

            # call the parent method
            yield defer.maybeDeferred(lambda :
                    service.MultiService.startService(self))

            # give all services a chance to load the new configuration, rather
            # than the base configuration
            yield self.reconfigService(self.config)

        except:
            f = failure.Failure()
            log.err(f, 'while starting BuildMaster')
            _reactor.stop()

        self._master_initialized = True

        self._setMasterState('started')
        log.msg("BuildMaster is running")


    def stopService(self):
        self._setMasterState('stopped')
        log.msg("BuildMsater is stopped")
        self._master_initialized = False


    def reconfig(self):
        # this method wraps doConfig, ensuring it is only ever called once at
        # a time, and alerting the user if the reconfig takes too long
        if self.reconfig_active:
            log.msg("reconfig already active; will reconfig again after")
            self.reconfig_requested = True
            return

        self.reconfig_active = reactor.seconds()
        metrics.MetricCountEvent.log("loaded_config", 1)

        # notify every 10 seconds that the reconfig is still going on, although
        # reconfigs should not take that long!
        self.reconfig_notifier = task.LoopingCall(lambda :
            log.msg("reconfig is ongoing for %d s" %
                    (reactor.seconds() - self.reconfig_active)))
        self.reconfig_notifier.start(10, now=False)

        timer = metrics.Timer("BuildMaster.reconfig")
        timer.start()

        d = self.doReconfig()

        @d.addBoth
        def cleanup(res):
            timer.stop()
            self.reconfig_notifier.stop()
            self.reconfig_notifier = None
            self.reconfig_active = False
            if self.reconfig_requested:
                self.reconfig_requested = False
                self.reconfig()
            return res

        d.addErrback(log.err, 'while reconfiguring')

        return d # for tests


    @defer.inlineCallbacks
    def doReconfig(self):
        log.msg("beginning configuration update")
        changes_made = False
        failed = False
        try:
            new_config = config.MasterConfig.loadConfig(self.basedir,
                                                    self.configFileName)
            changes_made = True
            self.config = new_config
            yield self.reconfigService(new_config)

        except config.ConfigErrors, e:
            for msg in e.errors:
                log.msg(msg)
            failed = True

        except:
            log.err(failure.Failure(), 'during reconfig:')
            failed = True

        if failed:
            if changes_made:
                log.msg("WARNING: reconfig partially applied; master "
                        "may malfunction")
            else:
                log.msg("reconfig aborted without making any changes")
        else:
            log.msg("configuration update complete")


    def reconfigService(self, new_config):
        if self.config.db['db_url'] != new_config.db['db_url']:
            config.error(
                "Cannot change c['db']['db_url'] after the master has started",
            )

        if self.config.mq['type'] != new_config.mq['type']:
            raise config.ConfigErrors([
                "Cannot change c['mq']['type'] after the master has started",
            ])

        return config.ReconfigurableServiceMixin.reconfigService(self,
                                            new_config)


    ## informational methods

    def allSchedulers(self):
        return list(self.scheduler_manager)

    def getStatus(self):
        """
        @rtype: L{buildbot.status.builder.Status}
        """
        return self.status

    ## triggering methods

    @defer.inlineCallbacks
    def addChange(self, who=None, files=None, comments=None, **kwargs):
        # deprecated in 0.9.0; will be removed in 1.0.0
        log.msg("WARNING: change source is using deprecated "
                "self.master.addChange method; this method will disappear in "
                "Buildbot-1.0.0")
        # handle positional arguments
        kwargs['who'] = who
        kwargs['files'] = files
        kwargs['comments'] = comments

        def handle_deprec(oldname, newname):
            if oldname not in kwargs:
                return
            old = kwargs.pop(oldname)
            if old is not None:
                if kwargs.get(newname) is None:
                    log.msg("WARNING: change source is using deprecated "
                            "addChange parameter '%s'" % oldname)
                    return old
                raise TypeError("Cannot provide '%s' and '%s' to addChange"
                                % (oldname, newname))
            return kwargs.get(newname)

        kwargs['author'] = handle_deprec("who", "author")
        kwargs['when_timestamp'] = handle_deprec("when", "when_timestamp")

        # is_dir and isdir are gone
        for oldname in 'is_dir', 'isdir':
            if oldname in kwargs:
                log.msg("WARNING: change source is providing deprecated "
                        "value %s (ignored)" % (oldname,))
                kwargs.pop(oldname)

        # timestamp must be an epoch timestamp now
        if isinstance(kwargs.get('when_timestamp'), datetime.datetime):
            kwargs['when_timestamp'] = datetime2epoch(kwargs['when_timestamp'])

        # unicodify stuff
        for k in ('comments', 'author', 'revision', 'branch', 'category',
                  'revlink', 'repository', 'codebase', 'project'):
            if k in kwargs:
                kwargs[k] = ascii2unicode(kwargs[k])
        if kwargs.get('files'):
            kwargs['files'] = [ ascii2unicode(f)
                                for f in kwargs['files'] ]
        if kwargs.get('properties'):
            kwargs['properties'] = dict( (ascii2unicode(k), v)
                for k, v in kwargs['properties'].iteritems() )


        # pass the converted call on to the data API
        changeid = yield self.data.updates.addChange(**kwargs)

        # and turn that changeid into a change object, since that's what
        # callers expected (and why this method was deprecated)
        chdict = yield self.db.changes.getChange(changeid)
        change = yield changes.Change.fromChdict(self, chdict)
        defer.returnValue(change)


    ## state maintenance (private)

    def getObjectId(self):
        """
        Return the obejct id for this master, for associating state with the
        master.

        @returns: ID, via Deferred
        """
        # try to get the cached value
        if self._object_id is not None:
            return defer.succeed(self._object_id)

        # failing that, get it from the DB; multiple calls to this function
        # at the same time will not hurt

        d = self.db.state.getObjectId(self.master_name,
                "buildbot.master.BuildMaster")
        def keep(id):
            self._object_id = id
            return id
        d.addCallback(keep)
        return d

    def _getState(self, name, default=None):
        "private wrapper around C{self.db.state.getState}"
        d = self.getObjectId()
        def get(objectid):
            return self.db.state.getState(objectid, name, default)
        d.addCallback(get)
        return d

    def _setState(self, name, value):
        "private wrapper around C{self.db.state.setState}"
        d = self.getObjectId()
        def set(objectid):
            return self.db.state.setState(objectid, name, value)
        d.addCallback(set)
        return d

    # master messages

    def _setMasterState(self, state):
        # for early termination and a few other cases, don't explode
        if not self._master_initialized:
            return
        d = self.data.updates.setMasterState(state=state)
        d.addErrback(log.err, "while sending master message")

class Control:
    implements(interfaces.IControl)

    def __init__(self, master):
        self.master = master

    def addChange(self, change):
        self.master.addChange(change)

    def addBuildset(self, **kwargs):
        return self.master.addBuildset(**kwargs)

    def getBuilder(self, name):
        b = self.master.botmaster.builders[name]
        return BuilderControl(b, self)

components.registerAdapter(Control, BuildMaster, interfaces.IControl)
