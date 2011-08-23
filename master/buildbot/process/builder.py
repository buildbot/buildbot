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


import random, weakref
from zope.interface import implements
from twisted.python import log, failure
from twisted.spread import pb
from twisted.application import service, internet
from twisted.internet import defer

from buildbot import interfaces
from buildbot.status.progress import Expectations
from buildbot.status.builder import RETRY
from buildbot.status.buildrequest import BuildRequestStatus
from buildbot.process.properties import Properties
from buildbot.process import buildrequest, slavebuilder
from buildbot.process.slavebuilder import BUILDING
from buildbot.db import buildrequests

class Builder(pb.Referenceable, service.MultiService):
    """I manage all Builds of a given type.

    Each Builder is created by an entry in the config file (the c['builders']
    list), with a number of parameters.

    One of these parameters is the L{buildbot.process.factory.BuildFactory}
    object that is associated with this Builder. The factory is responsible
    for creating new L{Build<buildbot.process.build.Build>} objects. Each
    Build object defines when and how the build is performed, so a new
    Factory or Builder should be defined to control this behavior.

    The Builder holds on to a number of L{BuildRequest} objects in a
    list named C{.buildable}. Incoming BuildRequest objects will be added to
    this list, or (if possible) merged into an existing request. When a slave
    becomes available, I will use my C{BuildFactory} to turn the request into
    a new C{Build} object. The C{BuildRequest} is forgotten, the C{Build}
    goes into C{.building} while it runs. Once the build finishes, I will
    discard it.

    I maintain a list of available SlaveBuilders, one for each connected
    slave that the C{slavenames} parameter says we can use. Some of these
    will be idle, some of them will be busy running builds for me. If there
    are multiple slaves, I can run multiple builds at once.

    I also manage forced builds, progress expectation (ETA) management, and
    some status delivery chores.

    @type buildable: list of L{buildbot.process.buildrequest.BuildRequest}
    @ivar buildable: BuildRequests that are ready to build, but which are
                     waiting for a buildslave to be available.

    @type building: list of L{buildbot.process.build.Build}
    @ivar building: Builds that are actively running

    @type slaves: list of L{buildbot.buildslave.BuildSlave} objects
    @ivar slaves: the slaves currently available for building
    """

    expectations = None # this is created the first time we get a good build

    def __init__(self, setup, builder_status):
        """
        @type  setup: dict
        @param setup: builder setup data, as stored in
                      BuildmasterConfig['builders'].  Contains name,
                      slavename(s), builddir, slavebuilddir, factory, locks.
        @type  builder_status: L{buildbot.status.builder.BuilderStatus}
        """
        service.MultiService.__init__(self)
        self.name = setup['name']
        self.slavenames = []
        if setup.has_key('slavename'):
            self.slavenames.append(setup['slavename'])
        if setup.has_key('slavenames'):
            self.slavenames.extend(setup['slavenames'])
        self.builddir = setup['builddir']
        self.slavebuilddir = setup['slavebuilddir']
        self.buildFactory = setup['factory']
        self.nextSlave = setup.get('nextSlave')
        if self.nextSlave is not None and not callable(self.nextSlave):
            raise ValueError("nextSlave must be callable")
        self.locks = setup.get("locks", [])
        self.env = setup.get('env', {})
        assert isinstance(self.env, dict)
        if setup.has_key('periodicBuildTime'):
            raise ValueError("periodicBuildTime can no longer be defined as"
                             " part of the Builder: use scheduler.Periodic"
                             " instead")
        self.nextBuild = setup.get('nextBuild')
        if self.nextBuild is not None and not callable(self.nextBuild):
            raise ValueError("nextBuild must be callable")
        self.buildHorizon = setup.get('buildHorizon')
        self.logHorizon = setup.get('logHorizon')
        self.eventHorizon = setup.get('eventHorizon')
        self.mergeRequests = setup.get('mergeRequests', None)
        self.properties = setup.get('properties', {})
        self.category = setup.get('category', None)

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

        self.builder_status = builder_status
        self.builder_status.setSlavenames(self.slavenames)
        self.builder_status.buildHorizon = self.buildHorizon
        self.builder_status.logHorizon = self.logHorizon
        self.builder_status.eventHorizon = self.eventHorizon

        self.reclaim_svc = internet.TimerService(10*60, self.reclaimAllBuilds)
        self.reclaim_svc.setServiceParent(self)

        # for testing, to help synchronize tests
        self.run_count = 0

    def stopService(self):
        d = defer.maybeDeferred(lambda :
                service.MultiService.stopService(self))
        def flushMaybeStartBuilds(_):
            # at this point, self.running = False, so another maybeStartBuilds
            # invocation won't hurt anything, but it also will not complete
            # until any currently-running invocations are done.
            return self.maybeStartBuild()
        d.addCallback(flushMaybeStartBuilds)
        return d

    def setBotmaster(self, botmaster):
        self.botmaster = botmaster
        self.master = botmaster.master
        self.db = self.master.db

    def compareToSetup(self, setup):
        diffs = []
        setup_slavenames = []
        if setup.has_key('slavename'):
            setup_slavenames.append(setup['slavename'])
        setup_slavenames.extend(setup.get('slavenames', []))
        if setup_slavenames != self.slavenames:
            diffs.append('slavenames changed from %s to %s' \
                         % (self.slavenames, setup_slavenames))
        if setup['builddir'] != self.builddir:
            diffs.append('builddir changed from %s to %s' \
                         % (self.builddir, setup['builddir']))
        if setup['slavebuilddir'] != self.slavebuilddir:
            diffs.append('slavebuilddir changed from %s to %s' \
                         % (self.slavebuilddir, setup['slavebuilddir']))
        if setup['factory'] != self.buildFactory: # compare objects
            diffs.append('factory changed')
        if setup.get('locks', []) != self.locks:
            diffs.append('locks changed from %s to %s' % (self.locks, setup.get('locks')))
        if setup.get('env', {}) != self.env:
            diffs.append('env changed from %s to %s' % (self.env, setup.get('env', {})))
        if setup.get('nextSlave') != self.nextSlave:
            diffs.append('nextSlave changed from %s to %s' % (self.nextSlave, setup.get('nextSlave')))
        if setup.get('nextBuild') != self.nextBuild:
            diffs.append('nextBuild changed from %s to %s' % (self.nextBuild, setup.get('nextBuild')))
        if setup.get('buildHorizon', None) != self.buildHorizon:
            diffs.append('buildHorizon changed from %s to %s' % (self.buildHorizon, setup['buildHorizon']))
        if setup.get('logHorizon', None) != self.logHorizon:
            diffs.append('logHorizon changed from %s to %s' % (self.logHorizon, setup['logHorizon']))
        if setup.get('eventHorizon', None) != self.eventHorizon:
            diffs.append('eventHorizon changed from %s to %s' % (self.eventHorizon, setup['eventHorizon']))
        if setup.get('category', None) != self.category:
            diffs.append('category changed from %r to %r' % (self.category, setup.get('category', None)))

        return diffs

    def __repr__(self):
        return "<Builder '%r' at %d>" % (self.name, id(self))

    @defer.deferredGenerator
    def getOldestRequestTime(self):

        """Returns the submitted_at of the oldest unclaimed build request for
        this builder, or None if there are no build requests.

        @returns: datetime instance or None, via Deferred
        """
        wfd = defer.waitForDeferred(
            self.master.db.buildrequests.getBuildRequests(
                        buildername=self.name, claimed=False))
        yield wfd
        unclaimed = wfd.getResult()

        if unclaimed:
            unclaimed = [ brd['submitted_at'] for brd in unclaimed ]
            unclaimed.sort()
            yield unclaimed[0]
        else:
            yield None

    def consumeTheSoulOfYourPredecessor(self, old):
        """Suck the brain out of an old Builder.

        This takes all the runtime state from an existing Builder and moves
        it into ourselves. This is used when a Builder is changed in the
        master.cfg file: the new Builder has a different factory, but we want
        all the builds that were queued for the old one to get processed by
        the new one. Any builds which are already running will keep running.
        The new Builder will get as many of the old SlaveBuilder objects as
        it wants."""

        log.msg("consumeTheSoulOfYourPredecessor: %s feeding upon %s" %
                (self, old))
        # all pending builds are stored in the DB, so we don't have to do
        # anything to claim them. The old builder will be stopService'd,
        # which should make sure they don't start any new work

        # this is kind of silly, but the builder status doesn't get updated
        # when the config changes, yet it stores the category.  So:
        self.builder_status.category = self.category

        # old.building (i.e. builds which are still running) is not migrated
        # directly: it keeps track of builds which were in progress in the
        # old Builder. When those builds finish, the old Builder will be
        # notified, not us. However, since the old SlaveBuilder will point to
        # us, it is our maybeStartBuild() that will be triggered.
        if old.building:
            self.builder_status.setBigState("building")
        # however, we do grab a weakref to the active builds, so that our
        # BuilderControl can see them and stop them. We use a weakref because
        # we aren't the one to get notified, so there isn't a convenient
        # place to remove it from self.building .
        for b in old.building:
            self.old_building[b] = None
        for b in old.old_building:
            self.old_building[b] = None

        # Our set of slavenames may be different. Steal any of the old
        # buildslaves that we want to keep using.
        for sb in old.slaves[:]:
            if sb.slave.slavename in self.slavenames:
                log.msg(" stealing buildslave %s" % sb)
                self.slaves.append(sb)
                old.slaves.remove(sb)
                sb.setBuilder(self)

        # old.attaching_slaves:
        #  these SlaveBuilders are waiting on a sequence of calls:
        #  remote.setMaster and remote.print . When these two complete,
        #  old._attached will be fired, which will add a 'connect' event to
        #  the builder_status and try to start a build. However, we've pulled
        #  everything out of the old builder's queue, so it will have no work
        #  to do. The outstanding remote.setMaster/print call will be holding
        #  the last reference to the old builder, so it will disappear just
        #  after that response comes back.
        #
        #  The BotMaster will ask the slave to re-set their list of Builders
        #  shortly after this function returns, which will cause our
        #  attached() method to be fired with a bunch of references to remote
        #  SlaveBuilders, some of which we already have (by stealing them
        #  from the old Builder), some of which will be new. The new ones
        #  will be re-attached.

        #  Therefore, we don't need to do anything about old.attaching_slaves

        return # all done

    def reclaimAllBuilds(self):
        brids = set()
        for b in self.building:
            brids.update([br.id for br in b.requests])
        for b in self.old_building:
            brids.update([br.id for br in b.requests])

        if not brids:
            return defer.succeed(None)

        d = self.master.db.buildrequests.reclaimBuildRequests(brids)
        d.addErrback(log.err, 'while re-claiming running BuildRequests')
        return d

    def getBuild(self, number):
        for b in self.building:
            if b.build_status and b.build_status.number == number:
                return b
        for b in self.old_building.keys():
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

    def attached(self, slave, remote, commands):
        """This is invoked by the BuildSlave when the self.slavename bot
        registers their builder.

        @type  slave: L{buildbot.buildslave.BuildSlave}
        @param slave: the BuildSlave that represents the buildslave as a whole
        @type  remote: L{twisted.spread.pb.RemoteReference}
        @param remote: a reference to the L{buildbot.slave.bot.SlaveBuilder}
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
        d = sb.attached(slave, remote, commands)
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
        sb.detached() # inform the SlaveBuilder that their slave went away
        self.updateBigStatus()

    def updateBigStatus(self):
        if not self.slaves:
            self.builder_status.setBigState("offline")
        elif self.building or self.old_building:
            self.builder_status.setBigState("building")
        else:
            self.builder_status.setBigState("idle")

    @defer.deferredGenerator
    def _startBuildFor(self, slavebuilder, buildrequests):
        """Start a build on the given slave.
        @param build: the L{base.Build} to start
        @param sb: the L{SlaveBuilder} which will host this build

        @return: (via Deferred) boolean indicating that the build was
        succesfully started.
        """

        # as of the Python versions supported now, try/finally can't be used
        # with a generator expression.  So instead, we push cleanup functions
        # into a list so that, at any point, we can abort this operation.
        cleanups = []
        def run_cleanups():
            while cleanups:
                fn = cleanups.pop()
                fn()

        # the last cleanup we want to perform is to update the big
        # status based on any other cleanup
        cleanups.append(lambda : self.updateBigStatus())

        build = self.buildFactory.newBuild(buildrequests)
        build.setBuilder(self)
        log.msg("starting build %s using slave %s" % (build, slavebuilder))

        # set up locks
        build.setLocks(self.locks)
        cleanups.append(lambda : slavebuilder.slave.releaseLocks())

        if len(self.env) > 0:
            build.setSlaveEnvironment(self.env)

        # append the build to self.building
        self.building.append(build)
        cleanups.append(lambda : self.building.remove(build))

        # update the big status accordingly
        self.updateBigStatus()

        try:
            wfd = defer.waitForDeferred(
                    slavebuilder.prepare(self.builder_status, build))
            yield wfd
            ready = wfd.getResult()
        except:
            log.err(failure.Failure(), 'while preparing slavebuilder:')
            ready = False

        # If prepare returns True then it is ready and we start a build
        # If it returns false then we don't start a new build.
        if not ready:
            log.msg("slave %s can't build %s after all; re-queueing the "
                    "request" % (build, slavebuilder))
            run_cleanups()
            yield False
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
            wfd = defer.waitForDeferred(
                    slavebuilder.ping())
            yield wfd
            ping_success = wfd.getResult()
        except:
            log.err(failure.Failure(), 'while pinging slave before build:')
            ping_success = False

        if not ping_success:
            log.msg("slave ping failed; re-queueing the request")
            run_cleanups()
            yield False
            return

        # The buildslave is ready to go. slavebuilder.buildStarted() sets its
        # state to BUILDING (so we won't try to use it for any other builds).
        # This gets set back to IDLE by the Build itself when it finishes.
        slavebuilder.buildStarted()
        cleanups.append(lambda : slavebuilder.buildFinished())

        # tell the remote that it's starting a build, too
        try:
            wfd = defer.waitForDeferred(
                    slavebuilder.remote.callRemote("startBuild"))
            yield wfd
            wfd.getResult()
        except:
            log.err(failure.Failure(), 'while calling remote startBuild:')
            run_cleanups()
            yield False
            return

        # create the BuildStatus object that goes with the Build
        bs = self.builder_status.newBuild()

        # record the build in the db - one row per buildrequest
        try:
            bids = []
            for req in build.requests:
                wfd = defer.waitForDeferred(
                    self.master.db.builds.addBuild(req.id, bs.number))
                yield wfd
                bids.append(wfd.getResult())
        except:
            log.err(failure.Failure(), 'while adding rows to build table:')
            run_cleanups()
            yield False
            return

        # let status know
        self.master.status.build_started(req.id, self.name, bs)

        # start the build. This will first set up the steps, then tell the
        # BuildStatus that it has started, which will announce it to the world
        # (through our BuilderStatus object, which is its parent).  Finally it
        # will start the actual build process.  This is done with a fresh
        # Deferred since _startBuildFor should not wait until the build is
        # finished.
        d = build.startBuild(bs, self.expectations, slavebuilder)
        d.addCallback(self.buildFinished, slavebuilder, bids)
        # this shouldn't happen. if it does, the slave will be wedged
        d.addErrback(log.err)

        # make sure the builder's status is represented correctly
        self.updateBigStatus()

        yield True

    def setupProperties(self, props):
        props.setProperty("buildername", self.name, "Builder")
        if len(self.properties) > 0:
            for propertyname in self.properties:
                props.setProperty(propertyname, self.properties[propertyname],
                                  "Builder")

    def buildFinished(self, build, sb, bids):
        """This is called when the Build has finished (either success or
        failure). Any exceptions during the build are reported with
        results=FAILURE, not with an errback."""

        # by the time we get here, the Build has already released the slave,
        # which will trigger a check for any now-possible build requests
        # (maybeStartBuilds)

        # mark the builds as finished, although since nothing ever reads this
        # table, it's not too important that it complete successfully
        d = self.db.builds.finishBuilds(bids)
        d.addErrback(log.err, 'while marking builds as finished (ignored)')

        results = build.build_status.getResults()
        self.building.remove(build)
        if results == RETRY:
            self._resubmit_buildreqs(build).addErrback(log.err)
        else:
            brids = [br.id for br in build.requests]
            db = self.master.db
            d = db.buildrequests.completeBuildRequests(brids, results)
            d.addCallback(
                lambda _ : self._maybeBuildsetsComplete(build.requests))
            # nothing in particular to do with this deferred, so just log it if
            # it fails..
            d.addErrback(log.err, 'while marking build requests as completed')

        if sb.slave:
            sb.slave.releaseLocks()

        self.updateBigStatus()

    @defer.deferredGenerator
    def _maybeBuildsetsComplete(self, requests):
        # inform the master that we may have completed a number of buildsets
        for br in requests:
            wfd = defer.waitForDeferred(
                self.master.maybeBuildsetComplete(br.bsid))
            yield wfd
            wfd.getResult()

    def _resubmit_buildreqs(self, build):
        brids = [br.id for br in build.requests]
        return self.db.buildrequests.unclaimBuildRequests(brids)

    def setExpectations(self, progress):
        """Mark the build as successful and update expectations for the next
        build. Only call this when the build did not fail in any way that
        would invalidate the time expectations generated by it. (if the
        compile failed and thus terminated early, we can't use the last
        build to predict how long the next one will take).
        """
        if self.expectations:
            self.expectations.update(progress)
        else:
            # the first time we get a good build, create our Expectations
            # based upon its results
            self.expectations = Expectations(progress)
        log.msg("new expectations: %s seconds" % \
                self.expectations.expectedBuildTime())

    # Build Creation

    @defer.deferredGenerator
    def maybeStartBuild(self):
        # This method is called by the botmaster whenever this builder should
        # check for and potentially start new builds.  Do not call this method
        # directly - use master.botmaster.maybeStartBuildsForBuilder, or one
        # of the other similar methods if more appropriate

        # first, if we're not running, then don't start builds; stopService
        # uses this to ensure that any ongoing maybeStartBuild invocations
        # are complete before it stops.
        if not self.running:
            return

        # Check for available slaves.  If there are no available slaves, then
        # there is no sense continuing
        available_slavebuilders = [ sb for sb in self.slaves
                                    if sb.isAvailable() ]
        if not available_slavebuilders:
            self.updateBigStatus()
            return

        # now, get the available build requests
        wfd = defer.waitForDeferred(
                self.master.db.buildrequests.getBuildRequests(
                        buildername=self.name, claimed=False))
        yield wfd
        unclaimed_requests = wfd.getResult()

        if not unclaimed_requests:
            self.updateBigStatus()
            return

        # sort by submitted_at, so the first is the oldest
        unclaimed_requests.sort(key=lambda brd : brd['submitted_at'])

        # get the mergeRequests function for later
        mergeRequests_fn = self._getMergeRequestsFn()

        # match them up until we're out of options
        while available_slavebuilders and unclaimed_requests:
            # first, choose a slave (using nextSlave)
            wfd = defer.waitForDeferred(
                self._chooseSlave(available_slavebuilders))
            yield wfd
            slavebuilder = wfd.getResult()

            if not slavebuilder:
                break

            if slavebuilder not in available_slavebuilders:
                log.msg(("nextSlave chose a nonexistent slave for builder "
                         "'%s'; cannot start build") % self.name)
                break

            # then choose a request (using nextBuild)
            wfd = defer.waitForDeferred(
                self._chooseBuild(unclaimed_requests))
            yield wfd
            brdict = wfd.getResult()

            if not brdict:
                break

            if brdict not in unclaimed_requests:
                log.msg(("nextBuild chose a nonexistent request for builder "
                         "'%s'; cannot start build") % self.name)
                break

            # merge the chosen request with any compatible requests in the
            # queue
            wfd = defer.waitForDeferred(
                self._mergeRequests(brdict, unclaimed_requests,
                                    mergeRequests_fn))
            yield wfd
            brdicts = wfd.getResult()

            # try to claim the build requests
            brids = [ brdict['brid'] for brdict in brdicts ]
            try:
                wfd = defer.waitForDeferred(
                        self.master.db.buildrequests.claimBuildRequests(brids))
                yield wfd
                wfd.getResult()
            except buildrequests.AlreadyClaimedError:
                # one or more of the build requests was already claimed;
                # re-fetch the now-partially-claimed build requests and keep
                # trying to match them
                self._breakBrdictRefloops(unclaimed_requests)
                wfd = defer.waitForDeferred(
                        self.master.db.buildrequests.getBuildRequests(
                                buildername=self.name, claimed=False))
                yield wfd
                unclaimed_requests = wfd.getResult()

                # go around the loop again
                continue

            # claim was successful, so initiate a build for this set of
            # requests.  Note that if the build fails from here on out (e.g.,
            # because a slave has failed), it will be handled outside of this
            # loop. TODO: test that!

            # _startBuildFor expects BuildRequest objects, so cook some up
            wfd = defer.waitForDeferred(
                    defer.gatherResults([ self._brdictToBuildRequest(brdict)
                                          for brdict in brdicts ]))
            yield wfd
            breqs = wfd.getResult()

            wfd = defer.waitForDeferred(
                    self._startBuildFor(slavebuilder, breqs))
            yield wfd
            build_started = wfd.getResult()

            if not build_started:
                # build was not started, so unclaim the build requests
                wfd = defer.waitForDeferred(
                    self.master.db.buildrequests.unclaimBuildRequests(brids))
                yield wfd
                wfd.getResult()

                # and try starting builds again.  If we still have a working slave,
                # then this may re-claim the same buildrequests
                self.botmaster.maybeStartBuildsForBuilder(self.name)

            # finally, remove the buildrequests and slavebuilder from the
            # respective queues
            self._breakBrdictRefloops(brdicts)
            for brdict in brdicts:
                unclaimed_requests.remove(brdict)
            available_slavebuilders.remove(slavebuilder)

        self._breakBrdictRefloops(unclaimed_requests)
        self.updateBigStatus()
        return

    # a few utility functions to make the maybeStartBuild a bit shorter and
    # easier to read

    def _chooseSlave(self, available_slavebuilders):
        """
        Choose the next slave, using the C{nextSlave} configuration if
        available, and falling back to C{random.choice} otherwise.

        @param available_slavebuilders: list of slavebuilders to choose from
        @returns: SlaveBuilder or None via Deferred
        """
        if self.nextSlave:
            return defer.maybeDeferred(lambda :
                    self.nextSlave(self, available_slavebuilders))
        else:
            return defer.succeed(random.choice(available_slavebuilders))

    def _chooseBuild(self, buildrequests):
        """
        Choose the next build from the given set of build requests (represented
        as dictionaries).  Defaults to returning the first request (earliest
        submitted).

        @param buildrequests: sorted list of build request dictionaries
        @returns: a build request dictionary or None via Deferred
        """
        if self.nextBuild:
            # nextBuild expects BuildRequest objects, so instantiate them here
            # and cache them in the dictionaries
            d = defer.gatherResults([ self._brdictToBuildRequest(brdict)
                                      for brdict in buildrequests ])
            d.addCallback(lambda requestobjects :
                    self.nextBuild(self, requestobjects))
            def to_brdict(brobj):
                # get the brdict for this object back
                return brobj.brdict
            d.addCallback(to_brdict)
            return d
        else:
            return defer.succeed(buildrequests[0])

    def _getMergeRequestsFn(self):
        """Helper function to determine which mergeRequests function to use
        from L{_mergeRequests}, or None for no merging"""
        # first, seek through builder, global, and the default
        mergeRequests_fn = self.mergeRequests
        if mergeRequests_fn is None:
            mergeRequests_fn = self.botmaster.mergeRequests
        if mergeRequests_fn is None:
            mergeRequests_fn = True

        # then translate False and True properly
        if mergeRequests_fn is False:
            mergeRequests_fn = None
        elif mergeRequests_fn is True:
            mergeRequests_fn = Builder._defaultMergeRequestFn

        return mergeRequests_fn

    def _defaultMergeRequestFn(self, req1, req2):
        return req1.canBeMergedWith(req2)

    @defer.deferredGenerator
    def _mergeRequests(self, breq, unclaimed_requests, mergeRequests_fn):
        """Use C{mergeRequests_fn} to merge C{breq} against
        C{unclaimed_requests}, where both are build request dictionaries"""
        # short circuit if there is no merging to do
        if not mergeRequests_fn or len(unclaimed_requests) == 1:
            yield [ breq ]
            return

        # we'll need BuildRequest objects, so get those first
        wfd = defer.waitForDeferred(
            defer.gatherResults(
                [ self._brdictToBuildRequest(brdict)
                  for brdict in unclaimed_requests ]))
        yield wfd
        unclaimed_request_objects = wfd.getResult()
        breq_object = unclaimed_request_objects.pop(
                unclaimed_requests.index(breq))

        # gather the mergeable requests
        merged_request_objects = [breq_object]
        for other_breq_object in unclaimed_request_objects:
            wfd = defer.waitForDeferred(
                defer.maybeDeferred(lambda :
                    mergeRequests_fn(self, breq_object, other_breq_object)))
            yield wfd
            if wfd.getResult():
                merged_request_objects.append(other_breq_object)

        # convert them back to brdicts and return
        merged_requests = [ br.brdict for br in merged_request_objects ]
        yield merged_requests

    def _brdictToBuildRequest(self, brdict):
        """
        Convert a build request dictionary to a L{buildrequest.BuildRequest}
        object, caching the result in the dictionary itself.  The resulting
        buildrequest will have a C{brdict} attribute pointing back to this
        dictionary.

        Note that this does not perform any locking - be careful that it is
        only called once at a time for each build request dictionary.

        @param brdict: dictionary to convert

        @returns: L{buildrequest.BuildRequest} via Deferred
        """
        if 'brobj' in brdict:
            return defer.succeed(brdict['brobj'])
        d = buildrequest.BuildRequest.fromBrdict(self.master, brdict)
        def keep(buildrequest):
            brdict['brobj'] = buildrequest
            buildrequest.brdict = brdict
            return buildrequest
        d.addCallback(keep)
        return d

    def _breakBrdictRefloops(self, requests):
        """Break the reference loops created by L{_brdictToBuildRequest}"""
        for brdict in requests:
            try:
                del brdict['brobj'].brdict
            except KeyError:
                pass


class BuilderControl:
    implements(interfaces.IBuilderControl)

    def __init__(self, builder, master):
        self.original = builder
        self.master = master

    def submitBuildRequest(self, ss, reason, props=None):
        d = ss.getSourceStampId(self.master.master)
        def add_buildset(ssid):
            return self.master.master.addBuildset(
                    builderNames=[self.original.name],
                    ssid=ssid, reason=reason, properties=props)
        d.addCallback(add_buildset)
        def get_brs((bsid,brids)):
            brs = BuildRequestStatus(self.original.name,
                                     brids[self.original.name],
                                     self.master.master.status)
            return brs
        d.addCallback(get_brs)
        return d

    def rebuildBuild(self, bs, reason="<rebuild, no reason given>", extraProperties=None):
        if not bs.isFinished():
            return

        # Make a copy of the properties so as not to modify the original build.
        properties = Properties()
        # Don't include runtime-set properties in a rebuild request
        properties.updateFromPropertiesNoRuntime(bs.getProperties())
        if extraProperties is None:
            properties.updateFromProperties(extraProperties)

        properties_dict = dict((k,(v,s)) for (k,v,s) in properties.asList())
        ss = bs.getSourceStamp(absolute=True)
        d = ss.getSourceStampId(self.master.master)
        def add_buildset(ssid):
            return self.master.master.addBuildset(
                    builderNames=[self.original.name],
                    ssid=ssid, reason=reason, properties=properties_dict)
        d.addCallback(add_buildset)
        return d

    @defer.deferredGenerator
    def getPendingBuildRequestControls(self):
        master = self.original.master
        wfd = defer.waitForDeferred(
            master.db.buildrequests.getBuildRequests(
                buildername=self.original.name,
                claimed=False))
        yield wfd
        brdicts = wfd.getResult()

        # convert those into BuildRequest objects
        buildrequests = [ ]
        for brdict in brdicts:
            wfd = defer.waitForDeferred(
                buildrequest.BuildRequest.fromBrdict(self.master.master,
                                                     brdict))
            yield wfd
            buildrequests.append(wfd.getResult())

        # and return the corresponding control objects
        yield [ buildrequest.BuildRequestControl(self.original, r)
                 for r in buildrequests ]

    def getBuild(self, number):
        return self.original.getBuild(number)

    def ping(self):
        if not self.original.slaves:
            self.original.builder_status.addPointEvent(["ping", "no slave"])
            return defer.succeed(False) # interfaces.NoSlaveError
        dl = []
        for s in self.original.slaves:
            dl.append(s.ping(self.original.builder_status))
        d = defer.DeferredList(dl)
        d.addCallback(self._gatherPingResults)
        return d

    def _gatherPingResults(self, res):
        for ignored,success in res:
            if not success:
                return False
        return True

