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


import weakref

from buildbot import interfaces
from buildbot.data import resultspec
from buildbot.process import buildrequest
from buildbot.process import slavebuilder
from buildbot.process.build import Build
from buildbot.process.slavebuilder import BUILDING
from buildbot.status.builder import RETRY
from buildbot.util import ascii2unicode
from buildbot.util import epoch2datetime
from buildbot.util import service as util_service
from twisted.application import internet
from twisted.application import service
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import failure
from twisted.python import log
from zope.interface import implements


def enforceChosenSlave(bldr, slavebuilder, breq):
    if 'slavename' in breq.properties:
        slavename = breq.properties['slavename']
        if isinstance(slavename, basestring):
            return slavename == slavebuilder.slave.slavename

    return True


class Builder(util_service.ReconfigurableServiceMixin,
              service.MultiService):

    # reconfigure builders before slaves
    reconfig_priority = 196

    def __init__(self, name, _addServices=True):
        service.MultiService.__init__(self)
        self.name = name

        # this is filled on demand by getBuilderId; don't access it directly
        self._builderid = None

        # this is created the first time we get a good build
        self.expectations = None

        # build/wannabuild slots: Build objects move along this sequence
        self.building = []
        # old_building holds active builds that were stolen from a predecessor
        self.old_building = weakref.WeakKeyDictionary()

        # buildslaves which have connected but which are not yet available.
        # These are always in the ATTACHING state.
        self.attaching_slaves = []

        # buildslaves at our disposal. Each SlaveBuilder instance has a
        # .state that is IDLE, PINGING, or BUILDING. "PINGING" is used when a
        # Build is about to start, to make sure that they're still alive.
        self.slaves = []

        self.config = None
        self.builder_status = None

        if _addServices:
            self.reclaim_svc = internet.TimerService(10 * 60,
                                                     self.reclaimAllBuilds)
            self.reclaim_svc.setServiceParent(self)

            # update big status every 30 minutes, working around #1980
            self.updateStatusService = internet.TimerService(30 * 60,
                                                             self.updateBigStatus)
            self.updateStatusService.setServiceParent(self)

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        # find this builder in the config
        for builder_config in new_config.builders:
            if builder_config.name == self.name:
                found_config = True
                break
        assert found_config, "no config found for builder '%s'" % self.name

        # set up a builder status object on the first reconfig
        if not self.builder_status:
            self.builder_status = self.master.status.builderAdded(
                name=builder_config.name,
                basedir=builder_config.builddir,
                tags=builder_config.tags,
                description=builder_config.description)

        self.config = builder_config

        # allocate  builderid now, so that the builder is visible in the web
        # UI; without this, the bulider wouldn't appear until it preformed a
        # build.
        builderid = yield self.getBuilderId()

        self.master.data.updates.updateBuilderInfo(builderid,
                                                   builder_config.description,
                                                   builder_config.tags)

        self.builder_status.setDescription(builder_config.description)
        self.builder_status.setTags(builder_config.tags)
        self.builder_status.setSlavenames(self.config.slavenames)
        self.builder_status.setCacheSize(new_config.caches['Builds'])

        # if we have any slavebuilders attached which are no longer configured,
        # drop them.
        new_slavenames = set(builder_config.slavenames)
        self.slaves = [s for s in self.slaves
                       if s.slave.slavename in new_slavenames]

    def __repr__(self):
        return "<Builder '%r' at %d>" % (self.name, id(self))

    def getBuilderId(self):
        # since findBuilderId is idempotent, there's no reason to add
        # additional locking around this function.
        if self._builderid:
            return defer.succeed(self._builderid)
        # buildbot.config should ensure this is already unicode, but it doesn't
        # hurt to check again
        name = ascii2unicode(self.name)
        d = self.master.data.updates.findBuilderId(name)

        @d.addCallback
        def keep(builderid):
            self._builderid = builderid
            return builderid
        return d

    @defer.inlineCallbacks
    def getOldestRequestTime(self):
        """Returns the submitted_at of the oldest unclaimed build request for
        this builder, or None if there are no build requests.

        @returns: datetime instance or None, via Deferred
        """
        bldrid = yield self.getBuilderId()
        unclaimed = yield self.master.data.get(
            ('builders', bldrid, 'buildrequests'),
            [resultspec.Filter('claimed', 'eq', [False])])
        if unclaimed:
            unclaimed = sorted([brd['submitted_at'] for brd in unclaimed])
            defer.returnValue(unclaimed[0])
        else:
            defer.returnValue(None)

    def reclaimAllBuilds(self):
        brids = set()
        for b in self.building:
            brids.update([br.id for br in b.requests])
        for b in self.old_building:
            brids.update([br.id for br in b.requests])

        if not brids:
            return defer.succeed(None)

        d = self.master.data.updates.reclaimBuildRequests(list(brids))
        d.addErrback(log.err, 'while re-claiming running BuildRequests')
        return d

    def getBuild(self, number):
        for b in self.building:
            if b.build_status and b.build_status.number == number:
                return b
        for b in self.old_building:
            if b.build_status and b.build_status.number == number:
                return b
        return None

    def addLatentSlave(self, slave):
        assert interfaces.ILatentBuildSlave.providedBy(slave)
        for s in self.slaves:
            if s == slave:
                break
        else:
            sb = slavebuilder.LatentSlaveBuilder(slave, self)
            self.builder_status.addPointEvent(
                ['added', 'latent', slave.slavename])
            self.slaves.append(sb)
            self.botmaster.maybeStartBuildsForBuilder(self.name)

    def attached(self, slave, commands):
        """This is invoked by the BuildSlave when the self.slavename bot
        registers their builder.

        @type  slave: L{buildbot.buildslave.BuildSlave}
        @param slave: the BuildSlave that represents the buildslave as a whole
        @type  commands: dict: string -> string, or None
        @param commands: provides the slave's version of each RemoteCommand

        @rtype:  L{twisted.internet.defer.Deferred}
        @return: a Deferred that fires (with 'self') when the slave-side
                 builder is fully attached and ready to accept commands.
        """
        for s in self.attaching_slaves + self.slaves:
            if s.slave == slave:
                # already attached to them. This is fairly common, since
                # attached() gets called each time we receive the builder
                # list from the slave, and we ask for it each time we add or
                # remove a builder. So if the slave is hosting builders
                # A,B,C, and the config file changes A, we'll remove A and
                # re-add it, triggering two builder-list requests, getting
                # two redundant calls to attached() for B, and another two
                # for C.
                #
                # Therefore, when we see that we're already attached, we can
                # just ignore it.
                return defer.succeed(self)

        sb = slavebuilder.SlaveBuilder()
        sb.setBuilder(self)
        self.attaching_slaves.append(sb)
        d = sb.attached(slave, commands)
        d.addCallback(self._attached)
        d.addErrback(self._not_attached, slave)
        return d

    def _attached(self, sb):
        self.builder_status.addPointEvent(['connect', sb.slave.slavename])
        self.attaching_slaves.remove(sb)
        self.slaves.append(sb)

        self.updateBigStatus()

        return self

    def _not_attached(self, why, slave):
        # already log.err'ed by SlaveBuilder._attachFailure
        # TODO: remove from self.slaves (except that detached() should get
        #       run first, right?)
        log.err(why, 'slave failed to attach')
        self.builder_status.addPointEvent(['failed', 'connect',
                                           slave.slavename])
        # TODO: add an HTMLLogFile of the exception

    def detached(self, slave):
        """This is called when the connection to the bot is lost."""
        for sb in self.attaching_slaves + self.slaves:
            if sb.slave == slave:
                break
        else:
            log.msg("WEIRD: Builder.detached(%s) (%s)"
                    " not in attaching_slaves(%s)"
                    " or slaves(%s)" % (slave, slave.slavename,
                                        self.attaching_slaves,
                                        self.slaves))
            return
        if sb.state == BUILDING:
            # the Build's .lostRemote method (invoked by a notifyOnDisconnect
            # handler) will cause the Build to be stopped, probably right
            # after the notifyOnDisconnect that invoked us finishes running.
            pass

        if sb in self.attaching_slaves:
            self.attaching_slaves.remove(sb)
        if sb in self.slaves:
            self.slaves.remove(sb)

        self.builder_status.addPointEvent(['disconnect', slave.slavename])
        sb.detached()  # inform the SlaveBuilder that their slave went away
        self.updateBigStatus()

    def updateBigStatus(self):
        try:
            # Catch exceptions here, since this is called in a LoopingCall.
            if not self.builder_status:
                return
            if not self.slaves:
                self.builder_status.setBigState("offline")
            elif self.building or self.old_building:
                self.builder_status.setBigState("building")
            else:
                self.builder_status.setBigState("idle")
        except Exception:
            log.err(None, "while trying to update status of builder '%s'" % (self.name,))

    def getAvailableSlaves(self):
        return [sb for sb in self.slaves if sb.isAvailable()]

    def canStartWithSlavebuilder(self, slavebuilder):
        locks = [(self.botmaster.getLockFromLockAccess(access), access)
                 for access in self.config.locks]
        return Build.canStartWithSlavebuilder(locks, slavebuilder)

    def canStartBuild(self, slavebuilder, breq):
        if callable(self.config.canStartBuild):
            return defer.maybeDeferred(self.config.canStartBuild, self, slavebuilder, breq)
        return defer.succeed(True)

    @defer.inlineCallbacks
    def _startBuildFor(self, slavebuilder, buildrequests):
        # Build a stack of cleanup functions so that, at any point, we can
        # abort this operation and unwind the commitments made so far.
        cleanups = []

        def run_cleanups():
            try:
                while cleanups:
                    fn = cleanups.pop()
                    fn()
            except Exception:
                log.err(failure.Failure(), "while running %r" % (run_cleanups,))

        # the last cleanup we want to perform is to update the big
        # status based on any other cleanup
        cleanups.append(lambda: self.updateBigStatus())

        build = self.config.factory.newBuild(buildrequests)
        build.setBuilder(self)
        log.msg("starting build %s using slave %s" % (build, slavebuilder))

        # set up locks
        build.setLocks(self.config.locks)
        cleanups.append(slavebuilder.slave.releaseLocks)

        if len(self.config.env) > 0:
            build.setSlaveEnvironment(self.config.env)

        # append the build to self.building
        self.building.append(build)
        cleanups.append(lambda: self.building.remove(build))

        # update the big status accordingly
        self.updateBigStatus()

        try:
            ready = yield slavebuilder.prepare(self.builder_status, build)
        except Exception:
            log.err(failure.Failure(), 'while preparing slavebuilder:')
            ready = False

        # If prepare returns True then it is ready and we start a build
        # If it returns false then we don't start a new build.
        if not ready:
            log.msg("slave %s can't build %s after all; re-queueing the "
                    "request" % (build, slavebuilder))
            run_cleanups()
            defer.returnValue(False)
            return

        # ping the slave to make sure they're still there. If they've
        # fallen off the map (due to a NAT timeout or something), this
        # will fail in a couple of minutes, depending upon the TCP
        # timeout.
        #
        # TODO: This can unnecessarily suspend the starting of a build, in
        # situations where the slave is live but is pushing lots of data to
        # us in a build.
        log.msg("starting build %s.. pinging the slave %s"
                % (build, slavebuilder))
        try:
            ping_success = yield slavebuilder.ping()
        except Exception:
            log.err(failure.Failure(), 'while pinging slave before build:')
            ping_success = False

        if not ping_success:
            log.msg("slave ping failed; re-queueing the request")
            run_cleanups()
            defer.returnValue(False)
            return

        # The buildslave is ready to go. slavebuilder.buildStarted() sets its
        # state to BUILDING (so we won't try to use it for any other builds).
        # This gets set back to IDLE by the Build itself when it finishes.
        slavebuilder.buildStarted()
        cleanups.append(lambda: slavebuilder.buildFinished())

        # tell the remote that it's starting a build, too
        try:
            yield slavebuilder.slave.conn.remoteStartBuild(build.builder.name)
        except Exception:
            log.err(failure.Failure(), 'while calling remote startBuild:')
            run_cleanups()
            defer.returnValue(False)
            return

        # create the BuildStatus object that goes with the Build
        bs = self.builder_status.newBuild()

        # IMPORTANT: no yielding is allowed from here to the startBuild call!

        # it's possible that we lost the slave remote between the ping above
        # and now.  If so, bail out.  The build.startBuild call below transfers
        # responsibility for monitoring this connection to the Build instance,
        # so this check ensures we hand off a working connection.
        if not slavebuilder.slave.conn:  # TODO: replace with isConnected()
            log.msg("slave disappeared before build could start")
            run_cleanups()
            defer.returnValue(False)
            return

        # let status know
        self.master.status.build_started(buildrequests[0].id, self.name, bs)

        # start the build. This will first set up the steps, then tell the
        # BuildStatus that it has started, which will announce it to the world
        # (through our BuilderStatus object, which is its parent).  Finally it
        # will start the actual build process.  This is done with a fresh
        # Deferred since _startBuildFor should not wait until the build is
        # finished.  This uses `maybeDeferred` to ensure that any exceptions
        # raised by startBuild are treated as deferred errbacks (see
        # http://trac.buildbot.net/ticket/2428).
        d = defer.maybeDeferred(build.startBuild,
                                bs, self.expectations, slavebuilder)
        d.addCallback(lambda _: self.buildFinished(build, slavebuilder))
        # this shouldn't happen. if it does, the slave will be wedged
        d.addErrback(log.err, 'from a running build; this is a '
                     'serious error - please file a bug at http://buildbot.net')

        # make sure the builder's status is represented correctly
        self.updateBigStatus()

        defer.returnValue(True)

    def setupProperties(self, props):
        props.setProperty("buildername", self.name, "Builder")
        if len(self.config.properties) > 0:
            for propertyname in self.config.properties:
                props.setProperty(propertyname,
                                  self.config.properties[propertyname],
                                  "Builder")

    def buildFinished(self, build, sb):
        """This is called when the Build has finished (either success or
        failure). Any exceptions during the build are reported with
        results=FAILURE, not with an errback."""

        # by the time we get here, the Build has already released the slave,
        # which will trigger a check for any now-possible build requests
        # (maybeStartBuilds)

        results = build.build_status.getResults()

        self.building.remove(build)
        if results == RETRY:
            d = self._resubmit_buildreqs(build)
            d.addErrback(log.err, 'while resubmitting a build request')
        else:
            complete_at_epoch = reactor.seconds()
            complete_at = epoch2datetime(complete_at_epoch)
            brids = [br.id for br in build.requests]

            d = self.master.data.updates.completeBuildRequests(brids, results, complete_at=complete_at)
            # nothing in particular to do with this deferred, so just log it if
            # it fails..
            d.addErrback(log.err, 'while marking build requests as completed')

        if sb.slave:
            sb.slave.releaseLocks()

        self.updateBigStatus()

    def _resubmit_buildreqs(self, build):
        brids = [br.id for br in build.requests]
        d = self.master.data.updates.unclaimBuildRequests(brids)

        @d.addCallback
        def notify(_):
            pass  # XXX method does not exist
            # self._msg_buildrequests_unclaimed(build.requests)
        return d

    # Build Creation

    @defer.inlineCallbacks
    def maybeStartBuild(self, slavebuilder, breqs, _reactor=reactor):
        # This method is called by the botmaster whenever this builder should
        # start a set of buildrequests on a slave. Do not call this method
        # directly - use master.botmaster.maybeStartBuildsForBuilder, or one of
        # the other similar methods if more appropriate

        # first, if we're not running, then don't start builds; stopService
        # uses this to ensure that any ongoing maybeStartBuild invocations
        # are complete before it stops.
        if not self.running:
            defer.returnValue(False)
            return

        # If the build fails from here on out (e.g., because a slave has failed),
        # it will be handled outside of this function. TODO: test that!

        build_started = yield self._startBuildFor(slavebuilder, breqs)
        defer.returnValue(build_started)

    # a few utility functions to make the maybeStartBuild a bit shorter and
    # easier to read

    def getCollapseRequestsFn(self):
        """Helper function to determine which collapseRequests function to use
        from L{_collapseRequests}, or None for no merging"""
        # first, seek through builder, global, and the default
        collapseRequests_fn = self.config.collapseRequests
        if collapseRequests_fn is None:
            collapseRequests_fn = self.master.config.collapseRequests
        if collapseRequests_fn is None:
            collapseRequests_fn = True

        # then translate False and True properly
        if collapseRequests_fn is False:
            collapseRequests_fn = None
        elif collapseRequests_fn is True:
            collapseRequests_fn = Builder._defaultCollapseRequestFn

        return collapseRequests_fn

    def _defaultCollapseRequestFn(self, brdict1, brdict2):
        return buildrequest.BuildRequest.canBeCollapsed(self.master, brdict1, brdict2)


class BuilderControl:
    implements(interfaces.IBuilderControl)

    def __init__(self, builder, control):
        self.original = builder
        self.control = control

    @defer.inlineCallbacks
    def getPendingBuildRequestControls(self):
        master = self.original.master
        # TODO Use DATA API
        brdicts = yield master.db.buildrequests.getBuildRequests(
            buildername=self.original.name,
            claimed=False)

        # convert those into BuildRequest objects
        buildrequests = []
        for brdict in brdicts:
            br = yield buildrequest.BuildRequest.fromBrdict(
                self.control.master, brdict)
            buildrequests.append(br)

        # and return the corresponding control objects
        defer.returnValue([buildrequest.BuildRequestControl(self.original, r)
                           for r in buildrequests])

    def getBuild(self, number):
        return self.original.getBuild(number)

    def ping(self):
        if not self.original.slaves:
            self.original.builder_status.addPointEvent(["ping", "no slave"])
            return defer.succeed(False)  # interfaces.NoSlaveError
        dl = []
        for s in self.original.slaves:
            dl.append(s.ping(self.original.builder_status))
        d = defer.DeferredList(dl)
        d.addCallback(self._gatherPingResults)
        return d

    def _gatherPingResults(self, res):
        for ignored, success in res:
            if not success:
                return False
        return True
