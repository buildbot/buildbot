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


from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet import defer
from twisted.application import service

from buildbot.process import metrics
from buildbot.process.buildrequest import BuildRequest
from buildbot.db.buildrequests import AlreadyClaimedError

import random

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
