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

import random
from unittest import mock

from parameterized import parameterized
from twisted.internet import defer
from twisted.python import failure
from twisted.trial import unittest

from buildbot import config
from buildbot.db import buildrequests
from buildbot.process import buildrequestdistributor
from buildbot.process import factory
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import epoch2datetime
from buildbot.util.eventual import fireEventually
from buildbot.util.twisted import async_to_deferred


def nth_worker(n):
    def pick_nth_by_name(builder, workers=None, br=None):
        if workers is None:
            workers = builder
        workers = workers[:]
        workers.sort(key=lambda a: a.name)
        return workers[n]

    return pick_nth_by_name


class TestBRDBase(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.botmaster = mock.Mock(name='botmaster')
        self.botmaster.builders = {}
        self.builders = {}

        def prioritizeBuilders(master, builders):
            # simple sort-by-name by default
            return sorted(builders, key=lambda b1: b1.name)

        self.master = self.botmaster.master = yield fakemaster.make_master(
            self, wantData=True, wantDb=True
        )
        self.master.caches = fakemaster.FakeCaches()
        self.master.config.prioritizeBuilders = prioritizeBuilders
        self.brd = buildrequestdistributor.BuildRequestDistributor(self.botmaster)
        self.brd.parent = self.botmaster
        self.brd.startService()

        @defer.inlineCallbacks
        def cleanup():
            if self.brd.running:
                yield self.brd.stopService()

        self.addCleanup(cleanup)

        # a collection of rows that would otherwise clutter up every test
        self.base_rows = [
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.SourceStamp(id=21),
            fakedb.Builder(id=77, name='A'),
            fakedb.Buildset(id=11, reason='because'),
            fakedb.BuildsetSourceStamp(sourcestampid=21, buildsetid=11),
        ]

    def make_workers(self, worker_count):
        rows = self.base_rows[:]
        for i in range(worker_count):
            self.addWorkers({f'test-worker{i}': 1})
            rows.append(fakedb.Buildset(id=100 + i, reason='because'))
            rows.append(fakedb.BuildsetSourceStamp(buildsetid=100 + i, sourcestampid=21))
            rows.append(fakedb.BuildRequest(id=10 + i, buildsetid=100 + i, builderid=77))
        return rows

    def addWorkers(self, workerforbuilders):
        """C{workerforbuilders} maps name : available"""
        for name, avail in workerforbuilders.items():
            wfb = mock.Mock(spec=['isAvailable'], name=name)
            wfb.name = name
            wfb.isAvailable.return_value = avail
            for bldr in self.builders.values():
                bldr.workers.append(wfb)

    @defer.inlineCallbacks
    def createBuilder(self, name, builderid=None, builder_config=None):
        if builderid is None:
            b = fakedb.Builder(name=name)
            yield self.master.db.insert_test_data([b])
            builderid = b.id

        bldr = mock.Mock(name=name)
        bldr.name = name
        self.botmaster.builders[name] = bldr
        self.builders[name] = bldr

        def maybeStartBuild(worker, builds):
            worker.isAvailable.return_value = False
            self.startedBuilds.append((worker.name, builds))
            d = defer.Deferred()
            self.reactor.callLater(0, d.callback, True)
            return d

        bldr.maybeStartBuild = maybeStartBuild
        bldr.getCollapseRequestsFn = lambda: False

        bldr.workers = []
        bldr.getAvailableWorkers = lambda: [w for w in bldr.workers if w.isAvailable()]
        bldr.getBuilderId = lambda: (builderid)
        if builder_config is None:
            bldr.config.nextWorker = None
            bldr.config.nextBuild = None
        else:
            bldr.config = builder_config

        def canStartBuild(*args):
            can = bldr.config.canStartBuild
            return not can or can(*args)

        bldr.canStartBuild = canStartBuild

        return bldr

    @defer.inlineCallbacks
    def addBuilders(self, names):
        self.startedBuilds = []

        for name in names:
            yield self.createBuilder(name)

    @defer.inlineCallbacks
    def assert_claims(self, brids):
        brs = yield self.master.data.get(('buildrequests',))
        got_brids = [
            br['buildrequestid']
            for br in brs
            if br['claimed_by_masterid'] == fakedb.FakeDBConnector.MASTER_ID
        ]

        self.assertEqual(list(set(got_brids)), list(set(brids)))


class Test(TestBRDBase):
    def checkAllCleanedUp(self):
        # check that the BRD didn't end with a stuck lock or in the 'active' state (which would mean
        # it ended without unwinding correctly)
        self.assertEqual(self.brd.pending_builders_lock.locked, False)
        self.assertEqual(self.brd.activity_lock.locked, False)
        self.assertEqual(self.brd.active, False)

    def useMock_maybeStartBuildsOnBuilder(self):
        # sets up a mock "maybeStartBuildsOnBuilder" so we can track
        # how the method gets invoked

        # keep track of the calls to brd.maybeStartBuildsOnBuilder
        self.maybeStartBuildsOnBuilder_calls = []

        def maybeStartBuildsOnBuilder(bldr):
            self.assertIdentical(self.builders[bldr.name], bldr)
            self.maybeStartBuildsOnBuilder_calls.append(bldr.name)
            return fireEventually()

        self.brd._maybeStartBuildsOnBuilder = maybeStartBuildsOnBuilder

    def removeBuilder(self, name):
        del self.builders[name]
        del self.botmaster.builders[name]

    # tests

    @defer.inlineCallbacks
    def test_maybeStartBuildsOn_simple(self):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['bldr1'])
        yield self.brd.maybeStartBuildsOn(['bldr1'])

        yield self.brd._waitForFinish()
        self.assertEqual(self.maybeStartBuildsOnBuilder_calls, ['bldr1'])
        self.checkAllCleanedUp()

    @defer.inlineCallbacks
    def test_maybeStartBuildsOn_parallel(self):
        # test 15 "parallel" invocations of maybeStartBuildsOn, with a
        # _sortBuilders that takes a while.  This is a regression test for bug
        # 1979.
        builders = [f'bldr{i:02}' for i in range(15)]

        def slow_sorter(master, bldrs):
            bldrs.sort(key=lambda b1: b1.name)
            d = defer.Deferred()
            self.reactor.callLater(0, d.callback, bldrs)

            def done(_):
                return _

            d.addCallback(done)
            return d

        self.master.config.prioritizeBuilders = slow_sorter

        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(builders)
        for bldr in builders:
            yield self.brd.maybeStartBuildsOn([bldr])

        yield self.brd._waitForFinish()
        self.assertEqual(self.maybeStartBuildsOnBuilder_calls, builders)
        self.checkAllCleanedUp()

    @defer.inlineCallbacks
    def test_maybeStartBuildsOn_exception(self):
        self.addBuilders(['bldr1'])

        async def _maybeStartBuildsOnBuilder(n):
            # fail slowly, so that the activity loop doesn't exit too soon
            d = defer.Deferred()
            self.reactor.callLater(0, d.errback, failure.Failure(RuntimeError("oh noes")))
            await d

        self.brd._maybeStartBuildsOnBuilder = _maybeStartBuildsOnBuilder

        yield self.brd.maybeStartBuildsOn(['bldr1'])

        yield self.brd._waitForFinish()
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        self.checkAllCleanedUp()

    @defer.inlineCallbacks
    def test_maybeStartBuildsOn_collapsing(self):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['bldr1', 'bldr2', 'bldr3'])
        yield self.brd.maybeStartBuildsOn(['bldr3'])
        yield self.brd.maybeStartBuildsOn(['bldr2', 'bldr1'])
        yield self.brd.maybeStartBuildsOn(['bldr4'])  # should be ignored
        yield self.brd.maybeStartBuildsOn(['bldr2'])  # already queued - ignored
        yield self.brd.maybeStartBuildsOn(['bldr3', 'bldr2'])

        yield self.brd._waitForFinish()
        # bldr3 gets invoked twice, since it's considered to have started
        # already when the first call to maybeStartBuildsOn returns
        self.assertEqual(self.maybeStartBuildsOnBuilder_calls, ['bldr3', 'bldr1', 'bldr2', 'bldr3'])
        self.checkAllCleanedUp()

    @defer.inlineCallbacks
    def test_maybeStartBuildsOn_builders_missing(self):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['bldr1', 'bldr2', 'bldr3'])
        yield self.brd.maybeStartBuildsOn(['bldr1', 'bldr2', 'bldr3'])
        # bldr1 is already run, so surreptitiously remove the other
        # two - nothing should crash, but the builders should not run
        self.removeBuilder('bldr2')
        self.removeBuilder('bldr3')

        yield self.brd._waitForFinish()
        self.assertEqual(self.maybeStartBuildsOnBuilder_calls, ['bldr1'])
        self.checkAllCleanedUp()

    @defer.inlineCallbacks
    def do_test_sortBuilders(
        self,
        prioritizeBuilders,
        oldestRequestTimes,
        highestPriorities,
        expected,
        returnDeferred=False,
    ):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(list(oldestRequestTimes))
        self.master.config.prioritizeBuilders = prioritizeBuilders

        def mklambda(t):  # work around variable-binding issues
            if returnDeferred:
                return lambda: defer.succeed(t)
            return lambda: t

        for n, t in oldestRequestTimes.items():
            if t is not None:
                t = epoch2datetime(t)
            self.builders[n].getOldestRequestTime = mklambda(t)

        for n, t in highestPriorities.items():
            self.builders[n].get_highest_priority = mklambda(t)

        result = yield self.brd._sortBuilders(list(oldestRequestTimes))

        self.assertEqual(result, expected)
        self.checkAllCleanedUp()

    def test_sortBuilders_default_sync(self):
        return self.do_test_sortBuilders(
            None,  # use the default sort
            {"bldr1": 777, "bldr2": 999, "bldr3": 888},
            {"bldr1": 10, "bldr2": 15, "bldr3": 5},
            ['bldr2', 'bldr1', 'bldr3'],
        )

    def test_sortBuilders_default_asyn(self):
        return self.do_test_sortBuilders(
            None,  # use the default sort
            {"bldr1": 777, "bldr2": 999, "bldr3": 888},
            {"bldr1": 10, "bldr2": 15, "bldr3": 5},
            ['bldr2', 'bldr1', 'bldr3'],
            returnDeferred=True,
        )

    def test_sortBuilders_default_None(self):
        return self.do_test_sortBuilders(
            None,  # use the default sort
            {"bldr1": 777, "bldr2": None, "bldr3": 888},
            {"bldr1": 10, "bldr2": None, "bldr3": 5},
            ['bldr1', 'bldr3', 'bldr2'],
        )

    def test_sortBuilders_default_priority_match(self):
        return self.do_test_sortBuilders(
            None,  # use the default sort
            {"bldr1": 777, "bldr2": 999, "bldr3": 888},
            {"bldr1": 10, "bldr2": 10, "bldr3": 10},
            ['bldr1', 'bldr3', 'bldr2'],
        )

    def test_sortBuilders_custom(self):
        def prioritizeBuilders(master, builders):
            self.assertIdentical(master, self.master)
            return sorted(builders, key=lambda b: b.name)

        return self.do_test_sortBuilders(
            prioritizeBuilders,
            {"bldr1": 1, "bldr2": 1, "bldr3": 1},
            {"bldr1": 10, "bldr2": 15, "bldr3": 5},
            ['bldr1', 'bldr2', 'bldr3'],
        )

    def test_sortBuilders_custom_async(self):
        def prioritizeBuilders(master, builders):
            self.assertIdentical(master, self.master)
            return defer.succeed(sorted(builders, key=lambda b: b.name))

        return self.do_test_sortBuilders(
            prioritizeBuilders,
            {"bldr1": 1, "bldr2": 1, "bldr3": 1},
            {"bldr1": 10, "bldr2": 15, "bldr3": 5},
            ['bldr1', 'bldr2', 'bldr3'],
        )

    @defer.inlineCallbacks
    def test_sortBuilders_custom_exception(self):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['x', 'y'])

        def fail(m, b):
            raise RuntimeError("oh noes")

        self.master.config.prioritizeBuilders = fail

        # expect to get the builders back in the same order in the event of an
        # exception
        result = yield self.brd._sortBuilders(['y', 'x'])

        self.assertEqual(result, ['y', 'x'])

        # and expect the exception to be logged
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def test_stopService(self):
        # check that stopService waits for a builder run to complete, but does not
        # allow a subsequent run to start
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['A', 'B'])

        oldMSBOB = self.brd._maybeStartBuildsOnBuilder

        def maybeStartBuildsOnBuilder(bldr):
            d = oldMSBOB(bldr)

            stop_d = self.brd.stopService()
            stop_d.addCallback(lambda _: self.maybeStartBuildsOnBuilder_calls.append('(stopped)'))

            d.addCallback(lambda _: self.maybeStartBuildsOnBuilder_calls.append('finished'))
            return d

        self.brd._maybeStartBuildsOnBuilder = maybeStartBuildsOnBuilder

        # start both builds; A should start and complete *before* the service stops,
        # and B should not run.
        yield self.brd.maybeStartBuildsOn(['A', 'B'])

        yield self.brd._waitForFinish()

        self.assertEqual(self.maybeStartBuildsOnBuilder_calls, ['A', 'finished', '(stopped)'])


class TestMaybeStartBuilds(TestBRDBase):
    @defer.inlineCallbacks
    def setUp(self):
        yield super().setUp()

        self.startedBuilds = []

        self.bldr = yield self.createBuilder('A', builderid=77)
        self.builders['A'] = self.bldr

    def assertBuildsStarted(self, exp):
        # munge builds_started into (worker, [brids])
        builds_started = [
            (worker, [br.id for br in breqs]) for (worker, breqs) in self.startedBuilds
        ]
        self.assertEqual(builds_started, exp)

    # _maybeStartBuildsOnBuilder

    @async_to_deferred
    async def do_test_maybeStartBuildsOnBuilder(self, rows=None, exp_claims=None, exp_builds=None):
        rows = rows or []
        exp_claims = exp_claims or []
        exp_builds = exp_builds or []
        await self.master.db.insert_test_data(rows)

        await self.brd._maybeStartBuildsOnBuilder(self.bldr)

        await self.assert_claims(exp_claims)
        self.assertBuildsStarted(exp_builds)

    @defer.inlineCallbacks
    def test_no_buildrequests(self):
        self.addWorkers({'test-worker11': 1})
        yield self.do_test_maybeStartBuildsOnBuilder(exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_no_workerforbuilders(self):
        rows = [
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Builder(id=78, name='bldr'),
            fakedb.Buildset(id=10),
            fakedb.BuildRequest(id=11, buildsetid=10, builderid=78),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_limited_by_workers(self):
        self.addWorkers({'test-worker1': 1})
        rows = [
            *self.base_rows,
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77, submitted_at=130000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows, exp_claims=[10], exp_builds=[('test-worker1', [10])]
        )

    @defer.inlineCallbacks
    def test_sorted_by_submit_time(self):
        # same as "limited_by_workers" but with rows swapped
        self.addWorkers({'test-worker1': 1})
        rows = [
            *self.base_rows,
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77, submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows, exp_claims=[10], exp_builds=[('test-worker1', [10])]
        )

    @defer.inlineCallbacks
    def test_limited_by_available_workers(self):
        self.addWorkers({'test-worker1': 0, 'test-worker2': 1})
        rows = [
            *self.base_rows,
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77, submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows, exp_claims=[10], exp_builds=[('test-worker2', [10])]
        )

    @defer.inlineCallbacks
    def test_slow_db(self):
        # test what happens if the "getBuildRequests" fetch takes a "long time"
        self.addWorkers({'test-worker1': 1})

        # wrap to simulate a "long" db access
        old_getBuildRequests = self.master.db.buildrequests.getBuildRequests

        def longGetBuildRequests(*args, **kwargs):
            res_d = old_getBuildRequests(*args, **kwargs)
            long_d = defer.Deferred()
            long_d.addCallback(lambda _: res_d)
            self.reactor.callLater(0, long_d.callback, None)
            return long_d

        self.master.db.buildrequests.getBuildRequests = longGetBuildRequests

        rows = [
            *self.base_rows,
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77, submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows, exp_claims=[10], exp_builds=[('test-worker1', [10])]
        )

    @defer.inlineCallbacks
    def test_limited_by_canStartBuild(self):
        """Set the 'canStartBuild' value in the config to something
        that limits the possible options."""

        self.bldr.config.nextWorker = nth_worker(-1)

        pairs_tested = []

        def _canStartBuild(worker, breq):
            result = (worker.name, breq.id)
            pairs_tested.append(result)
            allowed = [
                ("test-worker1", 10),
                ("test-worker3", 11),
            ]
            return result in allowed

        self.bldr.config.canStartBuild = _canStartBuild

        self.addWorkers({'test-worker1': 1, 'test-worker2': 1, 'test-worker3': 1})
        rows = [
            *self.base_rows,
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77, submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
            fakedb.BuildRequest(id=12, buildsetid=11, builderid=77, submitted_at=140000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows,
            exp_claims=[10, 11],
            exp_builds=[('test-worker1', [10]), ('test-worker3', [11])],
        )

        # we expect brids in order (10-11-12),
        # with each searched in reverse order of workers (3-2-1) available (due
        # to nth_worker(-1))
        self.assertEqual(
            pairs_tested,
            [
                ('test-worker3', 10),
                ('test-worker2', 10),
                ('test-worker1', 10),
                ('test-worker3', 11),
                ('test-worker2', 12),
            ],
        )

    @defer.inlineCallbacks
    def test_limited_by_canStartBuild_deferreds(self):
        # Another variant that returns Deferred types,
        self.bldr.config.nextWorker = nth_worker(-1)

        pairs_tested = []

        def _canStartBuild(worker, breq):
            result = (worker.name, breq.id)
            pairs_tested.append(result)
            allowed = [
                ("test-worker1", 10),
                ("test-worker3", 11),
            ]
            return defer.succeed(result in allowed)

        self.bldr.config.canStartBuild = _canStartBuild

        self.addWorkers({'test-worker1': 1, 'test-worker2': 1, 'test-worker3': 1})
        rows = [
            *self.base_rows,
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77, submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
            fakedb.BuildRequest(id=12, buildsetid=11, builderid=77, submitted_at=140000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows,
            exp_claims=[10, 11],
            exp_builds=[('test-worker1', [10]), ('test-worker3', [11])],
        )

        # we expect brids in order (10-11-12),
        # with worker2 unable to pair
        self.assertEqual(
            pairs_tested,
            [
                ('test-worker3', 10),
                ('test-worker2', 10),
                ('test-worker1', 10),
                ('test-worker3', 11),
                ('test-worker2', 12),
            ],
        )

    @defer.inlineCallbacks
    def test_unlimited(self):
        self.bldr.config.nextWorker = nth_worker(-1)
        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [
            *self.base_rows,
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77, submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows,
            exp_claims=[10, 11],
            exp_builds=[('test-worker2', [10]), ('test-worker1', [11])],
        )

    @defer.inlineCallbacks
    def test_bldr_maybeStartBuild_fails_always(self):
        self.bldr.config.nextWorker = nth_worker(-1)
        # the builder fails to start the build; we'll see that the build
        # was requested, but the brids will get claimed again

        def maybeStartBuild(worker, builds):
            self.startedBuilds.append((worker.name, builds))
            return defer.succeed(False)

        self.bldr.maybeStartBuild = maybeStartBuild

        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [
            *self.base_rows,
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77, submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows,
            # claimed again so none taken!
            exp_claims=[],
            exp_builds=[('test-worker2', [10]), ('test-worker1', [11])],
        )

    @async_to_deferred
    async def test_bldr_maybeStartBuild_fails_once(self):
        self.bldr.config.nextWorker = nth_worker(-1)
        # the builder fails to start the build; we'll see that the build
        # was requested, but the brids will get claimed again
        start_build_results = [False, True, True]

        def maybeStartBuild(worker, builds):
            self.startedBuilds.append((worker.name, builds))
            return defer.succeed(start_build_results.pop(0))

        self.bldr.maybeStartBuild = maybeStartBuild

        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [
            *self.base_rows,
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77, submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
        ]

        await self.master.db.insert_test_data(rows)

        # first time around, only #11 stays claimed
        await self.brd._maybeStartBuildsOnBuilder(self.bldr)
        await self.assert_claims([11])  # claimed again so none taken!
        self.assertBuildsStarted([('test-worker2', [10]), ('test-worker1', [11])])

        # second time around the #10 will pass, adding another request and it
        # is claimed
        await self.brd._maybeStartBuildsOnBuilder(self.bldr)
        await self.assert_claims([10, 11])
        self.assertBuildsStarted([
            ('test-worker2', [10]),
            ('test-worker1', [11]),
            ('test-worker2', [10]),
        ])

    @defer.inlineCallbacks
    def test_limited_by_requests(self):
        self.bldr.config.nextWorker = nth_worker(1)
        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [*self.base_rows, fakedb.BuildRequest(id=11, buildsetid=11, builderid=77)]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows, exp_claims=[11], exp_builds=[('test-worker2', [11])]
        )

    @defer.inlineCallbacks
    def test_nextWorker_None(self):
        self.bldr.config.nextWorker = lambda _1, _2, _3: defer.succeed(None)
        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [*self.base_rows, fakedb.BuildRequest(id=11, buildsetid=11, builderid=77)]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_nextWorker_bogus(self):
        self.bldr.config.nextWorker = lambda _1, _2, _3: defer.succeed(mock.Mock())
        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [*self.base_rows, fakedb.BuildRequest(id=11, buildsetid=11, builderid=77)]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_nextBuild_None(self):
        self.bldr.config.nextBuild = lambda _1, _2: defer.succeed(None)
        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [*self.base_rows, fakedb.BuildRequest(id=11, buildsetid=11, builderid=77)]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_nextBuild_bogus(self):
        self.bldr.config.nextBuild = lambda _1, _2: mock.Mock()
        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [*self.base_rows, fakedb.BuildRequest(id=11, buildsetid=11, builderid=77)]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_nextBuild_fails(self):
        def nextBuildRaises(*args):
            raise RuntimeError("xx")

        self.bldr.config.nextBuild = nextBuildRaises
        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [*self.base_rows, fakedb.BuildRequest(id=11, buildsetid=11, builderid=77)]
        result = self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_claims=[], exp_builds=[])
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
        yield result

    # check concurrency edge cases
    @defer.inlineCallbacks
    def test_claim_race(self):
        self.bldr.config.nextWorker = nth_worker(0)
        # fake a race condition on the buildrequests table
        old_claimBuildRequests = self.master.db.buildrequests.claimBuildRequests

        def claimBuildRequests(brids, claimed_at=None):
            # first, ensure this only happens the first time
            self.master.db.buildrequests.claimBuildRequests = old_claimBuildRequests
            # claim brid 10 for some other master
            assert 10 in brids
            self.master.db.buildrequests._claim_buildrequests_for_master(
                [10], 136000, 9999
            )  # some other masterid
            # ..and fail
            return defer.fail(buildrequests.AlreadyClaimedError())

        self.master.db.buildrequests.claimBuildRequests = claimBuildRequests

        self.addWorkers({'test-worker1': 1, 'test-worker2': 1})
        rows = [
            *self.base_rows,
            fakedb.Master(id=9999),
            fakedb.BuildRequest(
                id=10, buildsetid=11, builderid=77, submitted_at=130000
            ),  # will turn out to be claimed!
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77, submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows, exp_claims=[11], exp_builds=[('test-worker1', [11])]
        )

    # nextWorker
    @defer.inlineCallbacks
    def do_test_nextWorker(self, nextWorker, global_select_next_worker, exp_choice=None):
        if global_select_next_worker:
            self.master.config.select_next_worker = nextWorker
            builder_config = config.BuilderConfig(
                name='bldrconf',
                workernames=['wk1', 'wk2'],
                builddir='bdir',
                factory=factory.BuildFactory(),
            )
        else:
            builder_config = config.BuilderConfig(
                name='bldrconf',
                workernames=['wk1', 'wk2'],
                builddir='bdir',
                factory=factory.BuildFactory(),
                nextWorker=nextWorker,
            )

        self.bldr = yield self.createBuilder('B', builderid=78, builder_config=builder_config)
        for i in range(4):
            self.addWorkers({f'test-worker{i}': 1})

        rows = [
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.SourceStamp(id=21),
            fakedb.Builder(id=78, name='B'),
            fakedb.Buildset(id=12, reason='because'),
            fakedb.BuildsetSourceStamp(sourcestampid=21, buildsetid=12),
            fakedb.BuildRequest(id=12, buildsetid=12, builderid=78),
        ]

        if exp_choice is None:
            exp_claims = []
            exp_builds = []
        else:
            exp_claims = [12]
            exp_builds = [(f'test-worker{exp_choice}', [12])]

        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows, exp_claims=exp_claims, exp_builds=exp_builds
        )

    @parameterized.expand([True, False])
    def test_nextWorker_gets_buildrequest(self, global_select_next_worker):
        def nextWorker(bldr, lst, br=None):
            self.assertNotEqual(br, None)

        return self.do_test_nextWorker(
            nextWorker, global_select_next_worker=global_select_next_worker
        )

    @parameterized.expand([True, False])
    def test_nextWorker_default(self, global_select_next_worker):
        self.patch(random, 'choice', nth_worker(2))
        return self.do_test_nextWorker(
            None, exp_choice=2, global_select_next_worker=global_select_next_worker
        )

    @parameterized.expand([True, False])
    def test_nextWorker_simple(self, global_select_next_worker):
        def nextWorker(bldr, lst, br=None):
            self.assertIdentical(bldr, self.bldr)
            return lst[1]

        return self.do_test_nextWorker(
            nextWorker, global_select_next_worker=global_select_next_worker, exp_choice=1
        )

    @parameterized.expand([True, False])
    def test_nextWorker_deferred(self, global_select_next_worker):
        def nextWorker(bldr, lst, br=None):
            self.assertIdentical(bldr, self.bldr)
            return defer.succeed(lst[1])

        return self.do_test_nextWorker(
            nextWorker, global_select_next_worker=global_select_next_worker, exp_choice=1
        )

    @parameterized.expand([True, False])
    @defer.inlineCallbacks
    def test_nextWorker_exception(self, global_select_next_worker):
        def nextWorker(bldr, lst, br=None):
            raise RuntimeError("")

        yield self.do_test_nextWorker(
            nextWorker, global_select_next_worker=global_select_next_worker
        )
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))

    @parameterized.expand([True, False])
    @defer.inlineCallbacks
    def test_nextWorker_failure(self, global_select_next_worker):
        def nextWorker(bldr, lst, br=None):
            return defer.fail(failure.Failure(RuntimeError()))

        yield self.do_test_nextWorker(
            nextWorker, global_select_next_worker=global_select_next_worker
        )
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))

    # _nextBuild

    @defer.inlineCallbacks
    def do_test_nextBuild(self, nextBuild, exp_choice=None):
        self.bldr.config.nextWorker = nth_worker(-1)
        self.bldr.config.nextBuild = nextBuild

        rows = self.make_workers(4)

        exp_claims = []
        exp_builds = []
        if exp_choice is not None:
            worker = 3
            for choice in exp_choice:
                exp_claims.append(choice)
                exp_builds.append((f'test-worker{worker}', [choice]))
                worker = worker - 1

        yield self.do_test_maybeStartBuildsOnBuilder(
            rows=rows, exp_claims=sorted(exp_claims), exp_builds=exp_builds
        )

    def test_nextBuild_default(self):
        "default chooses the first in the list, which should be the earliest"
        return self.do_test_nextBuild(None, exp_choice=[10, 11, 12, 13])

    def test_nextBuild_simple(self):
        def nextBuild(bldr, lst):
            self.assertIdentical(bldr, self.bldr)
            return lst[-1]

        return self.do_test_nextBuild(nextBuild, exp_choice=[13, 12, 11, 10])

    def test_nextBuild_deferred(self):
        def nextBuild(bldr, lst):
            self.assertIdentical(bldr, self.bldr)
            return defer.succeed(lst[-1])

        return self.do_test_nextBuild(nextBuild, exp_choice=[13, 12, 11, 10])

    def test_nextBuild_exception(self):
        def nextBuild(bldr, lst):
            raise RuntimeError("")

        result = self.do_test_nextBuild(nextBuild)
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
        return result

    def test_nextBuild_failure(self):
        def nextBuild(bldr, lst):
            return defer.fail(failure.Failure(RuntimeError()))

        result = self.do_test_nextBuild(nextBuild)
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
        return result
