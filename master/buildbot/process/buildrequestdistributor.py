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
from buildbot import util

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
    def _pickUpSlave(self, slave, breq, slavepool=None):

        #  3. make sure slave+ is usable for the breq
        recycledSlaves = []
        while slave:
            canStart = yield self.canStartBuild(slave, breq)
            if canStart:
                break
            # try a different slave
            recycledSlaves.append(slave)
            slave = yield self._popNextSlave(slavepool)

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
    def _popNextSlave(self, slavepool=None):
        # use 'preferred' slaves first, if we have some ready
        if slavepool is None:
            slavepool = self.slavepool

        if self.preferredSlaves:
            slave = self.preferredSlaves.pop(0)
            defer.returnValue(slave)
            return
        
        while slavepool:
            try:
                slave = yield self.nextSlave(self.bldr, slavepool)
            except Exception:
                slave = None
            
            if not slave or slave not in slavepool:
                # bad slave or no slave returned
                break

            slavepool.remove(slave)
            
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

    def __init__(self, bldr, master):
        BasicBuildChooser.__init__(self, bldr, master)
        self.resumeSlavePool = self.bldr.getAvailableSlavesToResume()

    @defer.inlineCallbacks
    def claimBuildRequests(self, breqs):
        brids = [br.id for br in breqs]
        if len(breqs) > 1:
            yield self.master.db.buildrequests.mergePendingBuildRequests(brids)
            log.msg("merge pending buildrequest %s with %s " % (brids[0], brids[1:]))
        else:
            yield self.master.db.buildrequests.claimBuildRequests(brids)

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
    def _chooseBuild(self, buildrequests, useSelectedSlave=True):
        """
        Choose the next build from the given set of build requests (represented
        as dictionaries).  Defaults to returning the first request (earliest
        submitted).

        @param buildrequests: sorted list of build request dictionaries
        @returns: a build request dictionary or None via Deferred
        """
        sorted_requests = sorted(buildrequests, key=lambda br: (-br["priority"], br["submitted_at"]))
        for b in sorted_requests:
            breq = yield self._getBuildRequestForBrdict(b)
            if useSelectedSlave and self.buildRequestHasSelectedSlave(breq):
                selected_slave = self.getSelectedSlaveFromBuildRequest(breq)
                if selected_slave and selected_slave.isAvailable():
                    defer.returnValue(b)
            else:
                defer.returnValue(b)

        defer.returnValue(None)

    @defer.inlineCallbacks
    def _chooseBuildRequest(self, buildrequests, useSelectedSlave=True):
        nextBreq = None

        brdict = yield self._chooseBuild(buildrequests, useSelectedSlave=useSelectedSlave)

        if brdict:
            nextBreq = yield self._getBuildRequestForBrdict(brdict)
        defer.returnValue(nextBreq)

    @defer.inlineCallbacks
    def buildHasSelectedSlave(self, breq, slavepool):
        if self.buildRequestHasSelectedSlave(breq):
            slavebuilder = self.getSelectedSlaveFromBuildRequest(breq)

            if not slavebuilder or slavebuilder.isAvailable() is False or slavebuilder not in slavepool:
                defer.returnValue(None)
                return

            slavepool.remove(slavebuilder)

            canStart = yield self.bldr.canStartWithSlavebuilder(slavebuilder)
            if canStart:
                defer.returnValue(slavebuilder)
                return

            # save as a last resort, just in case we need them later
            if self.rejectedSlaves is not None:
                self.rejectedSlaves.append(slavebuilder)

        defer.returnValue(None)

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
            nextBreq = yield self._chooseBuildRequest(self.unclaimedBrdicts,
                                                      useSelectedSlave=self.bldr.shouldUseSelectedSlave())

        defer.returnValue(nextBreq)

    @defer.inlineCallbacks
    def fetchPreviouslyMergedBuildRequests(self, breqs):
        brids = [breq.id for breq in breqs]
        brdicts = yield self.master.db.buildrequests.getBuildRequests(buildername=self.bldr.name,
                                                                      mergebrids=brids)
        merged_breqs = yield defer.gatherResults([self._getBuildRequestForBrdict(brdict)
                                                  for brdict in brdicts])
        defer.returnValue(breqs + merged_breqs)

    @defer.inlineCallbacks
    def chooseNextBuildToResume(self):
        slave, breq = yield self.popNextBuildToResume()

        if not slave or not breq:
            defer.returnValue((None, None, None))
            return

        buildnumber = yield self.master.db.builds.getBuildNumberForRequest(breq.id)

        newBreqs = yield self.mergeRequests(breq, pendingBrdicts=self.resumeBrdicts)
        if len(newBreqs) > 1:
            brids = [br.id for br in newBreqs]
            log.msg("merge pending buildrequest to resume %s with %s " % (breq.id, brids[1:]))
            yield self.master.db.buildrequests.mergePendingBuildRequests(brids, artifactbrid=breq.id, claim=False)

        breqs = yield self.fetchPreviouslyMergedBuildRequests([breq])
        for b in breqs:
            self._removeBuildRequest(b, self.resumeBrdicts)

        defer.returnValue((slave, buildnumber, breqs))

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

    # notify the master that the buildrequests were removed from queue
    def notifyRequestsRemoved(self, buildrequests):
        for br in buildrequests:
            self.master.buildRequestRemoved(br.bsid, br.id, self.bldr.name)

    @defer.inlineCallbacks
    def mergeBuildingRequests(self, brids, breqs, claim):
        # check only the first br others will be compatible to merge
        for b in self.bldr.building:
            if self.bldr._defaultMergeRequestFn(b.requests[0], breqs[0]):
                try:
                    yield self.master.db.buildrequests.mergeBuildingRequest([b.requests[0]] + breqs,
                                                                            brids,
                                                                            b.build_status.number,
                                                                            claim=claim)
                except:
                    raise

                log.msg("merge brids %s with building request %s " % (brids, b.requests[0].id))
                b.requests += breqs
                self.notifyRequestsRemoved(breqs)
                defer.returnValue(b)
                return
        defer.returnValue(None)

    @defer.inlineCallbacks
    def _fetchResumeBrdicts(self):
        # we need to resume builds that are claimed by this master
        # since the status is not in the db
        if self.resumeBrdicts is None:
            brdicts = yield self.master.db.buildrequests.getBuildRequests(
                        buildername=self.bldr.name, claimed="mine", results=RESUME, mergebrids="exclude")
            brdicts.sort(key=lambda brd : brd['submitted_at'])
            self.resumeBrdicts = brdicts
        defer.returnValue(self.resumeBrdicts)

    @defer.inlineCallbacks
    def _getNextBuildToResume(self):
        yield self._fetchResumeBrdicts()

        if not self.resumeBrdicts:
            defer.returnValue(None)
            return

        nextBreq = yield self._chooseBuildRequest(self.resumeBrdicts)
        defer.returnValue(nextBreq)

    def getResumeSlavepool(self, selectedSlavepool):
        if selectedSlavepool == "startSlavenames":
            return self.slavepool

        return self.resumeSlavePool

    @defer.inlineCallbacks
    def popNextBuildToResume(self):
        nextBuild = (None, None)
        selectNextBuild = True

        while selectNextBuild:
            # 1. pick a request
            breq = yield self._getBuildRequest(claim=False)

            if not breq:
                break

            slavepool = self.getResumeSlavepool(breq.slavepool)

            # run the build on a specific slave
            if breq.slavepool != "startSlavenames" and self.buildRequestHasSelectedSlave(breq):
                slavebuilder = yield self.buildHasSelectedSlave(breq, slavepool)
                if slavebuilder is not None:
                    nextBuild = (slavebuilder, breq)
                    break
                # slave maybe not available anymore try another build
                self._removeBuildRequest(breq, self.resumeBrdicts)
                continue

            #  2. pick a slave
            slave = yield self._popNextSlave(slavepool)

            if not slave:
                break

            # either satisfy this build or we leave it for another day
            self._removeBuildRequest(breq, self.resumeBrdicts)

            #  3. make sure slave+ is usable for the breq
            slave = yield self._pickUpSlave(slave, breq, slavepool)

            #  4. done? otherwise we will try another build
            if slave:
                nextBuild = (slave, breq)
                break

        defer.returnValue(nextBuild)

    @defer.inlineCallbacks
    def resetQueue(self, claim):
        if claim:
            self.unclaimedBrdicts = None
            yield self._fetchUnclaimedBrdicts()
        else:
            self.resumeBrdicts = None
            yield self._fetchResumeBrdicts()

    @defer.inlineCallbacks
    def _getBuildRequest(self, claim=True):
        breq = None

        getNextBuildRequestFunc = self._getNextUnclaimedBuildRequest if claim else self._getNextBuildToResume

        def getPendingBrdict():
            if claim:
                return self.unclaimedBrdicts
            return self.resumeBrdicts

        while breq is None:
            # 1. pick a build request
            breq = yield getNextBuildRequestFunc()

            if not breq:
                break

            # 2. try merge this build with a compatible running build
            if breq and self.bldr.building:
                breqs = yield self.mergeRequests(breq, pendingBrdicts=getPendingBrdict())
                totalBreqs = yield self.fetchPreviouslyMergedBuildRequests(breqs)
                brids = [br.id for br in totalBreqs]

                try:
                    build = yield self.mergeBuildingRequests(brids, totalBreqs, claim=claim)
                    if build is not None:
                        for b in totalBreqs:
                            self._removeBuildRequest(b, pendingBrdicts=getPendingBrdict())

                        yield self.bldr.maybeUpdateMergedBuilds(brid=build.requests[0].id,
                                                                buildnumber=build.build_status.number,
                                                                brids=brids)
                        breq = None
                        continue
                except:
                    # update unclaimed list
                    yield self.resetQueue(claim=claim)
                    breq = None
                    continue

            # 3. try merge with compatible finished build in the same chain
            brdict = self._getBrdictForBuildRequest(breq, getPendingBrdict())
            if breq and 'startbrid' in brdict.keys() and brdict['startbrid'] is not None:
                #check if can be merged with finished build
                finished_br = yield self.master.db.buildrequests\
                    .findCompatibleFinishedBuildRequest(self.bldr.name, brdict['startbrid'])
                if finished_br:
                    breqs = yield self.mergeRequests(breq, pendingBrdicts=getPendingBrdict())
                    brids = [br.id for br in breqs]
                    merged_brids = yield self.master.db.buildrequests\
                        .getRequestsCompatibleToMerge(self.bldr.name, brdict['startbrid'], brids)
                    merged_breqs = []

                    for br in breqs:
                        if br.id in merged_brids:
                            merged_breqs.append(br)

                    totalBreqs = yield self.fetchPreviouslyMergedBuildRequests(merged_breqs)
                    totalBrids = [br.id for br in totalBreqs]

                    try:
                        log.msg("merge finished buildresquest %s with %s" % (finished_br, totalBrids))
                        yield self.master.db.buildrequests.mergeFinishedBuildRequest(finished_br,
                                                                                     totalBrids,
                                                                                     claim=claim)
                        yield self.bldr._maybeBuildsetsComplete(totalBreqs, requestRemoved=True)
                        for b in totalBreqs:
                            self._removeBuildRequest(b, getPendingBrdict())
                        buildnumber = yield self.master.db.builds.getBuildNumberForRequest(finished_br['brid'])
                        yield self.bldr.maybeUpdateMergedBuilds(brid=finished_br['brid'],
                                                                buildnumber=buildnumber,
                                                                brids=brids)
                        breq = None
                        continue

                    except:
                        # update unclaimed list
                        yield self.resetQueue(claim=claim)
                        breq = None
                        continue

        defer.returnValue(breq)

    @defer.inlineCallbacks
    def popNextBuild(self):
        nextBuild = (None, None)
        selectNextBuild = True

        while selectNextBuild:
            #1. pick a buildrequest
            breq = yield self._getBuildRequest(claim=True)

            if not breq:
                break

            # check if should run the build on a specific slave
            if self.bldr.shouldUseSelectedSlave() and self.buildRequestHasSelectedSlave(breq):
                slavebuilder = yield self.buildHasSelectedSlave(breq, self.slavepool)
                if slavebuilder is not None:
                    nextBuild = (slavebuilder, breq)
                    break
                # slave maybe not available anymore try another build
                self._removeBuildRequest(breq, self.unclaimedBrdicts)
                continue

            #  2. pick a slave
            slave = yield self._popNextSlave(self.slavepool)
            if not slave:
                break

            # either satisfy this build or we leave it for another day
            self._removeBuildRequest(breq, self.unclaimedBrdicts)

            #  3. make sure slave+ is usable for the breq
            slave = yield self._pickUpSlave(slave, breq, self.slavepool)

            #  4. done? otherwise we will try another build
            if slave:
                nextBuild = (slave, breq)
                break

        defer.returnValue(nextBuild)


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

    # todo read from configuration if want to use buildbot's or katana build chooser
    BuildChooser = KatanaBuildChooser
    
    def __init__(self, botmaster):
        self.botmaster = botmaster
        self.master = botmaster.master

        # lock to ensure builders are only sorted once at any time
        self.pending_builders_lock = defer.DeferredLock()
        self.resume_pending_builders_lock = defer.DeferredLock()

        # sorted list of names of builders that need their maybeStartBuild
        # method invoked.
        self._pending_builders = []
        self._resume_pending_builders = []
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
        d.addErrback(log.err, "while sorting builds on %s" % (new_builders,))

    def _hasPendingBuilders(self):
        return len(self._pending_builders) > 0 or len(self._resume_pending_builders) > 0

    @defer.inlineCallbacks
    def _maybeStartBuildsOn(self, new_builders):
        new_builders = set(new_builders)
        alreadyHasPendingBuilders = new_builders <= set(self._pending_builders)
        alreadyHasResumePendingBuilders = new_builders <= set(self._resume_pending_builders)

        # if we won't add any builders, there's nothing to do
        if alreadyHasPendingBuilders and alreadyHasResumePendingBuilders:
            defer.succeed(None)
            return

        # reset the list of pending builders
        @defer.inlineCallbacks
        def resetPendingBuildersList(new_builders):
            try:
                # re-fetch existing_pending, in case it has changed 
                # while acquiring the lock
                existing_pending = set(self._pending_builders)

                # then sort the new, expanded set of builders
                self._pending_builders = yield self._sortBuilders(
                    list(existing_pending | new_builders), queue='unclaimed')

            except Exception:
                log.err(Failure(),
                        "while attempting to resetPendingBuildersList")

        @defer.inlineCallbacks
        def resetResumePendingBuildersList(new_builders):
            try:
                existing_pending = set(self._resume_pending_builders)

                self._resume_pending_builders = yield self._sortBuilders(
                    list(existing_pending | new_builders), queue='resume')

            except Exception:
                log.err(Failure(),
                        "while attempting to resetPendingBuildersList")


        if not alreadyHasPendingBuilders:
            yield self.pending_builders_lock.run(resetPendingBuildersList, new_builders)

        if not alreadyHasResumePendingBuilders:
            yield self.resume_pending_builders_lock.run(resetResumePendingBuildersList, new_builders)

        # start the activity loop, if we aren't already
        #  working on that.
        if self._hasPendingBuilders() and not self.active:
            self._activityLoop()

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
    def _globalPrioritySorter(self, master, builders, queue=None):
        timer = metrics.Timer("BuildRequestDistributor._globalPrioritySorter()")
        timer.start()
        log.msg("starting _globalPrioritySorter started at %s number of builders %d" %
                (util.epoch2datetime(timer.started), len(builders)))

        def findPrioritizedBuildRequest(bldr):
            d = defer.maybeDeferred(lambda :
                    bldr.getPrioritizedBuildRequest(queue=queue))
            d.addCallback(lambda br: (br, bldr))
            return d

        builRequesPriorityPerBuilder = yield defer.gatherResults(
                [findPrioritizedBuildRequest(bldr) for bldr in builders])

        priorityBuilders = sorted(builRequesPriorityPerBuilder,
                                  key=lambda (br, priority_bldr): (-br["priority"], br["submitted_at"])
                                  if br else (True, True))

        rv = [sorted_bldr[1] for sorted_bldr in priorityBuilders if sorted_bldr[0] is not None]

        log.msg("finished _globalPrioritySorter started at %s finished at %s elapsed %s" %
                (util.epoch2datetime(timer.started),
                 util.epoch2datetime(util.now(timer._reactor)),
                 util.formatInterval(util.now(timer._reactor) - timer.started)))
        timer.stop()
        defer.returnValue(rv)


    @defer.inlineCallbacks
    def _sortBuilders(self, buildernames, queue=None):
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
            sorter = self._globalPrioritySorter

        # run it
        try:
            builders = yield defer.maybeDeferred(lambda:
                                                 sorter(self.master, builders, queue=queue))

        except Exception:
            log.msg("Exception prioritizing builders; order unspecified")
            log.err(Failure())

        # and return the names
        rv = [b.name for b in builders]
        timer.stop()
        defer.returnValue(rv)

    @defer.inlineCallbacks
    def _maybeUpdatePendingBuilders(self, buildername):
        yield self.pending_builders_lock.acquire()
        self._pending_builders = yield self._sortBuilders(
                            list(set(self._pending_builders) | set([buildername])), queue='unclaimed')
        self.pending_builders_lock.release()

    @defer.inlineCallbacks
    def _maybeUpdateResumePendingBuilders(self, buildername):
        yield self.resume_pending_builders_lock.acquire()
        self._resume_pending_builders = yield self._sortBuilders(
                            list(set(self._resume_pending_builders) | set([buildername])), queue='resume')
        yield self.resume_pending_builders_lock.release()

    @defer.inlineCallbacks
    def _callMaybeStartBuildsOnBuilder(self):
        # lock pending_builders, pop an element from it, and release
        if not self._pending_builders:
            return

        yield self.pending_builders_lock.acquire()
        bldr_name = self._pending_builders.pop(0)
        self.pending_builders_lock.release()

        try:
            # get the actual builder object
            bldr = self.botmaster.builders.get(bldr_name)

            if bldr:
                log.msg("_maybeStartBuildsOnBuilder:  %s" % bldr_name)
                hasPendingBuildRequestsAndAvailableSlaves = yield self._maybeStartBuildsOnBuilder(bldr)
                if hasPendingBuildRequestsAndAvailableSlaves:
                    log.msg("builder %s has pending BuildRequests and availiable slaves prioritizing queue" % bldr_name)
                    yield self._maybeUpdatePendingBuilders(bldr_name)

        except Exception:
            log.err(Failure(), "from maybeStartBuild for builder '%s'" % (bldr_name,))

    @defer.inlineCallbacks
    def _callMaybeResumeBuildsOnBuilder(self):
        if not self._resume_pending_builders:
            return
        # lock pending_builders, pop an element from it, and release
        yield self.resume_pending_builders_lock.acquire()
        bldr_name = self._resume_pending_builders.pop(0)
        self.resume_pending_builders_lock.release()

        try:
            # get the actual builder object
            bldr = self.botmaster.builders.get(bldr_name)

            if bldr:
                log.msg("_maybeResumeBuildsOnBuilder:  %s" % bldr_name)
                hasPendingBuildRequestsAndAvailableSlaves = yield self._maybeResumeBuildsOnBuilder(bldr)
                if hasPendingBuildRequestsAndAvailableSlaves:
                    log.msg("builder %s has pending BuildRequests for resume and availiable slaves prioritizing queue"
                            % bldr_name)
                    yield self._maybeUpdateResumePendingBuilders(bldr_name)

        except Exception:
            log.err(Failure(), "from maybeStartBuild for builder '%s'" % (bldr_name,))

    @defer.inlineCallbacks
    def _activityLoop(self):
        self.active = True

        timer = metrics.Timer('BuildRequestDistributor._activityLoop()')
        timer.start()

        while self._hasPendingBuilders():
            yield self.activity_lock.acquire()

            yield self._callMaybeStartBuildsOnBuilder()
            yield self._callMaybeResumeBuildsOnBuilder()

            self.activity_lock.release()

            # bail out if we shouldn't keep looping
            if not self.running or not self._hasPendingBuilders():
                break

        timer.stop()

        self.active = False
        self._quiet()

    def logResumeOrStartBuildStatus(self, msg, slave, breqs):
        if len(breqs) > 0:
            log.msg(" %s for buildername %s using slave %s buildrequest id %d priority %d submittedAt %s buildsetid %d" %
                    (msg, breqs[0].buildername, slave, breqs[0].id, breqs[0].priority,
                     util.epoch2datetime(breqs[0].submittedAt),
                     breqs[0].bsid))

    @defer.inlineCallbacks
    def _maybeResumeBuildOnBuilder(self, bc, bldr):
        slave, buildnumber, breqs = yield bc.chooseNextBuildToResume()

        if not slave or not breqs:
            return

        brids = [br.id for br in breqs]
        yield self.master.db.buildrequests.updateBuildRequests(brids, results=BEGINNING)

        buildStarted = yield bldr.maybeResumeBuild(slave, buildnumber, breqs)

        msg = "_maybeResumeBuildOnBuilder is resuming build"

        if not buildStarted:
            bc.resumeSlavePool = bldr.getAvailableSlavesToResume()
            bc.slavepool = bldr.getAvailableSlaves()
            yield self.master.db.buildrequests.updateBuildRequests(brids, results=RESUME)
            self.botmaster.maybeStartBuildsForBuilder(bldr.name)
            msg = "_maybeResumeBuildOnBuilder could not resume build"

        self.logResumeOrStartBuildStatus(msg, slave, breqs)

    @defer.inlineCallbacks
    def _maybeStartNewBuildsOnBuilder(self, bc, bldr):
        slave, breqs = yield bc.chooseNextBuild()

        if not slave or not breqs:
            return

        # claim brid's
        brids = [br.id for br in breqs]
        yield bc.claimBuildRequests(breqs)

        buildStarted = yield bldr.maybeStartBuild(slave, breqs)

        msg = "_maybeStartNewBuildsOnBuilder is starting build"

        if not buildStarted:
            bc.slavepool = bldr.getAvailableSlaves()
            yield self.master.db.buildrequests.unclaimBuildRequests(brids)
            # and try starting builds again.  If we still have a working slave,
            # then this may re-claim the same buildrequests
            self.botmaster.maybeStartBuildsForBuilder(bldr.name)
            msg = "_maybeStartNewBuildsOnBuilder could not start build"

        self.logResumeOrStartBuildStatus(msg, slave, breqs)

    @defer.inlineCallbacks
    def _maybeResumeBuildsOnBuilder(self, bldr):
        # create a chooser to give us our next builds
        # this object is temporary and will go away when we're done

        bc = self.createBuildChooser(bldr, self.master)

        try:

            if isinstance(bc, KatanaBuildChooser):
                 yield self._maybeResumeBuildOnBuilder(bc, bldr)

        except Exception:
            log.msg(Failure(), "from _maybeResumeBuildsOnBuilder for builder '%s'" % bldr.name)
                
        def hasPendingBuildRequestsAndCanStartBuilds(pendingQueue, slavePool):
            return (pendingQueue is not None and len(pendingQueue) > 0) \
                   and (slavePool is not None and len(slavePool) > 0)

        # take into accound if there are slaves available for next pending builds
        hasPendingBuildRequestsAndAvailableSlaves = isinstance(bc, KatanaBuildChooser) and \
                                                    hasPendingBuildRequestsAndCanStartBuilds(bc.resumeBrdicts,
                                                                                             bc.resumeSlavePool)

        defer.returnValue(hasPendingBuildRequestsAndAvailableSlaves)

    @defer.inlineCallbacks
    def _maybeStartBuildsOnBuilder(self, bldr):
        # create a chooser to give us our next builds
        # this object is temporary and will go away when we're done

        bc = self.createBuildChooser(bldr, self.master)

        try:
            yield self._maybeStartNewBuildsOnBuilder(bc, bldr)

        except Exception:
            log.msg(Failure(), "from _maybeStartBuildsOnBuilder for builder '%s'" % bldr.name)

        def hasPendingBuildRequestsAndCanStartBuilds(pendingQueue, slavePool):
            return (pendingQueue is not None and len(pendingQueue) > 0) \
                   and (slavePool is not None and len(slavePool) > 0)

        # take into accound if there are slaves available for next pending builds
        hasPendingBuildRequestsAndAvailableSlaves =  hasPendingBuildRequestsAndCanStartBuilds(bc.unclaimedBrdicts,
                                                                                              bc.slavepool)

        defer.returnValue(hasPendingBuildRequestsAndAvailableSlaves)

    def createBuildChooser(self, bldr, master):
        # just instantiate the build chooser requested
        return self.BuildChooser(bldr, master)
            
    def _quiet(self):
        # shim for tests
        pass # pragma: no cover
