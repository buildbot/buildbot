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


from twisted.python import log, reflect
from twisted.python.failure import Failure
from twisted.internet import defer, reactor
from twisted.spread import pb
from twisted.application import service

from buildbot.process.builder import Builder
from buildbot import interfaces, locks, config, util
from buildbot.process import metrics
from buildbot.process.buildrequest import BuildRequest
from buildbot.db.buildrequests import AlreadyClaimedError

import random

class BotMaster(config.ReconfigurableServiceMixin, service.MultiService):

    """This is the master-side service which manages remote buildbot slaves.
    It provides them with BuildSlaves, and distributes build requests to
    them."""

    debug = 0

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName("botmaster")
        self.master = master

        self.builders = {}
        self.builderNames = []
        # builders maps Builder names to instances of bb.p.builder.Builder,
        # which is the master-side object that defines and controls a build.

        # self.slaves contains a ready BuildSlave instance for each
        # potential buildslave, i.e. all the ones listed in the config file.
        # If the slave is connected, self.slaves[slavename].slave will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        self.slaves = {} # maps slavename to BuildSlave
        self.watchers = {}

        # self.locks holds the real Lock instances
        self.locks = {}

        # self.mergeRequests is the callable override for merging build
        # requests
        self.mergeRequests = None

        self.shuttingDown = False

        self.lastSlavePortnum = None

        # subscription to new build requests
        self.buildrequest_sub = None

        # a distributor for incoming build requests; see below
        self.brd = BuildRequestDistributor(self)
        self.brd.setServiceParent(self)

    def cleanShutdown(self, _reactor=reactor):
        """Shut down the entire process, once all currently-running builds are
        complete."""
        if self.shuttingDown:
            return
        log.msg("Initiating clean shutdown")
        self.shuttingDown = True

        # first, stop the distributor; this will finish any ongoing scheduling
        # operations before firing
        d = self.brd.stopService()

        # then wait for all builds to finish
        def wait(_):
            l = []
            for builder in self.builders.values():
                for build in builder.builder_status.getCurrentBuilds():
                    l.append(build.waitUntilFinished())
            if len(l) == 0:
                log.msg("No running jobs, starting shutdown immediately")
            else:
                log.msg("Waiting for %i build(s) to finish" % len(l))
                return defer.DeferredList(l)
        d.addCallback(wait)

        # Finally, shut the whole process down
        def shutdown(ign):
            # Double check that we're still supposed to be shutting down
            # The shutdown may have been cancelled!
            if self.shuttingDown:
                # Check that there really aren't any running builds
                for builder in self.builders.values():
                    n = len(builder.builder_status.getCurrentBuilds())
                    if n > 0:
                        log.msg("Not shutting down, builder %s has %i builds running" % (builder, n))
                        log.msg("Trying shutdown sequence again")
                        self.shuttingDown = False
                        self.cleanShutdown()
                        return
                log.msg("Stopping reactor")
                _reactor.stop()
            else:
                self.brd.startService()
        d.addCallback(shutdown)
        d.addErrback(log.err, 'while processing cleanShutdown')

    def cancelCleanShutdown(self):
        """Cancel a clean shutdown that is already in progress, if any"""
        if not self.shuttingDown:
            return
        log.msg("Cancelling clean shutdown")
        self.shuttingDown = False

    @metrics.countMethod('BotMaster.slaveLost()')
    def slaveLost(self, bot):
        metrics.MetricCountEvent.log("BotMaster.attached_slaves", -1)
        for name, b in self.builders.items():
            if bot.slavename in b.config.slavenames:
                b.detached(bot)

    @metrics.countMethod('BotMaster.getBuildersForSlave()')
    def getBuildersForSlave(self, slavename):
        return [ b for b in self.builders.values()
                 if slavename in b.config.slavenames ]

    def getBuildernames(self):
        return self.builderNames

    def getBuilders(self):
        return self.builders.values()

    def startService(self):
        def buildRequestAdded(notif):
            self.maybeStartBuildsForBuilder(notif['buildername'])
        self.buildrequest_sub = \
            self.master.subscribeToBuildRequests(buildRequestAdded)
        service.MultiService.startService(self)

    @defer.inlineCallbacks
    def reconfigService(self, new_config):
        timer = metrics.Timer("BotMaster.reconfigService")
        timer.start()

        # reconfigure slaves
        yield self.reconfigServiceSlaves(new_config)

        # reconfigure builders
        yield self.reconfigServiceBuilders(new_config)

        # call up
        yield config.ReconfigurableServiceMixin.reconfigService(self,
                                                    new_config)

        # try to start a build for every builder; this is necessary at master
        # startup, and a good idea in any other case
        self.maybeStartBuildsForAllBuilders()

        timer.stop()


    @defer.inlineCallbacks
    def reconfigServiceSlaves(self, new_config):

        timer = metrics.Timer("BotMaster.reconfigServiceSlaves")
        timer.start()

        # arrange slaves by name
        old_by_name = dict([ (s.slavename, s)
                            for s in list(self)
                            if interfaces.IBuildSlave.providedBy(s) ])
        old_set = set(old_by_name.iterkeys())
        new_by_name = dict([ (s.slavename, s)
                            for s in new_config.slaves ])
        new_set = set(new_by_name.iterkeys())

        # calculate new slaves, by name, and removed slaves
        removed_names, added_names = util.diffSets(old_set, new_set)

        # find any slaves for which the fully qualified class name has
        # changed, and treat those as an add and remove
        for n in old_set & new_set:
            old = old_by_name[n]
            new = new_by_name[n]
            # detect changed class name
            if reflect.qual(old.__class__) != reflect.qual(new.__class__):
                removed_names.add(n)
                added_names.add(n)

        if removed_names or added_names:
            log.msg("adding %d new slaves, removing %d" %
                    (len(added_names), len(removed_names)))

            for n in removed_names:
                slave = old_by_name[n]

                del self.slaves[n]
                slave.master = None
                slave.botmaster = None

                yield defer.maybeDeferred(lambda :
                        slave.disownServiceParent())

            for n in added_names:
                slave = new_by_name[n]
                slave.setServiceParent(self)
                self.slaves[n] = slave

        metrics.MetricCountEvent.log("num_slaves",
                len(self.slaves), absolute=True)

        timer.stop()


    @defer.inlineCallbacks
    def reconfigServiceBuilders(self, new_config):

        timer = metrics.Timer("BotMaster.reconfigServiceBuilders")
        timer.start()

        # arrange builders by name
        old_by_name = dict([ (b.name, b)
                            for b in list(self)
                            if isinstance(b, Builder) ])
        old_set = set(old_by_name.iterkeys())
        new_by_name = dict([ (bc.name, bc)
                            for bc in new_config.builders ])
        new_set = set(new_by_name.iterkeys())

        # calculate new builders, by name, and removed builders
        removed_names, added_names = util.diffSets(old_set, new_set)

        if removed_names or added_names:
            log.msg("adding %d new builders, removing %d" %
                    (len(added_names), len(removed_names)))

            for n in removed_names:
                builder = old_by_name[n]

                del self.builders[n]
                builder.master = None
                builder.botmaster = None

                yield defer.maybeDeferred(lambda :
                        builder.disownServiceParent())

            for n in added_names:
                builder = Builder(n)
                self.builders[n] = builder

                builder.botmaster = self
                builder.master = self.master
                builder.setServiceParent(self)

        self.builderNames = self.builders.keys()

        metrics.MetricCountEvent.log("num_builders",
                len(self.builders), absolute=True)

        timer.stop()


    def stopService(self):
        if self.buildrequest_sub:
            self.buildrequest_sub.unsubscribe()
            self.buildrequest_sub = None
        for b in self.builders.values():
            b.builder_status.addPointEvent(["master", "shutdown"])
            b.builder_status.saveYourself()
        return service.MultiService.stopService(self)

    def getLockByID(self, lockid):
        """Convert a Lock identifier into an actual Lock instance.
        @param lockid: a locks.MasterLock or locks.SlaveLock instance
        @return: a locks.RealMasterLock or locks.RealSlaveLock instance
        """
        assert isinstance(lockid, (locks.MasterLock, locks.SlaveLock))
        if not lockid in self.locks:
            self.locks[lockid] = lockid.lockClass(lockid)
        # if the master.cfg file has changed maxCount= on the lock, the next
        # time a build is started, they'll get a new RealLock instance. Note
        # that this requires that MasterLock and SlaveLock (marker) instances
        # be hashable and that they should compare properly.
        return self.locks[lockid]

    def getLockFromLockAccess(self, access):
        # Convert a lock-access object into an actual Lock instance.
        if not isinstance(access, locks.LockAccess):
            # Buildbot 0.7.7 compability: user did not specify access
            access = access.defaultAccess()
        lock = self.getLockByID(access.lockid)
        return lock

    def maybeStartBuildsForBuilder(self, buildername):
        """
        Call this when something suggests that a particular builder may now
        be available to start a build.

        @param buildername: the name of the builder
        """
        self.brd.maybeStartBuildsOn([buildername])

    def maybeStartBuildsForSlave(self, slave_name):
        """
        Call this when something suggests that a particular slave may now be
        available to start a build.

        @param slave_name: the name of the slave
        """
        builders = self.getBuildersForSlave(slave_name)
        self.brd.maybeStartBuildsOn([ b.name for b in builders ])

    def maybeStartBuildsForAllBuilders(self):
        """
        Call this when something suggests that this would be a good time to 
        start some builds, but nothing more specific.
        """
        self.brd.maybeStartBuildsOn(self.builderNames)


class BuildChooserBase(object):
    #
    # WARNING: This API is experimental and in active development. 
    #
    # This internal object selects a new build+slave pair. It acts as a 
    # generator, initializing its state on creation and offering up new
    # pairs until exhaustion. The object can be destroyed at any time
    # (eg, before the list exhausts), and can be "restarted" by abandoning 
    # an old instance and creating a new one.
    #
    # The entry point is:
    #    * bc.chooseNextBuild() - get the next (slave, [breqs]) or (None, None)
    #
    # The default implementation of this class implements a default
    # chooseNextBuild() that delegates out to two other functions:
    #   * bc.popNextBuild() - get the next (slave, breq) pair
    #   * bc.mergeRequests(breq) - perform a merge for this breq and return
    #       the list of breqs consumed by the merge (including breq itself)

    def __init__(self, bldr, master):
        self.bldr = bldr
        self.master = master
        self.breqCache = {}
        self.unclaimedBrdicts = None

    @defer.inlineCallbacks
    def chooseNextBuild(self):
        # Return the next build, as a (slave, [breqs]) pair

        slave, breq = yield self.popNextBuild()
        if not slave or not breq:
            defer.returnValue((None, None))
            return
        
        breqs = yield self.mergeRequests(breq)
        for b in breqs:
                self._removeBuildRequest(b)
                
        defer.returnValue((slave, breqs))
    

    # Must be implemented by subclass
    def popNextBuild(self):
        # Pick the next (slave, breq) pair; note this is pre-merge, so
        # it's just one breq
        raise NotImplementedError("Subclasses must implement this!")
    
    # Must be implemented by subclass
    def mergeRequests(self, breq):
        # Merge the chosen breq with any other breqs that are compatible
        # Returns a list of the breqs chosen (and should include the
        # original breq as well!)
        raise NotImplementedError("Subclasses must implement this!")
    

    # - Helper functions that are generally useful to all subclasses -
    
    @defer.inlineCallbacks
    def _fetchUnclaimedBrdicts(self):
        # Sets up a cache of all the unclaimed brdicts. The cache is
        # saved at self.unclaimedBrdicts cache. If the cache already 
        # exists, this function does nothing. If a refetch is desired, set 
        # the self.unclaimedBrdicts to None before calling."""
        
        if self.unclaimedBrdicts is None:
            brdicts = yield self.master.db.buildrequests.getBuildRequests(
                        buildername=self.bldr.name, claimed=False)         
            # sort by submitted_at, so the first is the oldest
            brdicts.sort(key=lambda brd : brd['submitted_at'])
            self.unclaimedBrdicts = brdicts
        defer.returnValue(self.unclaimedBrdicts)
    
    @defer.inlineCallbacks
    def _getBuildRequestForBrdict(self, brdict):
        # Turn a brdict into a BuildRequest into a brdict. This is useful 
        # for API like 'nextBuild', which operate on BuildRequest objects.

        breq = self.breqCache.get(brdict['brid'])
        if not breq:
            breq = yield BuildRequest.fromBrdict(self.master, brdict)
            if breq:
                self.breqCache[brdict['brid']] = breq
        defer.returnValue(breq)

    def _getBrdictForBuildRequest(self, breq):
        # Turn a BuildRequest back into a brdict. This operates from the 
        # cache, which must be set up once via _fetchUnclaimedBrdicts

        if breq is None:
            return None
        
        brid = breq.id
        for brdict in self.unclaimedBrdicts:
            if brid == brdict['brid']:
                return brdict
        return None

    def _removeBuildRequest(self, breq):
        # Remove a BuildrRequest object (and its brdict)
        # from the caches

        if breq is None:
            return
        
        brdict = self._getBrdictForBuildRequest(breq)
        if brdict is not None:
            self.unclaimedBrdicts.remove(brdict)

        if breq.id in self.breqCache:
            del self.breqCache[breq.id]

    def _getUnclaimedBuildRequests(self):
        # Retrieve the list of BuildRequest objects for all unclaimed builds
        return defer.gatherResults([
            self._getBuildRequestForBrdict(brdict)
              for brdict in self.unclaimedBrdicts ])
            
class BasicBuildChooser(BuildChooserBase):
    # BasicBuildChooser generates build pairs via the configuration points:
    #   * config.nextSlave  (or random.choice if not set)
    #   * config.nextBuild  (or "pop top" if not set)
    #
    # For N slaves, this will call nextSlave at most N times. If nextSlave
    # returns a slave that cannot satisfy the build chosen by nextBuild,
    # it will search for a slave that can satisfy the build. If one is found,
    # the slaves that cannot be used are "recycled" back into a list
    # to be tried, in order, for the next chosen build. 
    #
    # There are two tests performed on the slave:
    #   * can the slave start a generic build for the Builder?
    #   * if so, can the slave start the chosen build on the Builder?
    # Slaves that cannot meet the first criterion are saved into the 
    # self.rejectedSlaves list and will be used as a last resort. An example
    # of this test is whether the slave can grab the Builder's locks. 
    #
    # If all slaves fail the first test, then the algorithm will assign the
    # slaves in the order originally generated. By setting self.rejectedSlaves
    # to None, the behavior will instead refuse to ever assign to a slave that
    # fails the generic test.

    def __init__(self, bldr, master):
        BuildChooserBase.__init__(self, bldr, master)

        self.nextSlave = self.bldr.config.nextSlave
        if not self.nextSlave:
            self.nextSlave = lambda _,slaves: random.choice(slaves) if slaves else None
            
        self.slavepool = self.bldr.getAvailableSlaves()

        # Pick slaves one at a time from the pool, and if the Builder says 
        # they're usable (eg, locks can be satisfied), then prefer those slaves; 
        # otherwise they go in the 'last resort' bucket, and we'll use them if 
        # we need to. (Setting rejectedSlaves to None disables that feature)
        self.preferredSlaves = []
        self.rejectedSlaves = []

        self.nextBuild = self.bldr.config.nextBuild
        
        self.mergeRequestsFn = self.bldr.getMergeRequestsFn()
        
    @defer.inlineCallbacks
    def popNextBuild(self):
        nextBuild = (None, None)
        
        while 1:
            #  1. pick a slave
            slave = yield self._popNextSlave()
            if not slave:
                break
            
            #  2. pick a build
            breq = yield self._getNextUnclaimedBuildRequest()
            if not breq:
                break

            # either satisfy this build or we leave it for another day
            self._removeBuildRequest(breq)

            #  3. make sure slave+ is usable for the breq
            recycledSlaves = []
            while slave:
                canStart = yield self.canStartBuild(slave, breq)
                if canStart:
                    break
                # try a different slave
                recycledSlaves.append(slave)
                slave = yield self._popNextSlave()
                
            # recycle the slaves that we didnt use to the head of the queue
            # this helps ensure we run 'nextSlave' only once per slave choice
            if recycledSlaves:    
                self._unpopSlaves(recycledSlaves)
                
            #  4. done? otherwise we will try another build
            if slave:
                nextBuild = (slave, breq)
                break
        
        defer.returnValue(nextBuild)
        
    @defer.inlineCallbacks
    def mergeRequests(self, breq):
        mergedRequests = [ breq ]

        # short circuit if there is no merging to do
        if not self.mergeRequestsFn or not self.unclaimedBrdicts:
            defer.returnValue(mergedRequests)
            return

        # we'll need BuildRequest objects, so get those first
        unclaimedBreqs = yield self._getUnclaimedBuildRequests()

        # gather the mergeable requests
        for req in unclaimedBreqs:
            canMerge = yield self.mergeRequestsFn(self.bldr, breq, req)
            if canMerge:
                mergedRequests.append(req)

        defer.returnValue(mergedRequests)


    @defer.inlineCallbacks
    def _getNextUnclaimedBuildRequest(self):
        # ensure the cache is there
        yield self._fetchUnclaimedBrdicts()
        if not self.unclaimedBrdicts:
            defer.returnValue(None)
            return

        if self.nextBuild:
            # nextBuild expects BuildRequest objects
            breqs = yield self._getUnclaimedBuildRequests()
            try:
                nextBreq = yield self.nextBuild(self.bldr, breqs)
                if nextBreq not in breqs:
                    nextBreq = None
            except Exception:
                nextBreq = None            
        else:
            # otherwise just return the first build
            brdict = self.unclaimedBrdicts[0]
            nextBreq = yield self._getBuildRequestForBrdict(brdict)

        defer.returnValue(nextBreq)

    @defer.inlineCallbacks
    def _popNextSlave(self):
        # use 'preferred' slaves first, if we have some ready
        if self.preferredSlaves:
            slave = self.preferredSlaves.pop(0)
            defer.returnValue(slave)
            return
        
        while self.slavepool:
            try:
                slave = yield self.nextSlave(self.bldr, self.slavepool)
            except Exception:
                slave = None
            
            if not slave or slave not in self.slavepool:
                # bad slave or no slave returned
                break

            self.slavepool.remove(slave)
            
            canStart = yield self.bldr.canStartWithSlavebuilder(slave)
            if canStart:
                defer.returnValue(slave)
                return
            
            # save as a last resort, just in case we need them later
            if self.rejectedSlaves is not None:
                self.rejectedSlaves.append(slave)

        # if we chewed through them all, use as last resort:
        if self.rejectedSlaves:
            slave = self.rejectedSlaves.pop(0)
            defer.returnValue(slave)
            return
        
        defer.returnValue(None)

    def _unpopSlaves(self, slaves):
        # push the slaves back to the front
        self.preferredSlaves[:0] = slaves

    def canStartBuild(self, slave, breq):
        return self.bldr.canStartBuild(slave, breq)


class BuildRequestDistributor(service.Service):
    """
    Special-purpose class to handle distributing build requests to builders by
    calling their C{maybeStartBuild} method.

    This takes account of the C{prioritizeBuilders} configuration, and is
    highly re-entrant; that is, if a new build request arrives while builders
    are still working on the previous build request, then this class will
    correctly re-prioritize invocations of builders' C{maybeStartBuild}
    methods.
    """

    BuildChooser = BasicBuildChooser
    
    def __init__(self, botmaster):
        self.botmaster = botmaster
        self.master = botmaster.master

        # lock to ensure builders are only sorted once at any time
        self.pending_builders_lock = defer.DeferredLock()

        # sorted list of names of builders that need their maybeStartBuild
        # method invoked.
        self._pending_builders = []
        self.activity_lock = defer.DeferredLock()
        self.active = False

        self._pendingMSBOCalls = []

    @defer.inlineCallbacks
    def stopService(self):
        # Lots of stuff happens asynchronously here, so we need to let it all
        # quiesce.  First, let the parent stopService succeed between
        # activities; then the loop will stop calling itself, since
        # self.running is false.
        yield self.activity_lock.run(service.Service.stopService, self)

        # now let any outstanding calls to maybeStartBuildsOn to finish, so
        # they don't get interrupted in mid-stride.  This tends to be
        # particularly painful because it can occur when a generator is gc'd.
        if self._pendingMSBOCalls:
            yield defer.DeferredList(self._pendingMSBOCalls)

    def maybeStartBuildsOn(self, new_builders):
        """
        Try to start any builds that can be started right now.  This function
        returns immediately, and promises to trigger those builders
        eventually.

        @param new_builders: names of new builders that should be given the
        opportunity to check for new requests.
        """
        if not self.running:
            return

        d = self._maybeStartBuildsOn(new_builders)
        self._pendingMSBOCalls.append(d)
        @d.addBoth
        def remove(x):
            self._pendingMSBOCalls.remove(d)
            return x
        d.addErrback(log.err, "while strting builds on %s" % (new_builders,))

    @defer.inlineCallbacks
    def _maybeStartBuildsOn(self, new_builders):
        new_builders = set(new_builders)
        existing_pending = set(self._pending_builders)

        # if we won't add any builders, there's nothing to do
        if new_builders < existing_pending:
            return

        # reset the list of pending builders; this is async, so begin
        # by grabbing a lock
        yield self.pending_builders_lock.acquire()

        try:
            # re-fetch existing_pending, in case it has changed while acquiring
            # the lock
            existing_pending = set(self._pending_builders)

            # then sort the new, expanded set of builders
            self._pending_builders = \
                yield self._sortBuilders(list(existing_pending | new_builders))

            # start the activity loop, if we aren't already working on that.
            if not self.active:
                self._activityLoop()
        except Exception:
            log.err(Failure(),
                    "while attempting to start builds on %s" % self.name)

        # release the lock unconditionally
        self.pending_builders_lock.release()

    @defer.inlineCallbacks
    def _defaultSorter(self, master, builders):
        timer = metrics.Timer("BuildRequestDistributor._defaultSorter()")
        timer.start()
        # perform an asynchronous schwarzian transform, transforming None
        # into sys.maxint so that it sorts to the end
        def xform(bldr):
            d = defer.maybeDeferred(lambda :
                    bldr.getOldestRequestTime())
            d.addCallback(lambda time :
                (((time is None) and None or time),bldr))
            return d
        xformed = yield defer.gatherResults(
                [ xform(bldr) for bldr in builders ])

        # sort the transformed list synchronously, comparing None to the end of
        # the list
        def nonecmp(a,b):
            if a[0] is None: return 1
            if b[0] is None: return -1
            return cmp(a,b)
        xformed.sort(cmp=nonecmp)

        # and reverse the transform
        rv = [ xf[1] for xf in xformed ]
        timer.stop()
        defer.returnValue(rv)

    @defer.inlineCallbacks
    def _sortBuilders(self, buildernames):
        timer = metrics.Timer("BuildRequestDistributor._sortBuilders()")
        timer.start()
        # note that this takes and returns a list of builder names

        # convert builder names to builders
        builders_dict = self.botmaster.builders
        builders = [ builders_dict.get(n)
                     for n in buildernames
                     if n in builders_dict ]

        # find a sorting function
        sorter = self.master.config.prioritizeBuilders
        if not sorter:
            sorter = self._defaultSorter

        # run it
        try:
            builders = yield defer.maybeDeferred(lambda :
                    sorter(self.master, builders))
        except Exception:
            log.msg("Exception prioritizing builders; order unspecified")
            log.err(Failure())

        # and return the names
        rv = [ b.name for b in builders ]
        timer.stop()
        defer.returnValue(rv)

    @defer.inlineCallbacks
    def _activityLoop(self):
        self.active = True

        timer = metrics.Timer('BuildRequestDistributor._activityLoop()')
        timer.start()

        while 1:
            yield self.activity_lock.acquire()

            # lock pending_builders, pop an element from it, and release
            yield self.pending_builders_lock.acquire()

            # bail out if we shouldn't keep looping
            if not self.running or not self._pending_builders:
                self.pending_builders_lock.release()
                self.activity_lock.release()
                break

            bldr_name = self._pending_builders.pop(0)
            self.pending_builders_lock.release()

            try:
                # get the actual builder object
                bldr = self.botmaster.builders.get(bldr_name)
                if bldr:
                    yield self._maybeStartBuildsOnBuilder(bldr) 
            except Exception:
                log.err(Failure(),
                        "from maybeStartBuild for builder '%s'" % (bldr_name,))

            self.activity_lock.release()

        timer.stop()

        self.active = False
        self._quiet()
    
    @defer.inlineCallbacks
    def _maybeStartBuildsOnBuilder(self, bldr):
        # create a chooser to give us our next builds
        # this object is temporary and will go away when we're done
        bc = self.createBuildChooser(bldr, self.master)
    
        while 1:
            slave, breqs = yield bc.chooseNextBuild()
            if not slave or not breqs:
                break
            
            # claim brid's
            brids = [ br.id for br in breqs ]
            try:
                yield self.master.db.buildrequests.claimBuildRequests(brids)
            except AlreadyClaimedError:
                # some brids were already claimed, so start over
                bc = self.createBuildChooser(bldr, self.master)
                continue
            
            buildStarted = yield bldr.maybeStartBuild(slave, breqs)
            
            if not buildStarted:
                yield self.master.db.buildrequests.unclaimBuildRequests(brids)
    
                # and try starting builds again.  If we still have a working slave,
                # then this may re-claim the same buildrequests
                self.botmaster.maybeStartBuildsForBuilder(self.name)
            
    def createBuildChooser(self, bldr, master):
        # just instantiate the build chooser requested
        return self.BuildChooser(bldr, master)
            
    def _quiet(self):
        # shim for tests
        pass # pragma: no cover


class DuplicateSlaveArbitrator(object):
    """Utility class to arbitrate the situation when a new slave connects with
    the name of an existing, connected slave

    @ivar buildslave: L{buildbot.process.slavebuilder.AbstractBuildSlave}
    instance
    @ivar old_remote: L{RemoteReference} to the old slave
    @ivar new_remote: L{RemoteReference} to the new slave
    """
    _reactor = reactor # for testing

    # There are several likely duplicate slave scenarios in practice:
    #
    # 1. two slaves are configured with the same username/password
    #
    # 2. the same slave process believes it is disconnected (due to a network
    # hiccup), and is trying to reconnect
    #
    # For the first case, we want to prevent the two slaves from repeatedly
    # superseding one another (which results in lots of failed builds), so we
    # will prefer the old slave.  However, for the second case we need to
    # detect situations where the old slave is "gone".  Sometimes "gone" means
    # that the TCP/IP connection to it is in a long timeout period (10-20m,
    # depending on the OS configuration), so this can take a while.

    PING_TIMEOUT = 10
    """Timeout for pinging the old slave.  Set this to something quite long, as
    a very busy slave (e.g., one sending a big log chunk) may take a while to
    return a ping.
    """

    def __init__(self, buildslave):
        self.buildslave = buildslave
        self.old_remote = self.buildslave.slave

    def getPerspective(self, mind, slavename):
        self.new_remote = mind
        self.ping_old_slave_done = False
        self.old_slave_connected = True
        self.ping_new_slave_done = False

        old_tport = self.old_remote.broker.transport
        new_tport = self.new_remote.broker.transport
        log.msg("duplicate slave %s; delaying new slave (%s) and pinging old "
                "(%s)" % (self.buildslave.slavename, new_tport.getPeer(),
                          old_tport.getPeer()))

        # delay the new slave until we decide what to do with it
        d = self.new_slave_d = defer.Deferred()

        # Ping the old slave.  If this kills it, then we can allow the new
        # slave to connect.  If this does not kill it, then we disconnect
        # the new slave.
        self.ping_old_slave(new_tport.getPeer())

        # Print a message on the new slave, if possible.
        self.ping_new_slave()

        return d

    def ping_new_slave(self):
        d = defer.maybeDeferred(lambda :
            self.new_remote.callRemote("print", "master already has a "
                        "connection named '%s' - checking its liveness"
                        % self.buildslave.slavename))
        def done(_):
            # failure or success, doesn't matter - the ping is done.
            self.ping_new_slave_done = True
            self.maybe_done()
        d.addBoth(done)

    def ping_old_slave(self, new_peer):
        # set a timer on this ping, in case the network is bad.  TODO: a
        # timeout on the ping itself is not quite what we want.  If there is
        # other data flowing over the PB connection, then we should keep
        # waiting.  Bug #1703
        def timeout():
            self.ping_old_slave_timeout = None
            self.ping_old_slave_timed_out = True
            self.old_slave_connected = False
            self.ping_old_slave_done = True
            self.maybe_done()
        self.ping_old_slave_timeout = self._reactor.callLater(
                                    self.PING_TIMEOUT, timeout)
        self.ping_old_slave_timed_out = False

        # call this in maybeDeferred because callRemote tends to raise
        # exceptions instead of returning Failures
        d = defer.maybeDeferred(lambda :
            self.old_remote.callRemote("print",
                "master got a duplicate connection from %s; keeping this one"
                                        % new_peer))

        def clear_timeout(r):
            if self.ping_old_slave_timeout:
                self.ping_old_slave_timeout.cancel()
                self.ping_old_slave_timeout = None
            return r
        d.addBoth(clear_timeout)

        def old_gone(f):
            if self.ping_old_slave_timed_out:
                return # ignore after timeout
            f.trap(pb.PBConnectionLost, pb.DeadReferenceError)
            log.msg(("connection lost while pinging old slave '%s' - " +
                     "keeping new slave") % self.buildslave.slavename)
            self.old_slave_connected = False
        d.addErrback(old_gone)

        def other_err(f):
            log.err(f, "unexpected error pinging old slave; disconnecting it")
            self.old_slave_connected = False
        d.addErrback(other_err)

        def done(_):
            if self.ping_old_slave_timed_out:
                return # ignore after timeout
            self.ping_old_slave_done = True
            self.maybe_done()
        d.addCallback(done)

    def maybe_done(self):
        if not self.ping_new_slave_done or not self.ping_old_slave_done:
            return

        # both pings are done, so sort out the results
        if self.old_slave_connected:
            self.disconnect_new_slave()
        else:
            self.start_new_slave()

    def start_new_slave(self):
        # just in case
        if not self.new_slave_d: # pragma: ignore
            return

        d = self.new_slave_d
        self.new_slave_d = None

        if self.buildslave.isConnected():
            # we need to wait until the old slave has fully detached, which can
            # take a little while as buffers drain, etc.
            def detached():
                d.callback(self.buildslave)
            self.buildslave.subscribeToDetach(detached)
            self.old_remote.broker.transport.loseConnection()
        else: # pragma: ignore
            # by some unusual timing, it's quite possible that the old slave
            # has disconnected while the arbitration was going on.  In that
            # case, we're already done!
            d.callback(self.buildslave)

    def disconnect_new_slave(self):
        # just in case
        if not self.new_slave_d: # pragma: ignore
            return

        d = self.new_slave_d
        self.new_slave_d = None
        log.msg("rejecting duplicate slave with exception")
        d.errback(Failure(RuntimeError("rejecting duplicate slave")))


