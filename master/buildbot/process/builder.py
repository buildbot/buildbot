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
from twisted.python import log
from twisted.python.failure import Failure
from twisted.spread import pb
from twisted.application import service, internet
from twisted.internet import defer

from buildbot import interfaces, util
from buildbot.status.progress import Expectations
from buildbot.status.builder import RETRY
from buildbot.status.builder import BuildSetStatus
from buildbot.process.properties import Properties
from buildbot.util.eventual import eventually
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
        self.mergeRequests = setup.get('mergeRequests', True)
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

        # add serialized-invocation behavior to maybeStartBuild
        self.maybeStartBuild = util.SerializedInvocation(self.doMaybeStartBuild)

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
        self.db = botmaster.db
        self.master_name = botmaster.master_name
        self.master_incarnation = botmaster.master_incarnation

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

    def triggerNewBuildCheck(self):
        self.botmaster.triggerNewBuildCheck()

    def run(self):
        """Check for work to be done. This should be called any time I might
        be able to start a job:

         - when the Builder is first created
         - when a new job has been added to the [buildrequests] DB table
         - when a slave has connected

        If I have both an available slave and the database contains a
        BuildRequest that I can handle, I will claim the BuildRequest and
        start the build. When the build finishes, I will retire the
        BuildRequest.
        """
        # overall plan:
        #  move .expectations to DB

        # if we're not running, we may still be called from leftovers from
        # a run of the loop, so just ignore the call.
        if not self.running:
            return

        self.run_count += 1

        available_slaves = [sb for sb in self.slaves if sb.isAvailable()]
        if not available_slaves:
            self.updateBigStatus()
            return
        d = self.db.runInteraction(self._claim_buildreqs, available_slaves)
        d.addCallback(self._start_builds)
        return d

    # slave-managers must refresh their claim on a build at least once an
    # hour, less any inter-manager clock skew
    RECLAIM_INTERVAL = 1*3600

    def _claim_buildreqs(self, t, available_slaves):
        # return a dict mapping slave -> (brid,ssid)
        now = util.now()
        old = now - self.RECLAIM_INTERVAL
        requests = self.db.get_unclaimed_buildrequests(self.name, old,
                                                       self.master_name,
                                                       self.master_incarnation,
                                                       t)

        assignments = {}
        while requests and available_slaves:
            sb = self._choose_slave(available_slaves)
            if not sb:
                log.msg("%s: want to start build, but we don't have a remote"
                        % self)
                break
            available_slaves.remove(sb)
            breq = self._choose_build(requests)
            if not breq:
                log.msg("%s: went to start build, but nextBuild said not to"
                        % self)
                break
            requests.remove(breq)
            merged_requests = [breq]
            for other_breq in requests[:]:
                if (self.mergeRequests and
                    self.botmaster.shouldMergeRequests(self, breq, other_breq)
                    ):
                    requests.remove(other_breq)
                    merged_requests.append(other_breq)
            assignments[sb] = merged_requests
            brids = [br.id for br in merged_requests]
            self.db.claim_buildrequests(now, self.master_name,
                                        self.master_incarnation, brids, t)
        return assignments

    def _choose_slave(self, available_slaves):
        # note: this might return None if the nextSlave() function decided to
        # not give us anything
        if self.nextSlave:
            try:
                return self.nextSlave(self, available_slaves)
            except:
                log.msg("Exception choosing next slave")
                log.err(Failure())
            return None
        return random.choice(available_slaves)

    def _choose_build(self, buildable):
        if self.nextBuild:
            try:
                return self.nextBuild(self, buildable)
            except:
                log.msg("Exception choosing next build")
                log.err(Failure())
            return None
        return buildable[0]

    def _start_builds(self, assignments):
        # because _claim_buildreqs runs in a separate thread, we might have
        # lost a slave by this point. We treat that case the same as if we
        # lose the slave right after the build starts: the initial ping
        # fails.
        for (sb, requests) in assignments.items():
            build = self.buildFactory.newBuild(requests)
            build.setBuilder(self)
            build.setLocks(self.locks)
            if len(self.env) > 0:
                build.setSlaveEnvironment(self.env)
            self.startBuild(build, sb)
        self.updateBigStatus()


    def getBuildable(self, limit=None):
        return self.db.runInteractionNow(self._getBuildable, limit)
    def _getBuildable(self, t, limit):
        now = util.now()
        old = now - self.RECLAIM_INTERVAL
        return self.db.get_unclaimed_buildrequests(self.name, old,
                                                   self.master_name,
                                                   self.master_incarnation,
                                                   t,
                                                   limit)

    def getOldestRequestTime(self):
        """Returns the timestamp of the oldest build request for this builder.

        If there are no build requests, None is returned."""
        buildable = self.getBuildable(1)
        if buildable:
            # TODO: this is sorted by priority first, not strictly reqtime
            return buildable[0].getSubmitTime()
        return None

    def cancelBuildRequest(self, brid):
        return self.db.cancel_buildrequests([brid])

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
        try:
            now = util.now()
            brids = set()
            for b in self.building:
                brids.update([br.id for br in b.requests])
            for b in self.old_building:
                brids.update([br.id for br in b.requests])
            self.db.claim_buildrequests(now, self.master_name,
                                        self.master_incarnation, brids)
        except:
            log.msg("Error in reclaimAllBuilds")
            log.err()

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
            self.triggerNewBuildCheck()

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
        elif self.building:
            self.builder_status.setBigState("building")
        else:
            self.builder_status.setBigState("idle")

    def startBuild(self, build, sb):
        """Start a build on the given slave.
        @param build: the L{base.Build} to start
        @param sb: the L{SlaveBuilder} which will host this build

        @return: a Deferred which fires with a
        L{buildbot.interfaces.IBuildControl} that can be used to stop the
        Build, or to access a L{buildbot.interfaces.IBuildStatus} which will
        watch the Build as it runs. """

        self.building.append(build)
        self.updateBigStatus()
        log.msg("starting build %s using slave %s" % (build, sb))
        d = sb.prepare(self.builder_status, build)

        def _prepared(ready):
            # If prepare returns True then it is ready and we start a build
            # If it returns false then we don't start a new build.
            d = defer.succeed(ready)

            if not ready:
                #FIXME: We should perhaps trigger a check to see if there is
                # any other way to schedule the work
                log.msg("slave %s can't build %s after all" % (build, sb))

                # release the slave. This will queue a call to maybeStartBuild, which
                # will fire after other notifyOnDisconnect handlers have marked the
                # slave as disconnected (so we don't try to use it again).
                # sb.buildFinished()

                log.msg("re-queueing the BuildRequest %s" % build)
                self.building.remove(build)
                self._resubmit_buildreqs(build).addErrback(log.err)

                sb.slave.releaseLocks()
                self.triggerNewBuildCheck()

                return d

            def _ping(ign):
                # ping the slave to make sure they're still there. If they've
                # fallen off the map (due to a NAT timeout or something), this
                # will fail in a couple of minutes, depending upon the TCP
                # timeout.
                #
                # TODO: This can unnecessarily suspend the starting of a build, in
                # situations where the slave is live but is pushing lots of data to
                # us in a build.
                log.msg("starting build %s.. pinging the slave %s" % (build, sb))
                return sb.ping()
            d.addCallback(_ping)
            d.addCallback(self._startBuild_1, build, sb)

            return d

        d.addCallback(_prepared)
        return d

    def _startBuild_1(self, res, build, sb):
        if not res:
            return self._startBuildFailed("slave ping failed", build, sb)
        # The buildslave is ready to go. sb.buildStarted() sets its state to
        # BUILDING (so we won't try to use it for any other builds). This
        # gets set back to IDLE by the Build itself when it finishes.
        sb.buildStarted()
        d = sb.remote.callRemote("startBuild")
        d.addCallbacks(self._startBuild_2, self._startBuildFailed,
                       callbackArgs=(build,sb), errbackArgs=(build,sb))
        return d

    def _startBuild_2(self, res, build, sb):
        # create the BuildStatus object that goes with the Build
        bs = self.builder_status.newBuild()

        # start the build. This will first set up the steps, then tell the
        # BuildStatus that it has started, which will announce it to the
        # world (through our BuilderStatus object, which is its parent).
        # Finally it will start the actual build process.
        bids = [self.db.build_started(req.id, bs.number) for req in build.requests]
        d = build.startBuild(bs, self.expectations, sb)
        d.addCallback(self.buildFinished, sb, bids)
        # this shouldn't happen. if it does, the slave will be wedged
        d.addErrback(log.err)
        return build # this is the IBuildControl

    def _startBuildFailed(self, why, build, sb):
        # put the build back on the buildable list
        log.msg("I tried to tell the slave that the build %s started, but "
                "remote_startBuild failed: %s" % (build, why))
        # release the slave. This will queue a call to maybeStartBuild, which
        # will fire after other notifyOnDisconnect handlers have marked the
        # slave as disconnected (so we don't try to use it again).
        sb.buildFinished()

        log.msg("re-queueing the BuildRequest")
        self.building.remove(build)
        self._resubmit_buildreqs(build).addErrback(log.err)

    def setupProperties(self, props):
        props.setProperty("buildername", self.name, "Builder")
        if len(self.properties) > 0:
            for propertyname in self.properties:
                props.setProperty(propertyname, self.properties[propertyname], "Builder")

    def buildFinished(self, build, sb, bids):
        """This is called when the Build has finished (either success or
        failure). Any exceptions during the build are reported with
        results=FAILURE, not with an errback."""

        # by the time we get here, the Build has already released the slave
        # (which queues a call to maybeStartBuild)

        self.db.builds_finished(bids)

        results = build.build_status.getResults()
        self.building.remove(build)
        if results == RETRY:
            self._resubmit_buildreqs(build).addErrback(log.err) # returns Deferred
        else:
            brids = [br.id for br in build.requests]
            self.db.retire_buildrequests(brids, results)

        if sb.slave:
            sb.slave.releaseLocks()

        self.triggerNewBuildCheck()

    def _resubmit_buildreqs(self, build):
        brids = [br.id for br in build.requests]
        return self.db.resubmit_buildrequests(brids)

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

    # maybeStartBuild is called by the botmaster whenever this builder should
    # check for and potentially start new builds.  As an optimization,
    # invocations of this function are collapsed as much as possible while
    # maintaining the invariant that at least one execution of the entire
    # algorithm will occur between the invocation of the method and the firing
    # of its Deferred.  This is done with util.SerializedInvocation; see
    # Builder.__init__, above.

    @defer.deferredGenerator
    def doMaybeStartBuild(self):
        # first, if we're not running, then don't start builds; stopService
        # uses this to ensure that any ongoing doMaybeStartBuild invocations
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
            breq = wfd.getResult()

            if not breq:
                break

            if breq not in unclaimed_requests:
                log.msg(("nextBuild chose a nonexistent request for builder "
                         "'%s'; cannot start build") % self.name)
                break

            # merge the chosen request with any compatible requests in the
            # queue
            wfd = defer.waitForDeferred(
                self._mergeRequests(breq, unclaimed_requests,
                                    mergeRequests_fn))
            yield wfd
            breqs = wfd.getResult()

            # try to claim the build requests
            try:
                wfd = defer.waitForDeferred(
                        self.master.db.buildrequests.claimBuildRequests(
                            [ brdict['brid'] for brdict in breqs ]))
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
            wfd = defer.waitForDeferred(
                    self._startBuildFor(slavebuilder, breqs))
            yield wfd
            wfd.getResult()

            # and finally remove the buildrequests and slavebuilder from the
            # respective queues
            self._breakBrdictRefloops(breqs)
            for breq in breqs:
                unclaimed_requests.remove(breq)
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
            mergeRequests_fn = self.master.mergeRequests
        if mergeRequests_fn is None:
            mergeRequests_fn = True

        # then translate False and True properly
        if mergeRequests_fn is False:
            mergeRequests_fn = None
        elif mergeRequests_fn is True:
            mergeRequests_fn = buildrequest.BuildRequest.canBeMergedWith

        return mergeRequests_fn

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
                    mergeRequests_fn(breq_object, other_breq_object)))
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
        def get_brs(bsid):
            bss = BuildSetStatus(bsid, self.master.master.status,
                                 self.master.master.db)
            brs = bss.getBuildRequests()[0]
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

    def getPendingBuilds(self):
        # return IBuildRequestControl objects
        retval = []
        for r in self.original.getBuildable():
            retval.append(buildrequest.BuildRequestControl(self.original, r))

        return retval

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

