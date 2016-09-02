# coding=utf-8
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
from buildbot.status.results import RESUME, BEGINNING
from buildbot.db.buildrequests import AlreadyClaimedError, UnsupportedQueueError, Queue
from buildbot.process.builder import Slavepool
from buildbot import util
from buildbot.util import lru

import random

def timerLogFinished(msg, timer):
    log.msg(msg + " started at %s finished at %s elapsed %s" %
            (util.epoch2datetime(timer.started),
             util.epoch2datetime(util.now(timer._reactor)),
             util.formatInterval(util.now(timer._reactor) - timer.started)))
    timer.stop()

def timerLogStart(msg, function_name):
    timer = metrics.Timer(function_name)
    timer.start()
    log.msg(msg + " started at %s" % util.epoch2datetime(timer.started))
    return timer

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
        self.resumeBrdicts = None


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
    def claimBuildRequests(self, breqs):
        brids = [br.id for br in breqs]
        yield self.master.db.buildrequests.claimBuildRequests(brids)
    
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

    def _getBrdictForBuildRequest(self, breq, pendingBrdicts=None):
        # Turn a BuildRequest back into a brdict. This operates from the 
        # cache, which must be set up once via _fetchUnclaimedBrdicts

        if breq is None:
            return None

        if pendingBrdicts is None:
            pendingBrdicts = self.unclaimedBrdicts
        
        brid = breq.id
        for brdict in pendingBrdicts:
            if brid == brdict['brid']:
                return brdict
        return None

    def _removeBuildRequest(self, breq, pendingBrdicts=None):
        # Remove a BuildrRequest object (and its brdict)
        # from the caches

        if breq is None:
            return

        if pendingBrdicts is None:
            pendingBrdicts = self.unclaimedBrdicts
        
        brdict = self._getBrdictForBuildRequest(breq, pendingBrdicts)
        if brdict is not None and brdict in pendingBrdicts:
            pendingBrdicts.remove(brdict)

        if breq.id in self.breqCache:
            del self.breqCache[breq.id]

    def _getUnclaimedBuildRequests(self, pendingBrdicts=None):
        if pendingBrdicts is None:
            pendingBrdicts = self.unclaimedBrdicts
        # Retrieve the list of BuildRequest objects for all unclaimed builds
        return defer.gatherResults([
            self._getBuildRequestForBrdict(brdict)
              for brdict in pendingBrdicts])
            
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
        # By default katana  merges Requests
        if bldr.config.mergeRequests is None:
            bldr.config.mergeRequests = True
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
    def _pickUpSlave(self, slave, breq):

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

        defer.returnValue(slave)
        
    @defer.inlineCallbacks
    def popNextBuild(self):
        nextBuild = (None, None)
        
        while 1:
            
            #  1. pick a build
            breq = yield self._getNextUnclaimedBuildRequest()
            if not breq:
                break

            #  2. pick a slave
            slave = yield self._popNextSlave()
            if not slave:
                break

            # either satisfy this build or we leave it for another day
            self._removeBuildRequest(breq)

            #  3. make sure slave+ is usable for the breq
            slave = yield self._pickUpSlave(slave, breq)

            #  4. done? otherwise we will try another build
            if slave:
                nextBuild = (slave, breq)
                break
        
        defer.returnValue(nextBuild)
        
    @defer.inlineCallbacks
    def mergeRequests(self, breq, pendingBrdicts=None):
        mergedRequests = [breq]

        if pendingBrdicts is None:
            pendingBrdicts = self.unclaimedBrdicts

        # short circuit if there is no merging to do
        if not self.mergeRequestsFn or not pendingBrdicts:
            defer.returnValue(mergedRequests)
            return

        # we'll need BuildRequest objects, so get those first
        unclaimedBreqs = yield self._getUnclaimedBuildRequests(pendingBrdicts)

        # gather the mergeable requests
        for req in unclaimedBreqs:
            canMerge = yield self.mergeRequestsFn(self.bldr, breq, req)
            if canMerge and req.id != breq.id:
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

class KatanaBuildChooser(BasicBuildChooser):

    def __init__(self, builders, master):
        # By default katana  merges Requests
        self.bldr = None
        self.master = master
        self.initializeBreqCache()
        self.builders = builders
        self.initializeBuildRequestQueue()

    def initializeBuildRequestQueue(self):
        self.unclaimedBrdicts = None
        self.resumeBrdicts = None

    def setupNextBuildRequest(self, bldr, breq):
        # by default katana merges buildrequests
        if bldr.config.mergeRequests is None:
            bldr.config.mergeRequests = True

        self.bldr = bldr

        self.nextSlave = self.bldr.config.nextSlave
        if not self.nextSlave:
            self.nextSlave = lambda _,slaves: random.choice(slaves) if slaves else None

        self.preferredSlaves = []
        self.rejectedSlaves = []

        self.mergeRequestsFn = self.bldr.getMergeRequestsFn()

        # katana initialized it from build request distributor
        self.nextBreq = breq

    def initializeBreqCache(self):
        self.breqCache = lru.AsyncLRUCache(BuildRequest.fromBrdict, 6000)
        self.breqCache.fn_uses_key = False

    def cleanupNextBuildRequest(self):
        self.bldr = None
        self.nextBreq = None
        self.nextSlave = None
        self.mergeRequestsFn = None

    @defer.inlineCallbacks
    def claimBuildRequests(self, breqs):
        brids = [br.id for br in breqs]
        if len(breqs) > 1:
            yield self.master.db.buildrequests.mergePendingBuildRequests(brids)
            log.msg("merge pending buildrequest %s with %s " % (brids[0], brids[1:]))
        else:
            yield self.master.db.buildrequests.claimBuildRequests(brids)

    def removeBuildRequest(self, breq):
        # reset the checkMerges in case the breq still in the master cache
        breq.checkMerges = True
        breq.retries = 0
        if self.unclaimedBrdicts and breq.brdict and breq.brdict in self.unclaimedBrdicts:
            self.unclaimedBrdicts.remove(breq.brdict)
        if self.resumeBrdicts and breq.brdict and breq.brdict in self.resumeBrdicts:
            self.resumeBrdicts.remove(breq.brdict)
        self.breqCache.remove(breq.id)

    def removeBuildRequests(self, breqs):
        # Remove a BuildrRequest object (and its brdict)
        # from the caches

        for breq in breqs:
            self.removeBuildRequest(breq)

    def retryBuildRequest(self):
        msg = "Katana failed to process buildrequest.id %s, Katana will retry again" % self.nextBreq.id
        self.nextBreq.retries += 1
        if self.nextBreq.retries > 4:
            msg = "Katana failed to process buildrequest.id %s after %d retries, " \
                  "Katana will retry after the queue is proccessed " % (self.nextBreq.id, self.nextBreq.retries)
            self.removeBuildRequest(self.nextBreq)
        log.msg(msg)

    @defer.inlineCallbacks
    def _getBuildRequestForBrdict(self, brdict):
        # Turn a brdict into a BuildRequest into a brdict. This is useful
        # for API like 'nextBuild', which operate on BuildRequest objects.
        timer = timerLogStart("_getBuildRequestForBrdict starting",
                              function_name="KatanaBuildChooser._getBuildRequestForBrdict")
        breq = yield self.breqCache.get(brdict['brid'], master=self.master, brdict=brdict)
        breq.brdict = brdict
        timerLogFinished(msg="_getBuildRequestForBrdict finished", timer=timer)
        defer.returnValue(breq)

    @defer.inlineCallbacks
    def _getBuildRequestsQueue(self, queue):
        if queue == Queue.unclaimed:
            if self.unclaimedBrdicts is None:
                self.unclaimedBrdicts = yield self.master.db.buildrequests\
                    .getBuildRequestsInQueue(queue=queue)
            defer.returnValue(self.unclaimedBrdicts)
            return

        if queue == Queue.resume:
            if self.resumeBrdicts is None:
                self.resumeBrdicts = yield self.master.db.buildrequests\
                    .getBuildRequestsInQueue(queue=queue)
            defer.returnValue(self.resumeBrdicts)

    # Katana's gets the next priority builder from the DB instead of keeping a local list
    @defer.inlineCallbacks
    def getNextPriorityBuilder(self, queue):
        """
        Finds the next builder that should start running builds
        selecting the one with the higher priority and oldest submitted time.

        it will return None if there are no slaves available for the task.

        @param queue: None will select the higher priority overall pending buids,
        if queue is 'unclaimed' will select only the pending builds and if queue='resume'
        it will select only builds pending to be resume
        @returns: a build request dictionary or None via Deferred
        """
        unavailableBuilderNames = []
        builderSlavepool = {}

        # TODO: For performance reasons we may need to limit the searches but  we need to load test it first
        buildrequestQueue = yield self._getBuildRequestsQueue(queue)

        log.msg("getNextPriorityBuilder found %d buildrequests in the '%s' Queue" % (len(buildrequestQueue), queue))

        for br in buildrequestQueue:
            buildername = br['buildername']

            bldr = self.builders.get(buildername)

            if not bldr:
                log.msg("BuildRequest %d uses unknown builder %s" % (br['brid'], buildername))
                continue

            if not bldr.config:
                log.msg("BuildRequest %d uses builder %s with no configuration" % (br['brid'], buildername))
                continue

            if buildername in unavailableBuilderNames and not bldr.building and br['startbrid'] is None:
                continue

            breq = yield self._getBuildRequestForBrdict(br)

            self.setupNextBuildRequest(bldr, breq)
            if breq.checkMerges and (yield self.mergeCompatibleBuildRequests(breq, queue)):
                continue

            def getSlavepool():
                if queue == Queue.unclaimed:
                    return Slavepool.startSlavenames
                elif queue == Queue.resume and br['slavepool']:
                    return br['slavepool']
                return Slavepool.slavenames

            slavepool = getSlavepool()

            if buildername not in builderSlavepool:
                builderSlavepool[buildername] = bldr.getAvailableSlavesToProcessBuildRequests(slavepool=slavepool)

            if not builderSlavepool[buildername]:
                unavailableBuilderNames.append(buildername)
                log.msg("No idle slaves found in '%s' list to process buildrequest.id %d for builder %s"
                        % (slavepool, br['brid'], buildername))

                continue

            self.slavepool = builderSlavepool[buildername]

            buildRequestShouldUseSelectedSlave = "selected_slave" in br and br["selected_slave"] \
                                                 and br['results'] == BEGINNING and bldr.shouldUseSelectedSlave()

            resumingBuildRequestShouldUseSelectedSlave = "selected_slave" in br and br["selected_slave"] \
                                                         and br['results'] == RESUME \
                                                         and br['slavepool'] != Slavepool.startSlavenames

            if buildRequestShouldUseSelectedSlave or resumingBuildRequestShouldUseSelectedSlave:
                if bldr.slaveIsAvailable(slavename=br["selected_slave"]):
                    defer.returnValue(breq)
                    return

                # slave not available check next br
                continue

            # bldr can start the build on any available slave
            defer.returnValue(breq)
            return

        self.cleanupNextBuildRequest()
        defer.returnValue(None)

    def getSelectedSlaveFromBuildRequest(self, breq):
        """
        Grab the selected slave and return the slave object
        if selected_slave property is not found then returns
        None
        """
        if self.buildRequestHasSelectedSlave(breq):
            for sb in self.bldr.slaves:
                if sb.slave.slave_status.getName() == breq.properties.getProperty("selected_slave"):
                    return sb
        return None

    def buildRequestHasSelectedSlave(self, breq):
        """
        Does the build request have a specified slave?
        """

        return breq.properties.hasProperty("selected_slave")

    @defer.inlineCallbacks
    def buildHasSelectedSlave(self, breq):
        if self.buildRequestHasSelectedSlave(breq):
            slavebuilder = self.getSelectedSlaveFromBuildRequest(breq)

            if not slavebuilder or slavebuilder.isAvailable() is False or slavebuilder not in self.slavepool:
                defer.returnValue(None)
                return

            self.slavepool.remove(slavebuilder)

            canStart = yield self.bldr.canStartWithSlavebuilder(slavebuilder)
            if canStart:
                defer.returnValue(slavebuilder)
                return

            # save as a last resort, just in case we need them later
            if self.rejectedSlaves is not None:
                self.rejectedSlaves.append(slavebuilder)

        defer.returnValue(None)

    @defer.inlineCallbacks
    def fetchPreviouslyMergedBuildRequests(self, breqs, queue):
        brids = [breq.id for breq in breqs]
        brdicts = yield self.master.db.buildrequests.getBuildRequestsInQueue(queue=queue,
                                                                             buildername=self.bldr.name,
                                                                             mergebrids=brids,
                                                                             order=False)
        merged_breqs = yield defer.gatherResults([self._getBuildRequestForBrdict(brdict)
                                                  for brdict in brdicts])
        defer.returnValue(breqs + merged_breqs)

    @defer.inlineCallbacks
    def mergeRequests(self, breq, queue, startbrid=None):
        mergedRequests = [breq]

        sourcestamps = []
        for ss in breq.sources.itervalues():
            sourcestamps.append({'b_codebase': ss.codebase, 'b_revision': ss.revision,
                                 'b_branch': ss.branch, 'b_sourcestampsetid': ss.sourcestampsetid})

        brdicts = yield self.master.db.buildrequests.getBuildRequestsInQueue(queue=queue,
                                                                             buildername=self.bldr.name,
                                                                             sourcestamps=sourcestamps,
                                                                             startbrid=startbrid,
                                                                             order=False)

        for brdict in brdicts:
            req = yield self._getBuildRequestForBrdict(brdict)
            canMerge = yield self.mergeRequestsFn(self.bldr, breq, req)
            if canMerge and req.id != breq.id:
                mergedRequests.append(req)

        defer.returnValue(mergedRequests)

    @defer.inlineCallbacks
    def chooseNextBuildToResume(self):
        slave, breq = yield self.popNextBuildToResume()

        if not slave or not breq:
            defer.returnValue((None, None, None))
            return

        buildnumber = yield self.master.db.builds.getBuildNumberForRequest(breq.id)
        queue = Queue.resume

        newBreqs = yield self.mergeRequests(breq, queue=queue)
        if len(newBreqs) > 1:
            brids = [br.id for br in newBreqs]
            log.msg("merge pending buildrequest to resume %s with %s " % (breq.id, brids[1:]))
            yield self.master.db.buildrequests.mergePendingBuildRequests(brids,
                                                                         artifactbrid=breq.id,
                                                                         queue=queue)

        breqs = yield self.fetchPreviouslyMergedBuildRequests([breq], queue=queue)

        defer.returnValue((slave, buildnumber, breqs))

    @defer.inlineCallbacks
    def chooseNextBuild(self):
        # Return the next build, as a (slave, [breqs]) pair

        slave, breq = yield self.popNextBuild()

        if not slave or not breq:
            defer.returnValue((None, None))
            return

        breqs = yield self.mergeRequests(breq, queue=Queue.unclaimed)

        defer.returnValue((slave, breqs))

    # notify the master that the buildrequests were removed from queue
    def notifyRequestsRemoved(self, buildrequests):
        for br in buildrequests:
            self.removeBuildRequest(br)
            self.master.buildRequestRemoved(br.bsid, br.id, self.bldr.name)

    @defer.inlineCallbacks
    def _completeMergedBuildsets(self, requests):
        # inform the master that we may have completed a number of buildsets
        for br in requests:
            yield self.master.maybeBuildsetComplete(br.bsid)
            # notify the master that the buildrequest was remove from queue
            self.master.buildRequestRemoved(br.bsid, br.id, self.bldr.name)
            self.removeBuildRequest(br)

    @defer.inlineCallbacks
    def mergeBuildingRequests(self, brids, breqs, queue):
        # check only the first br others will be compatible to merge
        for b in self.bldr.building:
            if not b.finished and self.mergeRequestsFn(self.bldr, b.requests[0], breqs[0]):
                try:
                    yield self.master.db.buildrequests.mergeBuildingRequest([b.requests[0]] + breqs,
                                                                            brids,
                                                                            b.build_status.number,
                                                                            queue=queue)

                    if b.finished:
                        log.msg("buildrequest %s finished while merging %s " % (b.requests[0].id, brids))
                        yield self.bldr.finishBuildRequests(brids,
                                                            requests=breqs,
                                                            build=b,
                                                            mergedbrids=[b.requests[0].id]+brids)
                except:
                    raise

                b.requests += breqs
                log.msg("merge brids %s with building request %s " % (brids, b.requests[0].id))
                self.notifyRequestsRemoved(breqs)
                defer.returnValue(b)
                return
        defer.returnValue(None)

    @defer.inlineCallbacks
    def selectSlave(self, breq):
        selected_slave = yield self._popNextSlave()
        #  make sure slave+ is usable for the breq
        slave = yield self._pickUpSlave(selected_slave, breq) if selected_slave else None
        self.logSlaveSelectionStatus(breq, selected_slave, slave)
        defer.returnValue(slave)

    @defer.inlineCallbacks
    def popNextBuildToResume(self):
        nextBuild = (None, None)

        breq = self.nextBreq

        # run the build on a specific slave
        if breq.slavepool and breq.slavepool != Slavepool.startSlavenames and self.buildRequestHasSelectedSlave(breq):
            slavebuilder = yield self.buildHasSelectedSlave(breq)
            if slavebuilder is not None:
                nextBuild = (slavebuilder, breq)

            # if the slave is not available anymore find another high priority builder
            defer.returnValue(nextBuild)
            return

        #  2. pick a slave
        slave = yield self.selectSlave(breq)

        #  3. done? otherwise we will try another build
        if slave:
            nextBuild = (slave, breq)

        defer.returnValue(nextBuild)

    @defer.inlineCallbacks
    def mergeCompatibleBuildRequests(self, breq, queue):
        timer = timerLogStart("mergeCompatibleBuildRequests starting",
                              function_name="KatanaBuildChooser.mergeCompatibleBuildRequests")

        def mergeCheckFinished():
            breq.checkMerges = False
            timerLogFinished(msg="mergeCompatibleBuildRequests finished", timer=timer)

        # 2. try merge this build with a compatible running build
        if breq and self.bldr.building:
            breqs = yield self.mergeRequests(breq, queue=queue)
            totalBreqs = yield self.fetchPreviouslyMergedBuildRequests(breqs, queue=queue)
            brids = [br.id for br in totalBreqs]

            try:
                build = yield self.mergeBuildingRequests(brids, totalBreqs, queue=queue)
                if build is not None:
                    yield self.bldr.maybeUpdateMergedBuilds(brid=build.requests[0].id,
                                                            buildnumber=build.build_status.number,
                                                            brids=brids)
                    mergeCheckFinished()
                    defer.returnValue(True)
                    return

            except Exception:
                log.msg(Failure(), "from _getBuildRequest for builder '%s'" % self.bldr.name)
                log.msg("mergeBuildingRequests skipped: merge brids %s with building request failed" % brids)

        # 3. try merge with compatible finished build in the same chain
        if breq and breq.buildChainID and breq.buildChainID != breq.id:
            #check if can be merged with finished build
            finished_br = yield self.master.db.buildrequests\
                .findCompatibleFinishedBuildRequest(self.bldr.name, breq.buildChainID)

            finishedBreq = yield self._getBuildRequestForBrdict(finished_br) if finished_br else None

            if finishedBreq and self.mergeRequestsFn(self.bldr, finishedBreq, breq):
                # get buildrequest in queue in the same buildchain
                breqs = yield self.mergeRequests(breq, queue=queue, startbrid=breq.buildChainID)
                totalBreqs = yield self.fetchPreviouslyMergedBuildRequests(breqs, queue=queue)
                totalBrids = [br.id for br in totalBreqs]

                try:
                    log.msg("merge finished buildresquest %s with %s" % (finished_br, totalBrids))
                    yield self.master.db.buildrequests.mergeFinishedBuildRequest(finished_br,
                                                                                 totalBrids,
                                                                                 queue=queue)
                    yield self._completeMergedBuildsets(totalBreqs)

                    buildnumber = yield self.master.db.builds.getBuildNumberForRequest(finished_br['brid'])
                    yield self.bldr.maybeUpdateMergedBuilds(brid=finished_br['brid'],
                                                            buildnumber=buildnumber,
                                                            brids=totalBrids)
                    mergeCheckFinished()
                    defer.returnValue(True)
                    return

                except Exception:
                    log.msg(Failure(), "from _getBuildRequest for builder '%s'" % self.bldr.name)
                    log.msg("mergeFinishedBuildRequest skipped: merge finished buildresquest %s with %s failed"
                            % (finished_br, totalBrids))

        mergeCheckFinished()
        defer.returnValue(False)

    def logSlaveSelectionStatus(self, breq, selected_slave, usable_slave):
        if selected_slave and selected_slave.slave and not usable_slave:
            log.msg("KatanaBuildChooser selected slave %s but is not usable for the buildrequest: %s buildername: %s" %
                    (selected_slave.slave.slavename, breq.id, breq.buildername))

        if (not selected_slave or not selected_slave.slave) and not usable_slave:
            log.msg("KatanaBuildChooser failed to select slave for buildrequest: %s buildername: %s" %
                    (breq.id, breq.buildername))

    @defer.inlineCallbacks
    def popNextBuild(self):
        nextBuild = (None, None)

        breq = self.nextBreq

        # check if should run the build on a specific slave
        if self.bldr.shouldUseSelectedSlave() and self.buildRequestHasSelectedSlave(breq):
            slavebuilder = yield self.buildHasSelectedSlave(breq)
            if slavebuilder is not None:
                nextBuild = (slavebuilder, breq)

            # if the slave is not available anymore find another high priority builder
            defer.returnValue(nextBuild)
            return

        #  2. pick a slave
        slave = yield self.selectSlave(breq)

        #  3. done? otherwise we will try another build
        if slave:
            nextBuild = (slave, breq)

        defer.returnValue(nextBuild)


# Buildbot's default BuildRequestDistributor with the default BasicBuildChooser
# from the eight branch
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

    def _maybeStartBuildsOn(self, new_builders):
        new_builders = set(new_builders)
        existing_pending = set(self._pending_builders)

        # if we won't add any builders, there's nothing to do
        if new_builders < existing_pending:
            return defer.succeed(None)

        # reset the list of pending builders
        @defer.inlineCallbacks
        def resetPendingBuildersList(new_builders):
            try:
                # re-fetch existing_pending, in case it has changed
                # while acquiring the lock
                existing_pending = set(self._pending_builders)

                # then sort the new, expanded set of builders
                self._pending_builders = \
                    yield self._sortBuilders(
                        list(existing_pending | new_builders))

                # start the activity loop, if we aren't already
                # working on that.
                if not self.active:
                    self._activityLoop()
            except Exception:
                log.err(Failure(),
                        "while attempting to start builds on %s" % self.name)

        return self.pending_builders_lock.run(
            resetPendingBuildersList, new_builders)

    @defer.inlineCallbacks
    def _defaultSorter(self, master, builders):
        timer = metrics.Timer("BuildRequestDistributor._defaultSorter()")
        timer.start()
        # perform an asynchronous schwarzian transform, transforming None
        # into sys.maxint so that it sorts to the end

        def xform(bldr):
            d = defer.maybeDeferred(lambda:
                                    bldr.getOldestRequestTime())
            d.addCallback(lambda time:
                          (((time is None) and None or time), bldr))
            return d
        xformed = yield defer.gatherResults(
            [xform(bldr) for bldr in builders])

        # sort the transformed list synchronously, comparing None to the end of
        # the list
        def nonecmp(a, b):
            if a[0] is None:
                return 1
            if b[0] is None:
                return -1
            return cmp(a, b)
        xformed.sort(cmp=nonecmp)

        # and reverse the transform
        rv = [xf[1] for xf in xformed]
        timer.stop()
        defer.returnValue(rv)

    @defer.inlineCallbacks
    def _sortBuilders(self, buildernames):
        timer = metrics.Timer("BuildRequestDistributor._sortBuilders()")
        timer.start()
        # note that this takes and returns a list of builder names

        # convert builder names to builders
        builders_dict = self.botmaster.builders
        builders = [builders_dict.get(n)
                    for n in buildernames
                    if n in builders_dict]

        # find a sorting function
        sorter = self.master.config.prioritizeBuilders
        if not sorter:
            sorter = self._defaultSorter

        # run it
        try:
            builders = yield defer.maybeDeferred(lambda:
                                                 sorter(self.master, builders))
        except Exception:
            log.err(Failure(), "prioritizing builders; order unspecified")

        # and return the names
        rv = [b.name for b in builders]
        timer.stop()
        defer.returnValue(rv)

    @defer.inlineCallbacks
    def _activityLoop(self):
        self.active = True

        timer = metrics.Timer('BuildRequestDistributor._activityLoop()')
        timer.start()

        while True:
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

            # get the actual builder object
            bldr = self.botmaster.builders.get(bldr_name)
            try:
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

        while True:
            slave, breqs = yield bc.chooseNextBuild()
            if not slave or not breqs:
                break

            # claim brid's
            brids = [br.id for br in breqs]
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
        pass  # pragma: no cover


class KatanaBuildRequestDistributor(service.Service):
    """
    Special-purpose class to handle distributing build requests to builders by
    calling their C{_maybeStartOrResumeBuildsOn} method.

    KatanaBuildRequestDistributor is not maintaining a list but fetching the builder with highest priority
    and lowest submitted time from the db, it also process one request at a time per builder
     including processing all possible merges.
    """

    # todo read from configuration if want to use buildbot's or katana build chooser
    BuildChooser = KatanaBuildChooser
    
    def __init__(self, botmaster):
        self.botmaster = botmaster
        self.master = botmaster.master

        # sorted list of names of builders that need their maybeStartBuild
        # method invoked.
        self.activity_lock = defer.DeferredLock()
        self.active = False
        self._pendingMSBOCalls = []
        self.check_new_builds = True
        self.check_resume_builds = True
        self.katanaBuildChooser = self.createBuildChooser(builders=self.botmaster.builders, master=self.master)

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
        if not self.running or not self.master.config.builders:
            return

        d = self._maybeStartOrResumeBuildsOn(new_builders)
        self._pendingMSBOCalls.append(d)
        @d.addBoth
        def remove(x):
            self._pendingMSBOCalls.remove(d)
            return x
        d.addErrback(log.err, "while starting or resuming builds on %s" % (new_builders,))

    @defer.inlineCallbacks
    def _maybeStartOrResumeBuildsOn(self, new_builders):
        # start the activity loop, if we aren't already
        #  working on that.
        if not self.activity_lock.waiting:
            yield self.activity_lock.acquire()
            self._checkBuildRequests()
            self.activity_lock.release()
            if not self.active:
                yield self._procesBuildRequestsActivityLoop()

    def _checkBuildRequests(self):
        self.check_new_builds = True
        self.check_resume_builds = True
        self.katanaBuildChooser.initializeBuildRequestQueue()

    @defer.inlineCallbacks
    def _selectNextBuildRequest(self, queue, asyncFunc):
        # get the actual builder object that should start running new builds
        timer = timerLogStart(msg="_selectNextBuildRequest starting _getNextPriorityBuilder queue %s" % queue,
                              function_name="KatanaBuildRequestDistributor._selectNextBuildRequest()")
        breq = yield self.katanaBuildChooser.getNextPriorityBuilder(queue=queue)
        timerLogFinished(msg="_selectNextBuildRequest _getNextPriorityBuilder finished", timer=timer)

        if breq is None:
            defer.returnValue(breq)
            return

        try:
            log.msg("_nextBuilder:  %s, brid %s, queue: %s" % (breq.buildername, breq.id, queue))
            timer = timerLogStart(msg="starting asyncFunc queue %s" % queue,
                                   function_name="KatanaBuildRequestDistributor._selectNextBuildRequest()")

            if not (yield asyncFunc()):
                self.katanaBuildChooser.retryBuildRequest()

        except Exception:
            self.katanaBuildChooser.initializeBuildRequestQueue()
            log.err(Failure(), "from _selectNextBuildRequest for builder '%s' queue '%s'" % (breq.buildername, queue))

        timerLogFinished(msg="asyncFunc finished", timer=timer)

        defer.returnValue(breq)

    @defer.inlineCallbacks
    def _procesBuildRequestsActivityLoop(self):
        self.active = True

        timer = timerLogStart(msg="_procesBuildRequestsActivityLoop ",
                                   function_name="KatanaBuildRequestDistributor._procesBuildRequestsActivityLoop()")

        while 1:
            yield self.activity_lock.acquire()

            self.active = self.running and (self.check_new_builds or self.check_resume_builds)
            # bail out if we shouldn't keep looping
            if not self.active:
                self.activity_lock.release()
                break

            # continue checking new builds if we have pending builders
            if self.check_new_builds:
                nextBuilder = yield self._selectNextBuildRequest(queue=Queue.unclaimed,
                                                                 asyncFunc=self._maybeStartBuildsOnBuilder)
                self.check_new_builds = nextBuilder is not None

            # continue checking resume builds if we have pending builders to resume
            if  self.check_resume_builds:
                nextResumeBuilder = yield self._selectNextBuildRequest(queue=Queue.resume,
                                                                       asyncFunc=self._maybeResumeBuildsOnBuilder)
                self.check_resume_builds = nextResumeBuilder is not None

            self.activity_lock.release()

        timerLogFinished(msg="KatanaBuildRequestDistributor._procesBuildRequestsActivityLoop finished", timer=timer)
        self.katanaBuildChooser.initializeBreqCache()
        self._quiet()

    def logResumeOrStartBuildStatus(self, msg, slave, breqs):
        if len(breqs) > 0:
            log.msg(" %s for buildername %s using slave %s buildrequest id %d priority %d submittedAt %s buildsetid %d" %
                    (msg, breqs[0].buildername, slave, breqs[0].id, breqs[0].priority,
                     util.epoch2datetime(breqs[0].submittedAt),
                     breqs[0].bsid))

    @defer.inlineCallbacks
    def _maybeResumeBuildsOnBuilder(self):
        slave, buildnumber, breqs = yield self.katanaBuildChooser.chooseNextBuildToResume()

        if not slave or not breqs:
            defer.returnValue(False)
            return

        brids = [br.id for br in breqs]
        yield self.master.db.buildrequests.updateBuildRequests(brids, results=BEGINNING)

        buildStarted = yield self.katanaBuildChooser.bldr.maybeResumeBuild(slave, buildnumber, breqs)

        msg = "_maybeResumeBuildOnBuilder is resuming build"

        if not buildStarted:
            yield self.master.db.buildrequests.updateBuildRequests(brids, results=RESUME)
            self.botmaster.maybeStartBuildsForBuilder(self.katanaBuildChooser.bldr.name)
            msg = "_maybeResumeBuildOnBuilder could not resume build"
        else:
            self.katanaBuildChooser.removeBuildRequests(breqs)

        self.logResumeOrStartBuildStatus(msg, slave, breqs)
        defer.returnValue(buildStarted)

    @defer.inlineCallbacks
    def _maybeStartBuildsOnBuilder(self):
        slave, breqs = yield self.katanaBuildChooser.chooseNextBuild()

        if not slave or not breqs:
            defer.returnValue(False)
            return

        # claim brid's
        brids = [br.id for br in breqs]
        yield self.katanaBuildChooser.claimBuildRequests(breqs)

        buildStarted = yield self.katanaBuildChooser.bldr.maybeStartBuild(slave, breqs)

        msg = "_maybeStartNewBuildsOnBuilder is starting build"

        if not buildStarted:
            yield self.master.db.buildrequests.unclaimBuildRequests(brids)
            # and try starting builds again.  If we still have a working slave,
            # then this may re-claim the same buildrequests
            self.botmaster.maybeStartBuildsForBuilder(self.katanaBuildChooser.bldr.name)
            msg = "_maybeStartNewBuildsOnBuilder could not start build"
        else:
            self.katanaBuildChooser.removeBuildRequests(breqs)

        self.logResumeOrStartBuildStatus(msg, slave, breqs)
        defer.returnValue(buildStarted)

    def createBuildChooser(self, builders, master):
        # just instantiate the build chooser requested
        return self.BuildChooser(builders, master)
            
    def _quiet(self):
        # shim for tests
        pass # pragma: no cover
