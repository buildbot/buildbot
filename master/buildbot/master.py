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

from zope.interface import implements
from twisted.python import log, components, failure
from twisted.internet import defer, reactor, task
from twisted.application import service

import buildbot
import buildbot.pbmanager
from buildbot.util import epoch2datetime
from buildbot.status.master import Status
from buildbot.changes import changes
from buildbot.changes.manager import ChangeManager
from buildbot import interfaces
from buildbot.process.builder import BuilderControl
from buildbot.db import connector as dbconnector, exceptions
from buildbot.mq import connector as mqconnector
from buildbot.data import connector as dataconnector
from buildbot.schedulers.manager import SchedulerManager
from buildbot.process.botmaster import BotMaster
from buildbot.process import debug
from buildbot.process import metrics
from buildbot.process import cache
from buildbot.process.users import users
from buildbot.process.users.manager import UserManagerManager
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE
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

        self.produce_master_msg('started')
        log.msg("BuildMaster is running")


    def stopService(self):
        self.produce_master_msg('stopped')
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
    def addChange(self, who=None, files=None, comments=None, author=None,
            isdir=None, is_dir=None, revision=None, when=None,
            when_timestamp=None, branch=None, category=None, revlink='',
            properties={}, repository='', codebase=None, project='', src=None):
        """
        Add a change to the buildmaster and act on it.

        This is a wrapper around L{ChangesConnectorComponent.addChange} which
        also acts on the resulting change and returns a L{Change} instance.

        Note that all parameters are keyword arguments, although C{who},
        C{files}, and C{comments} can be specified positionally for
        backward-compatibility.

        @param author: the author of this change
        @type author: unicode string

        @param who: deprecated name for C{author}

        @param files: a list of filenames that were changed
        @type branch: list of unicode strings

        @param comments: user comments on the change
        @type branch: unicode string

        @param is_dir: deprecated

        @param isdir: deprecated name for C{is_dir}

        @param revision: the revision identifier for this change
        @type revision: unicode string

        @param when_timestamp: when this change occurred, or the current time
          if None
        @type when_timestamp: datetime instance or None

        @param when: deprecated name and type for C{when_timestamp}
        @type when: integer (UNIX epoch time) or None

        @param branch: the branch on which this change took place
        @type branch: unicode string

        @param category: category for this change (arbitrary use by Buildbot
        users)
        @type category: unicode string

        @param revlink: link to a web view of this revision
        @type revlink: unicode string

        @param properties: properties to set on this change
        @type properties: dictionary with string keys and simple values
        (JSON-able).  Note that the property source is I{not} included
        in this dictionary.

        @param repository: the repository in which this change took place
        @type repository: unicode string

        @param project: the project this change is a part of
        @type project: unicode string

        @param src: source of the change (vcs or other)
        @type src: string

        @returns: L{Change} instance via Deferred
        """
        metrics.MetricCountEvent.log("added_changes", 1)

        # handle translating deprecated names into new names for db.changes
        def handle_deprec(oldname, old, newname, new, default=None,
                          converter = lambda x:x):
            if old is not None:
                if new is None:
                    log.msg("WARNING: change source is using deprecated "
                            "addChange parameter '%s'" % oldname)
                    return converter(old)
                raise TypeError("Cannot provide '%s' and '%s' to addChange"
                                % (oldname, newname))
            if new is None:
                new = default
            return new

        author = handle_deprec("who", who, "author", author)
        is_dir = handle_deprec("isdir", isdir, "is_dir", is_dir,
                                default=0)
        when_timestamp = handle_deprec("when", when,
                                "when_timestamp", when_timestamp,
                                converter=epoch2datetime)

        # add a source to each property
        for n in properties:
            properties[n] = (properties[n], 'Change')

        if codebase is None:
            if self.config.codebaseGenerator is not None:
                chdict = {
                    'changeid': None,
                    'author': author,
                    'files': files,
                    'comments': comments,
                    'is_dir': is_dir,
                    'revision': revision,
                    'when_timestamp': when_timestamp,
                    'branch': branch,
                    'category': category,
                    'revlink': revlink,
                    'properties': properties,
                    'repository': repository,
                    'project': project,
                }
                codebase = self.config.codebaseGenerator(chdict)
            else:
                codebase = ''

        if src:
            # create user object, returning a corresponding uid
            uid = yield users.createUserObject(self, author, src)
        else:
            uid = None

        # add the Change to the database
        chdict = yield self.data.update.addChange(author=author, files=files,
                            comments=comments, is_dir=is_dir,
                            revision=revision, when_timestamp=when_timestamp,
                            branch=branch, category=category,
                            revlink=revlink, properties=properties,
                            repository=repository, project=project,
                            codebase=codebase, uid=uid)

        # convert the changeid to a Change instance
        change = yield changes.Change.fromChdict(self, chdict)

        defer.returnValue(change)

    @defer.inlineCallbacks
    def addBuildset(self, scheduler, **kwargs):
        """
        Add a buildset to the buildmaster and act on it.  Interface is
        identical to
        L{buildbot.db.buildsets.BuildsetConnectorComponent.addBuildset},
        including returning a Deferred, but also potentially triggers the
        resulting builds.  This method also takes a 'scheduler' parameter
        to name the initiating scheduler.
        """
        bsid, brids = yield self.db.buildsets.addBuildset(**kwargs)

        log.msg("added buildset %d to database" % bsid)

        # notify about the component build requests
        for bn, brid in brids.iteritems():
            self.mq.produce(_type='buildrequest', _event='new',
                buildrequest=brid,
                buildset=bsid,
                buildername=bn,
                builderid=-1) # TODO

        # and the buildset itself
        self.mq.produce(_type='buildset', _event='new',
            buildset=bsid,
            external_idstring=kwargs.get('external_idstring', None),
            reason=kwargs['reason'],
            sourcestampsetid=kwargs['sourcestampsetid'],
            buildrequests=brids,
            scheduler=scheduler,
            properties=kwargs.get('properties', {}))

        defer.returnValue((bsid,brids))

    @defer.inlineCallbacks
    def maybeBuildsetComplete(self, bsid, _reactor=reactor):
        """
        Instructs the master to check whether the buildset is complete,
        and notify appropriately if it is.

        Note that buildset completions are only reported on the master
        on which the last build request completes.
        """
        brdicts = yield self.db.buildrequests.getBuildRequests(
            bsid=bsid, complete=False)

        # if there are incomplete buildrequests, bail out
        if brdicts:
            return

        brdicts = yield self.db.buildrequests.getBuildRequests(bsid=bsid)

        # figure out the overall results of the buildset
        cumulative_results = SUCCESS
        for brdict in brdicts:
            if brdict['results'] not in (SUCCESS, WARNINGS):
                cumulative_results = FAILURE

        # mark it as completed in the database
        complete_at_epoch = _reactor.seconds()
        complete_at = epoch2datetime(complete_at_epoch)
        yield self.db.buildsets.completeBuildset(bsid, cumulative_results,
                complete_at=complete_at)

        # new-style notification
        # TODO: Complete state
        self.mq.produce(_type='buildset', _event='complete',
            buildset=bsid,
            complete_at=complete_at_epoch,
            results=cumulative_results)


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
        master_name = "%s:%s" % (self.hostname, os.path.abspath(self.basedir))

        d = self.db.state.getObjectId(master_name,
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

    def produce_master_msg(self, state):
        if not self._master_initialized:
            return

        d = self.getObjectId()
        @d.addCallback
        def send(objectid):
            self.mq.produce(_type='master', _event=state,
                master=objectid,
                hostname=self.hostname,
                basedir=os.path.abspath(self.basedir))
        d.addErrback(log.msg, "while sending master message")

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
