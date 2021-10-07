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


import copy
import random
from datetime import datetime

from dateutil.tz import tzutc

from twisted.internet import defer
from twisted.python import log
from twisted.python.failure import Failure

from buildbot.data import resultspec
from buildbot.process import metrics
from buildbot.process.buildrequest import BuildRequest
from buildbot.util import deferwaiter
from buildbot.util import epoch2datetime
from buildbot.util import service


class BuildChooserBase:
    #
    # WARNING: This API is experimental and in active development.
    #
    # This internal object selects a new build+worker pair. It acts as a
    # generator, initializing its state on creation and offering up new
    # pairs until exhaustion. The object can be destroyed at any time
    # (eg, before the list exhausts), and can be "restarted" by abandoning
    # an old instance and creating a new one.
    #
    # The entry point is:
    #    * bc.chooseNextBuild() - get the next (worker, [breqs]) or
    #      (None, None)
    #
    # The default implementation of this class implements a default
    # chooseNextBuild() that delegates out to two other functions:
    #   * bc.popNextBuild() - get the next (worker, breq) pair

    def __init__(self, bldr, master):
        self.bldr = bldr
        self.master = master
        self.breqCache = {}
        self.unclaimedBrdicts = None

    @defer.inlineCallbacks
    def chooseNextBuild(self):
        # Return the next build, as a (worker, [breqs]) pair

        worker, breq = yield self.popNextBuild()
        if not worker or not breq:
            return (None, None)

        return (worker, [breq])

    # Must be implemented by subclass
    def popNextBuild(self):
        # Pick the next (worker, breq) pair; note this is pre-merge, so
        # it's just one breq
        raise NotImplementedError("Subclasses must implement this!")

    # - Helper functions that are generally useful to all subclasses -
    @defer.inlineCallbacks
    def _fetchUnclaimedBrdicts(self):
        # Sets up a cache of all the unclaimed brdicts. The cache is
        # saved at self.unclaimedBrdicts cache. If the cache already
        # exists, this function does nothing. If a refetch is desired, set
        # the self.unclaimedBrdicts to None before calling."""
        if self.unclaimedBrdicts is None:
            # TODO: use order of the DATA API
            brdicts = yield self.master.data.get(('builders',
                                                  (yield self.bldr.getBuilderId()),
                                                  'buildrequests'),
                                                 [resultspec.Filter('claimed',
                                                                    'eq',
                                                                    [False])])
            # sort by submitted_at, so the first is the oldest
            brdicts.sort(key=lambda brd: brd['submitted_at'])
            self.unclaimedBrdicts = brdicts
        return self.unclaimedBrdicts

    @defer.inlineCallbacks
    def _getBuildRequestForBrdict(self, brdict):
        # Turn a brdict into a BuildRequest into a brdict. This is useful
        # for API like 'nextBuild', which operate on BuildRequest objects.

        breq = self.breqCache.get(brdict['buildrequestid'])
        if not breq:
            breq = yield BuildRequest.fromBrdict(self.master, brdict)
            if breq:
                self.breqCache[brdict['buildrequestid']] = breq
        return breq

    def _getBrdictForBuildRequest(self, breq):
        # Turn a BuildRequest back into a brdict. This operates from the
        # cache, which must be set up once via _fetchUnclaimedBrdicts

        if breq is None:
            return None

        brid = breq.id
        for brdict in self.unclaimedBrdicts:
            if brid == brdict['buildrequestid']:
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

    @defer.inlineCallbacks
    def _getUnclaimedBuildRequests(self):
        # Retrieve the list of BuildRequest objects for all unclaimed builds. This should
        # return a fresh list each time so that `popNextBuild` is free to modify it.
        yield self._fetchUnclaimedBrdicts()
        breqs = yield defer.gatherResults([
            self._getBuildRequestForBrdict(brdict)
            for brdict in self.unclaimedBrdicts])

        return breqs


class BasicBuildChooser(BuildChooserBase):
    """
    BasicBuildChooser generates build pairs via the builder's configuration points:

    - config.nextWorker (or random.choice if not set)
    - config.nextBuild (or "top" if not set)

    When the distributor calls popNextBuild, we retrieve all unclaimed build requests.
    nextBuild is used to select the first one to attempt to place on a worker. If
    nextBuild returns None, we immediately return an empty pair and the distribution
    cycle ends.

    If a build request was chosen, we will then pass it to nextWorker. If nextWorker
    returns None, we cannot place this request. We discard it from consideration and loop
    around to the next request as selected by nextBuild.

    If a worker can be chosen, the final step is to call Builder.canStartBuild. If this
    returns False, we discard the chosen worker and loop back to try to find another. If
    it returns True, we remove this build request from the collection of unclaimed
    requests and return the (worker, request) pair. The distribution cycle can continue
    on to calling popNextBuild again.

    If either nextBuild or nextWorker return requests/workers that do not actually belong
    to our builder, we treat it as if they had returned None.
    """
    def __init__(self, bldr, master):
        super().__init__(bldr, master)
        self.workerpool = self.bldr.getAvailableWorkers()

        self.nextWorker = self.bldr.config.nextWorker
        if not self.nextWorker:
            self.nextWorker = lambda _, workers, __: random.choice(
                workers) if workers else None

        self.nextBuild = self.bldr.config.nextBuild
        if not self.nextBuild:
            self.nextBuild = lambda _, breqs: breqs[0] if breqs else None

    @defer.inlineCallbacks
    def popNextBuild(self):
        breqs = yield self._getUnclaimedBuildRequests()
        while breqs:
            breq = None
            try:
                breq = yield self.nextBuild(self.bldr, breqs)
                if breq not in breqs:
                    # Handle a misbehaving nextBuild returning a request for a different
                    # builder.
                    breq = None
                else:
                    # Only consider each build request once.
                    breqs.remove(breq)

            except Exception:
                log.err(Failure(), "from nextBuild for builder '{}'".format(self.bldr))

            if breq is None:
                break

            # For each build request we need to consider the entire worker pool, so make
            # a copy of it here that we can discard workers from if they don't work for
            # the current request.
            workers = copy.copy(self.workerpool)
            while workers:
                worker = None
                try:
                    worker = yield self.nextWorker(self.bldr, workers, breq)
                    if worker not in workers:
                        # Handle a misbehaving nextWorker returning a worker we cannot
                        # actually use.
                        worker = None
                    else:
                        # Only consider each worker once.
                        workers.remove(worker)

                except Exception:
                    log.err(Failure(),
                            "from nextWorker for builder '{}'".format(self.bldr))

                if worker is None:
                    # If none of the workers are able to handle this request at all, move
                    # on to the next request.
                    break

                canStart = yield self.bldr.canStartBuild(worker, breq)
                if canStart:
                    self._removeBuildRequest(breq)
                    self.workerpool.remove(worker)
                    return (worker, breq)

        # If we never returned from within the loop, we failed to find any runnable
        # requests.
        return (None, None)


class BuildRequestDistributor(service.AsyncMultiService):

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
        super().__init__()
        self.botmaster = botmaster

        # lock to ensure builders are only sorted once at any time
        self.pending_builders_lock = defer.DeferredLock()

        # sorted list of names of builders that need their maybeStartBuild
        # method invoked.
        self._pending_builders = []
        self.activity_lock = defer.DeferredLock()
        self.active = False

        self._deferwaiter = deferwaiter.DeferWaiter()
        self._activity_loop_deferred = None

    @defer.inlineCallbacks
    def stopService(self):
        # Lots of stuff happens asynchronously here, so we need to let it all
        # quiesce.  First, let the parent stopService succeed between
        # activities; then the loop will stop calling itself, since
        # self.running is false.
        yield self.activity_lock.run(service.AsyncService.stopService, self)

        # now let any outstanding calls to maybeStartBuildsOn to finish, so
        # they don't get interrupted in mid-stride.  This tends to be
        # particularly painful because it can occur when a generator is gc'd.
        # TEST-TODO: this behavior is not asserted in any way.
        yield self._deferwaiter.wait()

    @defer.inlineCallbacks
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

        try:
            yield self._deferwaiter.add(self._maybeStartBuildsOn(new_builders))
        except Exception as e:  # pragma: no cover
            log.err(e, "while starting builds on {0}".format(new_builders))

    @defer.inlineCallbacks
    def _maybeStartBuildsOn(self, new_builders):
        new_builders = set(new_builders)
        existing_pending = set(self._pending_builders)

        # if we won't add any builders, there's nothing to do
        if new_builders < existing_pending:
            return None

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
                    self._activity_loop_deferred = self._activityLoop()
            except Exception:  # pragma: no cover
                log.err(Failure(),
                        "while attempting to start builds on {}".format(self.name))

        yield self.pending_builders_lock.run(
            resetPendingBuildersList, new_builders)
        return None

    @defer.inlineCallbacks
    def _defaultSorter(self, master, builders):
        timer = metrics.Timer("BuildRequestDistributor._defaultSorter()")
        timer.start()
        # perform an asynchronous schwarzian transform, transforming None
        # into sys.maxint so that it sorts to the end

        def xform(bldr):
            d = defer.maybeDeferred(bldr.getOldestRequestTime)
            d.addCallback(lambda time:
                          (((time is None) and None or time), bldr))
            return d
        xformed = yield defer.gatherResults(
            [xform(bldr) for bldr in builders])

        # sort the transformed list synchronously, comparing None to the end of
        # the list
        def xformedKey(a):
            """
            Key function can be used to sort a list
            where each list element is a tuple:
                (datetime.datetime, Builder)

            @return: a tuple of (date, builder name)
            """
            (date, builder) = a
            if date is None:
                # Choose a really big date, so that any
                # date set to 'None' will appear at the
                # end of the list during comparisons.
                date = datetime.max
                # Need to set the timezone on the date, in order
                # to perform comparisons with other dates which
                # have the time zone set.
                date = date.replace(tzinfo=tzutc())
            return (date, builder.name)
        xformed.sort(key=xformedKey)

        # and reverse the transform
        rv = [xf[1] for xf in xformed]
        timer.stop()
        return rv

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
            builders = yield sorter(self.master, builders)
        except Exception:
            log.err(Failure(), "prioritizing builders; order unspecified")

        # and return the names
        rv = [b.name for b in builders]
        timer.stop()
        return rv

    @defer.inlineCallbacks
    def _activityLoop(self):
        self.active = True

        timer = metrics.Timer('BuildRequestDistributor._activityLoop()')
        timer.start()
        pending_builders = []
        while True:
            yield self.activity_lock.acquire()
            if not self.running:
                self.activity_lock.release()
                break

            if not pending_builders:
                # lock pending_builders, pop an element from it, and release
                yield self.pending_builders_lock.acquire()

                # bail out if we shouldn't keep looping
                if not self._pending_builders:
                    self.pending_builders_lock.release()
                    self.activity_lock.release()
                    break
                # take that builder list, and run it until the end
                # we make a copy of it, as it could be modified meanwhile
                pending_builders = copy.copy(self._pending_builders)
                self._pending_builders = []
                self.pending_builders_lock.release()

            bldr_name = pending_builders.pop(0)

            # get the actual builder object
            bldr = self.botmaster.builders.get(bldr_name)
            try:
                if bldr:
                    yield self._maybeStartBuildsOnBuilder(bldr)
            except Exception:
                log.err(Failure(), "from maybeStartBuild for builder '{}'".format(bldr_name))

            self.activity_lock.release()

        timer.stop()

        self.active = False

    @defer.inlineCallbacks
    def _maybeStartBuildsOnBuilder(self, bldr):
        # create a chooser to give us our next builds
        # this object is temporary and will go away when we're done
        bc = self.createBuildChooser(bldr, self.master)

        while True:
            worker, breqs = yield bc.chooseNextBuild()
            if not worker or not breqs:
                break

            # claim brid's
            brids = [br.id for br in breqs]
            claimed_at_epoch = self.master.reactor.seconds()
            claimed_at = epoch2datetime(claimed_at_epoch)
            if not (yield self.master.data.updates.claimBuildRequests(
                    brids, claimed_at=claimed_at)):
                # some brids were already claimed, so start over
                bc = self.createBuildChooser(bldr, self.master)
                continue

            buildStarted = yield bldr.maybeStartBuild(worker, breqs)
            if not buildStarted:
                yield self.master.data.updates.unclaimBuildRequests(brids)
                # try starting builds again.  If we still have a working worker,
                # then this may re-claim the same buildrequests
                self.botmaster.maybeStartBuildsForBuilder(self.name)

    def createBuildChooser(self, bldr, master):
        # just instantiate the build chooser requested
        return self.BuildChooser(bldr, master)

    @defer.inlineCallbacks
    def _waitForFinish(self):
        if self._activity_loop_deferred is not None:
            yield self._activity_loop_deferred
