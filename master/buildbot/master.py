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
from buildbot.util import subscription, epoch2datetime
from buildbot.status.master import Status
from buildbot.changes import changes
from buildbot.changes.manager import ChangeManager
from buildbot import interfaces
from buildbot.process.builder import BuilderControl
from buildbot.db import connector
from buildbot.schedulers.manager import SchedulerManager
from buildbot.buildslave import manager as bslavemanager
from buildbot.process.botmaster import BotMaster
from buildbot.process import debug
from buildbot.process import metrics
from buildbot.process import cache
from buildbot.process.users import users
from buildbot.process.users.manager import UserManagerManager
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE
from buildbot.util.eventual import eventually
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

    # if this quantity of unclaimed build requests are present in the table,
    # then something is probably wrong!  The master will log a WARNING on every
    # database poll operation.
    WARNING_UNCLAIMED_COUNT = 10000

    def __init__(self, basedir, configFileName="master.cfg", umask=None):
        service.MultiService.__init__(self)
        self.setName("buildmaster")

        self.umask = umask

        self.basedir = basedir
        assert os.path.isdir(self.basedir)
        self.configFileName = configFileName

        # set up child services
        self.create_child_services()

        # loop for polling the db
        self.db_loop = None
        # db configured values
        self.configured_db_url = None
        self.configured_poll_interval = None

        # configuration / reconfiguration handling
        self.config = config.MasterConfig()
        self.reconfig_active = False
        self.reconfig_requested = False
        self.reconfig_notifier = None

        # this stores parameters used in the tac file, and is accessed by the
        # WebStatus to duplicate those values.
        self.log_rotation = LogRotation()

        # subscription points
        self._change_subs = \
                subscription.SubscriptionPoint("changes")
        self._new_buildrequest_subs = \
                subscription.SubscriptionPoint("buildrequest_additions")
        self._new_buildset_subs = \
                subscription.SubscriptionPoint("buildset_additions")
        self._complete_buildset_subs = \
                subscription.SubscriptionPoint("buildset_completion")

        # local cache for this master's object ID
        self._object_id = None


    def create_child_services(self):
        # note that these are order-dependent.  If you get the order wrong,
        # you'll know it, as the master will fail to start.

        self.metrics = metrics.MetricLogObserver()
        self.metrics.setServiceParent(self)

        self.caches = cache.CacheManager()
        self.caches.setServiceParent(self)

        self.pbmanager = buildbot.pbmanager.PBManager()
        self.pbmanager.setServiceParent(self)

        self.buildslaves = bslavemanager.BuildslaveManager(self)
        self.buildslaves.setServiceParent(self)

        self.change_svc = ChangeManager(self)
        self.change_svc.setServiceParent(self)

        self.botmaster = BotMaster(self)
        self.botmaster.setServiceParent(self)

        self.scheduler_manager = SchedulerManager(self)
        self.scheduler_manager.setServiceParent(self)

        self.user_manager = UserManagerManager(self)
        self.user_manager.setServiceParent(self)

        self.db = connector.DBConnector(self, self.basedir)
        self.db.setServiceParent(self)

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

            # set up services that need access to the config before everything else
            # gets told to reconfig
            try:
                yield self.db.setup()
            except connector.DatabaseNotReadyError:
                # (message was already logged)
                _reactor.stop()
                return

            if hasattr(signal, "SIGHUP"):
                def sighup(*args):
                    eventually(self.reconfig)
                signal.signal(signal.SIGHUP, sighup)

            if hasattr(signal, "SIGUSR1"):
                def sigusr1(*args):
                    _reactor.callLater(0, self.botmaster.cleanShutdown)
                signal.signal(signal.SIGUSR1, sigusr1)

            # call the parent method
            yield defer.maybeDeferred(lambda :
                    service.MultiService.startService(self))

            # give all services a chance to load the new configuration, rather than
            # the base configuration
            yield self.reconfigService(self.config)
        except:
            f = failure.Failure()
            log.err(f, 'while starting BuildMaster')
            _reactor.stop()

        log.msg("BuildMaster is running")

    @defer.inlineCallbacks
    def stopService(self):
        if self.running:
            yield service.MultiService.stopService(self)
        if self.db_loop:
            self.db_loop.stop()
            self.db_loop = None


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
        if self.configured_db_url is None:
            self.configured_db_url = new_config.db['db_url']
        elif (self.configured_db_url != new_config.db['db_url']):
            config.error(
                "Cannot change c['db']['db_url'] after the master has started",
            )

        # adjust the db poller
        if (self.configured_poll_interval
                != new_config.db['db_poll_interval']):
            if self.db_loop:
                self.db_loop.stop()
                self.db_loop = None
            self.configured_poll_interval = new_config.db['db_poll_interval']
            if self.configured_poll_interval:
                self.db_loop = task.LoopingCall(self.pollDatabase)
                self.db_loop.start(self.configured_poll_interval, now=False)

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
        try:
            hostname = os.uname()[1] # only on unix
        except AttributeError:
            hostname = socket.getfqdn()
        master_name = "%s:%s" % (hostname, os.path.abspath(self.basedir))

        d = self.db.state.getObjectId(master_name,
                "buildbot.master.BuildMaster")
        def keep(id):
            self._object_id = id
            return id
        d.addCallback(keep)
        return d


    ## triggering methods and subscriptions

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
            
        d = defer.succeed(None)
        if src:
            # create user object, returning a corresponding uid
            d.addCallback(lambda _ : users.createUserObject(self, author, src))
         
        # add the Change to the database
        d.addCallback(lambda uid :
                          self.db.changes.addChange(author=author, files=files,
                                          comments=comments, is_dir=is_dir,
                                          revision=revision,
                                          when_timestamp=when_timestamp,
                                          branch=branch, category=category,
                                          revlink=revlink, properties=properties,
                                          repository=repository, codebase=codebase,
                                          project=project, uid=uid))

        # convert the changeid to a Change instance
        d.addCallback(lambda changeid :
            self.db.changes.getChange(changeid))
        d.addCallback(lambda chdict :
            changes.Change.fromChdict(self, chdict))

        def notify(change):
            msg = u"added change %s to database" % change
            log.msg(msg.encode('utf-8', 'replace'))
            # only deliver messages immediately if we're not polling
            if not self.config.db['db_poll_interval']:
                self._change_subs.deliver(change)
            return change
        d.addCallback(notify)
        return d

    def subscribeToChanges(self, callback):
        """
        Request that C{callback} be called with each Change object added to the
        cluster.

        Note: this method will go away in 0.9.x
        """
        return self._change_subs.subscribe(callback)

    def addBuildset(self, **kwargs):
        """
        Add a buildset to the buildmaster and act on it.  Interface is
        identical to
        L{buildbot.db.buildsets.BuildsetConnectorComponent.addBuildset},
        including returning a Deferred, but also potentially triggers the
        resulting builds.
        """
        d = self.db.buildsets.addBuildset(**kwargs)
        def notify((bsid,brids)):
            log.msg("added buildset %d to database" % bsid)
            # note that buildset additions are only reported on this master
            self._new_buildset_subs.deliver(bsid=bsid, **kwargs)
            # only deliver messages immediately if we're not polling
            if not self.config.db['db_poll_interval']:
                for bn, brid in brids.iteritems():
                    self.buildRequestAdded(bsid=bsid, brid=brid,
                                           buildername=bn)
            return (bsid,brids)
        d.addCallback(notify)
        return d

    def subscribeToBuildsets(self, callback):
        """
        Request that C{callback(bsid=bsid, ssid=ssid, reason=reason,
        properties=properties, builderNames=builderNames,
        external_idstring=external_idstring)} be called whenever a buildset is
        added.  Properties is a dictionary as expected for
        L{BuildsetsConnectorComponent.addBuildset}.

        Note that this only works for buildsets added on this master.

        Note: this method will go away in 0.9.x
        """
        return self._new_buildset_subs.subscribe(callback)

    @defer.inlineCallbacks
    def maybeBuildsetComplete(self, bsid):
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
        yield self.db.buildsets.completeBuildset(bsid, cumulative_results)

        # and deliver to any listeners
        self._buildsetComplete(bsid, cumulative_results)

    def _buildsetComplete(self, bsid, results):
        self._complete_buildset_subs.deliver(bsid, results)

    def subscribeToBuildsetCompletions(self, callback):
        """
        Request that C{callback(bsid, result)} be called whenever a
        buildset is complete.

        Note: this method will go away in 0.9.x
        """
        return self._complete_buildset_subs.subscribe(callback)

    def buildRequestAdded(self, bsid, brid, buildername):
        """
        Notifies the master that a build request is available to be claimed;
        this may be a brand new build request, or a build request that was
        previously claimed and unclaimed through a timeout or other calamity.

        @param bsid: containing buildset id
        @param brid: buildrequest ID
        @param buildername: builder named by the build request
        """
        self._new_buildrequest_subs.deliver(
                dict(bsid=bsid, brid=brid, buildername=buildername))

    def subscribeToBuildRequests(self, callback):
        """
        Request that C{callback} be invoked with a dictionary with keys C{brid}
        (the build request id), C{bsid} (buildset id) and C{buildername}
        whenever a new build request is added to the database.  Note that, due
        to the delayed nature of subscriptions, the build request may already
        be claimed by the time C{callback} is invoked.

        Note: this method will go away in 0.9.x
        """
        return self._new_buildrequest_subs.subscribe(callback)


    ## database polling

    def pollDatabase(self):
        # poll each of the tables that can indicate new, actionable stuff for
        # this buildmaster to do.  This is used in a TimerService, so returning
        # a Deferred means that we won't run two polling operations
        # simultaneously.  Each particular poll method handles errors itself,
        # although catastrophic errors are handled here
        d = defer.gatherResults([
            self.pollDatabaseChanges(),
            self.pollDatabaseBuildRequests(),
            # also unclaim
        ])
        d.addErrback(log.err, 'while polling database')
        return d

    _last_processed_change = None
    @defer.inlineCallbacks
    def pollDatabaseChanges(self):
        # Older versions of Buildbot had each scheduler polling the database
        # independently, and storing a "last_processed" state indicating the
        # last change it had processed.  This had the advantage of allowing
        # schedulers to pick up changes that arrived in the database while
        # the scheduler was not running, but was horribly inefficient.

        # This version polls the database on behalf of the schedulers, using a
        # similar state at the master level.

        timer = metrics.Timer("BuildMaster.pollDatabaseChanges()")
        timer.start()

        need_setState = False

        # get the last processed change id
        if self._last_processed_change is None:
            self._last_processed_change = \
                    yield self._getState('last_processed_change')

        # if it's still None, assume we've processed up to the latest changeid
        if self._last_processed_change is None:
            lpc = yield self.db.changes.getLatestChangeid()
            # if there *are* no changes, count the last as '0' so that we don't
            # skip the first change
            if lpc is None:
                lpc = 0
            self._last_processed_change = lpc

            need_setState = True

        if self._last_processed_change is None:
            timer.stop()
            return

        while True:
            changeid = self._last_processed_change + 1
            chdict = yield self.db.changes.getChange(changeid)

            # if there's no such change, we've reached the end and can
            # stop polling
            if not chdict:
                break

            change = yield changes.Change.fromChdict(self, chdict)

            self._change_subs.deliver(change)

            self._last_processed_change = changeid
            need_setState = True

        # write back the updated state, if it's changed
        if need_setState:
            yield self._setState('last_processed_change',
                            self._last_processed_change)
        timer.stop()

    _last_unclaimed_brids_set = None
    _last_claim_cleanup = 0
    @defer.inlineCallbacks
    def pollDatabaseBuildRequests(self):
        # deal with cleaning up unclaimed requests, and (if necessary)
        # requests from a previous instance of this master
        timer = metrics.Timer("BuildMaster.pollDatabaseBuildRequests()")
        timer.start()

        # cleanup unclaimed builds
        since_last_cleanup = reactor.seconds() - self._last_claim_cleanup 
        if since_last_cleanup < self.RECLAIM_BUILD_INTERVAL:
            unclaimed_age = (self.RECLAIM_BUILD_INTERVAL
                           * self.UNCLAIMED_BUILD_FACTOR)
            yield self.db.buildrequests.unclaimExpiredRequests(unclaimed_age)

            self._last_claim_cleanup = reactor.seconds()

        # _last_unclaimed_brids_set tracks the state of unclaimed build
        # requests; whenever it sees a build request which was not claimed on
        # the last poll, it notifies the subscribers.  It only tracks that
        # state within the master instance, though; on startup, it notifies for
        # all unclaimed requests in the database.

        last_unclaimed = self._last_unclaimed_brids_set or set()
        if len(last_unclaimed) > self.WARNING_UNCLAIMED_COUNT:
            log.msg("WARNING: %d unclaimed buildrequests - is a scheduler "
                    "producing builds for which no builder is running?"
                    % len(last_unclaimed))

        # get the current set of unclaimed buildrequests
        now_unclaimed_brdicts = \
            yield self.db.buildrequests.getBuildRequests(claimed=False)
        now_unclaimed = set([ brd['brid'] for brd in now_unclaimed_brdicts ])

        # and store that for next time
        self._last_unclaimed_brids_set = now_unclaimed

        # see what's new, and notify if anything is
        new_unclaimed = now_unclaimed - last_unclaimed
        if new_unclaimed:
            brdicts = dict((brd['brid'], brd) for brd in now_unclaimed_brdicts)
            for brid in new_unclaimed:
                brd = brdicts[brid]
                self.buildRequestAdded(brd['buildsetid'], brd['brid'],
                                       brd['buildername'])
        timer.stop()

    ## state maintenance (private)

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
