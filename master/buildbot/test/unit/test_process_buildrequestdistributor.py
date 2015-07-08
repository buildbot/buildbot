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
from future.utils import iteritems

import mock

from buildbot.db import buildrequests
from buildbot.process import buildrequestdistributor
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.util import epoch2datetime
from buildbot.util.eventual import fireEventually
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest


def nth_slave(n):
    def pick_nth_by_name(builder, slaves=None, br=None):
        if slaves is None:
            slaves = builder
        slaves = slaves[:]
        slaves.sort(cmp=lambda a, b: cmp(a.name, b.name))
        return slaves[n]
    return pick_nth_by_name


class SkipSlavesThatCantGetLock(buildrequestdistributor.BasicBuildChooser):

    """This class disables the 'rejectedSlaves' feature"""

    def __init__(self, *args, **kwargs):
        buildrequestdistributor.BasicBuildChooser.__init__(self, *args, **kwargs)
        self.rejectedSlaves = None  # disable this feature


class TestBRDBase(unittest.TestCase):

    def setUp(self):
        self.botmaster = mock.Mock(name='botmaster')
        self.botmaster.builders = {}
        self.builders = {}

        def prioritizeBuilders(master, builders):
            # simple sort-by-name by default
            return sorted(builders, lambda b1, b2: cmp(b1.name, b2.name))
        self.master = self.botmaster.master = fakemaster.make_master(testcase=self,
                                                                     wantData=True, wantDb=True)
        self.master.caches = fakemaster.FakeCaches()
        self.master.config.prioritizeBuilders = prioritizeBuilders
        self.brd = buildrequestdistributor.BuildRequestDistributor(self.botmaster)
        self.brd.parent = self.botmaster
        self.brd.startService()

        # TODO: this is a terrible way to detect the "end" of the test -
        # it regularly completes too early after a simple modification of
        # a test.  Is there a better way?
        self.quiet_deferred = defer.Deferred()

        def _quiet():
            if self.quiet_deferred:
                d, self.quiet_deferred = self.quiet_deferred, None
                d.callback(None)
            else:
                self.fail("loop has already gone quiet once")
        self.brd._quiet = _quiet

        # a collection of rows that would otherwise clutter up every test
        self.base_rows = [
            fakedb.SourceStamp(id=21),
            fakedb.Builder(id=77, name='A'),
            fakedb.Buildset(id=11, reason='because'),
            fakedb.BuildsetSourceStamp(sourcestampid=21, buildsetid=11),
        ]

    def tearDown(self):
        if self.brd.running:
            return self.brd.stopService()

    def make_slaves(self, slave_count):
        rows = self.base_rows[:]
        for i in range(slave_count):
            self.addSlaves({'test-slave%d' % i: 1})
            rows.append(fakedb.Buildset(id=100 + i, reason='because'))
            rows.append(fakedb.BuildsetSourceStamp(buildsetid=100 + i, sourcestampid=21))
            rows.append(fakedb.BuildRequest(id=10 + i, buildsetid=100 + i, builderid=77))
        return rows

    def addSlaves(self, slavebuilders):
        """C{slaves} maps name : available"""
        for name, avail in iteritems(slavebuilders):
            sb = mock.Mock(spec=['isAvailable'], name=name)
            sb.name = name
            sb.isAvailable.return_value = avail
            for bldr in self.builders.values():
                bldr.slaves.append(sb)

    @defer.inlineCallbacks
    def createBuilder(self, name, builderid=None):
        if builderid is None:
            b = fakedb.Builder(name=name)
            yield self.master.db.insertTestData([b])
            builderid = b.id

        bldr = mock.Mock(name=name)
        bldr.name = name
        self.botmaster.builders[name] = bldr
        self.builders[name] = bldr

        def maybeStartBuild(slave, builds):
            self.startedBuilds.append((slave.name, builds))
            d = defer.Deferred()
            reactor.callLater(0, d.callback, True)
            return d
        bldr.maybeStartBuild = maybeStartBuild
        bldr.canStartWithSlavebuilder = lambda _: True
        bldr.getCollapseRequestsFn = lambda: False

        bldr.slaves = []
        bldr.getAvailableSlaves = lambda: [s for s in bldr.slaves if s.isAvailable()]
        bldr.getBuilderId = lambda: (builderid)
        bldr.config.nextSlave = None
        bldr.config.nextBuild = None

        def canStartBuild(*args):
            can = bldr.config.canStartBuild
            return not can or can(*args)
        bldr.canStartBuild = canStartBuild

        defer.returnValue(bldr)

    @defer.inlineCallbacks
    def addBuilders(self, names):
        self.startedBuilds = []

        for name in names:
            yield self.createBuilder(name)

    def assertMyClaims(self, brids):
        self.assertEqual(self.master.data.updates.claimedBuildRequests,
                         set(brids))


class Test(TestBRDBase):

    def checkAllCleanedUp(self):
        # check that the BRD didnt end with a stuck lock or in the 'active' state (which would mean
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

    def test_maybeStartBuildsOn_simple(self):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['bldr1'])
        self.brd.maybeStartBuildsOn(['bldr1'])

        def check(_):
            self.assertEqual(self.maybeStartBuildsOnBuilder_calls, ['bldr1'])
            self.checkAllCleanedUp()
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    def test_maybeStartBuildsOn_parallel(self):
        # test 15 "parallel" invocations of maybeStartBuildsOn, with a
        # _sortBuilders that takes a while.  This is a regression test for bug
        # 1979.
        builders = ['bldr%02d' % i for i in xrange(15)]

        def slow_sorter(master, bldrs):
            bldrs.sort(lambda b1, b2: cmp(b1.name, b2.name))
            d = defer.Deferred()
            reactor.callLater(0, d.callback, bldrs)

            def done(_):
                return _
            d.addCallback(done)
            return d
        self.master.config.prioritizeBuilders = slow_sorter

        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(builders)
        for bldr in builders:
            self.brd.maybeStartBuildsOn([bldr])

        def check(_):
            self.assertEqual(self.maybeStartBuildsOnBuilder_calls, builders)
            self.checkAllCleanedUp()
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    def test_maybeStartBuildsOn_exception(self):
        self.addBuilders(['bldr1'])

        def _maybeStartBuildsOnBuilder(n):
            # fail slowly, so that the activity loop doesn't go quiet too soon
            d = defer.Deferred()
            reactor.callLater(0,
                              d.errback, failure.Failure(RuntimeError("oh noes")))
            return d
        self.brd._maybeStartBuildsOnBuilder = _maybeStartBuildsOnBuilder

        self.brd.maybeStartBuildsOn(['bldr1'])

        def check(_):
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
            self.checkAllCleanedUp()
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    def test_maybeStartBuildsOn_collapsing(self):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['bldr1', 'bldr2', 'bldr3'])
        self.brd.maybeStartBuildsOn(['bldr3'])
        self.brd.maybeStartBuildsOn(['bldr2', 'bldr1'])
        self.brd.maybeStartBuildsOn(['bldr4'])  # should be ignored
        self.brd.maybeStartBuildsOn(['bldr2'])  # already queued - ignored
        self.brd.maybeStartBuildsOn(['bldr3', 'bldr2'])

        def check(_):
            # bldr3 gets invoked twice, since it's considered to have started
            # already when the first call to maybeStartBuildsOn returns
            self.assertEqual(self.maybeStartBuildsOnBuilder_calls,
                             ['bldr3', 'bldr1', 'bldr2', 'bldr3'])
            self.checkAllCleanedUp()
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    def test_maybeStartBuildsOn_builders_missing(self):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['bldr1', 'bldr2', 'bldr3'])
        self.brd.maybeStartBuildsOn(['bldr1', 'bldr2', 'bldr3'])
        # bldr1 is already run, so surreptitiously remove the other
        # two - nothing should crash, but the builders should not run
        self.removeBuilder('bldr2')
        self.removeBuilder('bldr3')

        def check(_):
            self.assertEqual(self.maybeStartBuildsOnBuilder_calls, ['bldr1'])
            self.checkAllCleanedUp()
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    def do_test_sortBuilders(self, prioritizeBuilders, oldestRequestTimes,
                             expected, returnDeferred=False):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(list(oldestRequestTimes))
        self.master.config.prioritizeBuilders = prioritizeBuilders

        def mklambda(t):  # work around variable-binding issues
            if returnDeferred:
                return lambda: defer.succeed(t)
            else:
                return lambda: t

        for n, t in iteritems(oldestRequestTimes):
            if t is not None:
                t = epoch2datetime(t)
            self.builders[n].getOldestRequestTime = mklambda(t)

        d = self.brd._sortBuilders(list(oldestRequestTimes))

        def check(result):
            self.assertEqual(result, expected)
            self.checkAllCleanedUp()
        d.addCallback(check)
        return d

    def test_sortBuilders_default_sync(self):
        return self.do_test_sortBuilders(None,  # use the default sort
                                         dict(bldr1=777, bldr2=999, bldr3=888),
                                         ['bldr1', 'bldr3', 'bldr2'])

    def test_sortBuilders_default_asyn(self):
        return self.do_test_sortBuilders(None,  # use the default sort
                                         dict(bldr1=777, bldr2=999, bldr3=888),
                                         ['bldr1', 'bldr3', 'bldr2'],
                                         returnDeferred=True)

    def test_sortBuilders_default_None(self):
        return self.do_test_sortBuilders(None,  # use the default sort
                                         dict(bldr1=777, bldr2=None, bldr3=888),
                                         ['bldr1', 'bldr3', 'bldr2'])

    def test_sortBuilders_custom(self):
        def prioritizeBuilders(master, builders):
            self.assertIdentical(master, self.master)
            return sorted(builders, key=lambda b: b.name)

        return self.do_test_sortBuilders(prioritizeBuilders,
                                         dict(bldr1=1, bldr2=1, bldr3=1),
                                         ['bldr1', 'bldr2', 'bldr3'])

    def test_sortBuilders_custom_async(self):
        def prioritizeBuilders(master, builders):
            self.assertIdentical(master, self.master)
            return defer.succeed(sorted(builders, key=lambda b: b.name))

        return self.do_test_sortBuilders(prioritizeBuilders,
                                         dict(bldr1=1, bldr2=1, bldr3=1),
                                         ['bldr1', 'bldr2', 'bldr3'])

    def test_sortBuilders_custom_exception(self):
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['x', 'y'])

        def fail(m, b):
            raise RuntimeError("oh noes")
        self.master.config.prioritizeBuilders = fail

        # expect to get the builders back in the same order in the event of an
        # exception
        d = self.brd._sortBuilders(['y', 'x'])

        def check(result):
            self.assertEqual(result, ['y', 'x'])

            # and expect the exception to be logged
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        d.addCallback(check)
        return d

    def test_stopService(self):
        # check that stopService waits for a builder run to complete, but does not
        # allow a subsequent run to start
        self.useMock_maybeStartBuildsOnBuilder()
        self.addBuilders(['A', 'B'])

        oldMSBOB = self.brd._maybeStartBuildsOnBuilder

        def maybeStartBuildsOnBuilder(bldr):
            d = oldMSBOB(bldr)

            stop_d = self.brd.stopService()
            stop_d.addCallback(lambda _:
                               self.maybeStartBuildsOnBuilder_calls.append('(stopped)'))

            d.addCallback(lambda _:
                          self.maybeStartBuildsOnBuilder_calls.append('finished'))
            return d
        self.brd._maybeStartBuildsOnBuilder = maybeStartBuildsOnBuilder

        # start both builds; A should start and complete *before* the service stops,
        # and B should not run.
        self.brd.maybeStartBuildsOn(['A', 'B'])

        def check(_):
            self.assertEqual(self.maybeStartBuildsOnBuilder_calls,
                             ['A', 'finished', '(stopped)'])
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred


class TestMaybeStartBuilds(TestBRDBase):

    @defer.inlineCallbacks
    def setUp(self):
        TestBRDBase.setUp(self)

        self.startedBuilds = []

        self.bldr = yield self.createBuilder('A', builderid=77)
        self.builders['A'] = self.bldr

    def assertBuildsStarted(self, exp):
        # munge builds_started into (slave, [brids])
        builds_started = [
            (slave, [br.id for br in breqs])
            for (slave, breqs) in self.startedBuilds]
        self.assertEqual(builds_started, exp)

    # _maybeStartBuildsOnBuilder

    @defer.inlineCallbacks
    def do_test_maybeStartBuildsOnBuilder(self, rows=None, exp_claims=None, exp_builds=None):
        rows = rows or []
        exp_claims = exp_claims or []
        exp_builds = exp_builds or []
        yield self.master.db.insertTestData(rows)

        yield self.brd._maybeStartBuildsOnBuilder(self.bldr)

        self.assertMyClaims(exp_claims)
        self.assertBuildsStarted(exp_builds)

    @defer.inlineCallbacks
    def test_no_buildreqests(self):
        self.addSlaves({'test-slave11': 1})
        yield self.do_test_maybeStartBuildsOnBuilder(exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_no_slavebuilders(self):
        rows = [
            fakedb.Builder(id=78, name='bldr'),
            fakedb.BuildRequest(id=11, buildsetid=10, builderid=78),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_limited_by_slaves(self):
        self.addSlaves({'test-slave1': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[10], exp_builds=[('test-slave1', [10])])

    @defer.inlineCallbacks
    def test_sorted_by_submit_time(self):
        # same as "limited_by_slaves" but with rows swapped
        self.addSlaves({'test-slave1': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[10], exp_builds=[('test-slave1', [10])])

    @defer.inlineCallbacks
    def test_limited_by_available_slaves(self):
        self.addSlaves({'test-slave1': 0, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[10], exp_builds=[('test-slave2', [10])])

    @defer.inlineCallbacks
    def test_slow_db(self):
        # test what happens if the "getBuildRequests" fetch takes a "long time"
        self.addSlaves({'test-slave1': 1})

        # wrap to simulate a "long" db access
        old_getBuildRequests = self.master.db.buildrequests.getBuildRequests

        def longGetBuildRequests(*args, **kwargs):
            res_d = old_getBuildRequests(*args, **kwargs)
            long_d = defer.Deferred()
            long_d.addCallback(lambda _: res_d)
            reactor.callLater(0, long_d.callback, None)
            return long_d
        self.master.db.buildrequests.getBuildRequests = longGetBuildRequests

        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[10], exp_builds=[('test-slave1', [10])])

    @defer.inlineCallbacks
    def test_limited_by_canStartBuild(self):
        """Set the 'canStartBuild' value in the config to something
        that limits the possible options."""

        self.bldr.config.nextSlave = nth_slave(-1)

        slaves_attempted = []

        def _canStartWithSlavebuilder(slavebuilder):
            slaves_attempted.append(slavebuilder.name)
            return True
        self.bldr.canStartWithSlavebuilder = _canStartWithSlavebuilder

        pairs_tested = []

        def _canStartBuild(slave, breq):
            result = (slave.name, breq.id)
            pairs_tested.append(result)
            allowed = [
                ("test-slave1", 10),
                ("test-slave3", 11),
            ]
            return result in allowed
        self.bldr.config.canStartBuild = _canStartBuild

        self.addSlaves({'test-slave1': 1, 'test-slave2': 1, 'test-slave3': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
            fakedb.BuildRequest(id=12, buildsetid=11, builderid=77,
                                submitted_at=140000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[10, 11], exp_builds=[('test-slave1', [10]), ('test-slave3', [11])])

        self.assertEqual(slaves_attempted, ['test-slave3', 'test-slave2', 'test-slave1'])

        # we expect brids in order (10-11-12),
        # with each searched in reverse order of slaves (3-2-1) available (due to nth_slave(-1))
        self.assertEqual(pairs_tested, [
            ('test-slave3', 10),
            ('test-slave2', 10),
            ('test-slave1', 10),
            ('test-slave3', 11),
            ('test-slave2', 12)])

    @mock.patch('buildbot.process.buildrequestdistributor.BuildRequestDistributor.BuildChooser', SkipSlavesThatCantGetLock)
    @defer.inlineCallbacks
    def test_limited_by_canStartBuild_deferreds(self):
        """Another variant that:
         * returns Deferred types,
         * use 'canStartWithSlavebuilder' to reject one of the slaves
         * patch using SkipSlavesThatCantGetLock to disable the 'rejectedSlaves' feature"""

        self.bldr.config.nextSlave = nth_slave(-1)

        slaves_attempted = []

        def _canStartWithSlavebuilder(slavebuilder):
            slaves_attempted.append(slavebuilder.name)
            allowed = slavebuilder.name in ['test-slave2', 'test-slave1']
            return defer.succeed(allowed)   # a deferred here!
        self.bldr.canStartWithSlavebuilder = _canStartWithSlavebuilder

        pairs_tested = []

        def _canStartBuild(slave, breq):
            result = (slave.name, breq.id)
            pairs_tested.append(result)
            allowed = [
                ("test-slave1", 10),
                ("test-slave3", 11),
            ]
            return defer.succeed(result in allowed)
        self.bldr.config.canStartBuild = _canStartBuild

        self.addSlaves({'test-slave1': 1, 'test-slave2': 1, 'test-slave3': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
            fakedb.BuildRequest(id=12, buildsetid=11, builderid=77,
                                submitted_at=140000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[10], exp_builds=[('test-slave1', [10])])

        self.assertEqual(slaves_attempted, ['test-slave3', 'test-slave2', 'test-slave1'])

        # we expect brids in order (10-11-12),
        # with slave3 skipped, and slave2 unable to pair
        self.assertEqual(pairs_tested, [
            ('test-slave2', 10),
            ('test-slave1', 10),
            ('test-slave2', 11),
            ('test-slave2', 12)])

    @defer.inlineCallbacks
    def test_limited_by_canStartWithSlavebuilder(self):
        self.bldr.config.nextSlave = nth_slave(-1)

        slaves_attempted = []

        def _canStartWithSlavebuilder(slavebuilder):
            slaves_attempted.append(slavebuilder.name)
            return (slavebuilder.name == 'test-slave3')
        self.bldr.canStartWithSlavebuilder = _canStartWithSlavebuilder
        self.addSlaves({'test-slave1': 0, 'test-slave2': 1, 'test-slave3': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[10, 11], exp_builds=[('test-slave3', [10]), ('test-slave2', [11])])

        self.assertEqual(slaves_attempted, ['test-slave3', 'test-slave2'])

    @defer.inlineCallbacks
    def test_unlimited(self):
        self.bldr.config.nextSlave = nth_slave(-1)
        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[10, 11],
                                                     exp_builds=[('test-slave2', [10]), ('test-slave1', [11])])

    @defer.inlineCallbacks
    def test_bldr_maybeStartBuild_fails_always(self):
        self.bldr.config.nextSlave = nth_slave(-1)
        # the builder fails to start the build; we'll see that the build
        # was requested, but the brids will get reclaimed

        def maybeStartBuild(slave, builds):
            self.startedBuilds.append((slave.name, builds))
            return defer.succeed(False)
        self.bldr.maybeStartBuild = maybeStartBuild

        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[],  # reclaimed so none taken!
                                                     exp_builds=[('test-slave2', [10]), ('test-slave1', [11])])

    @defer.inlineCallbacks
    def test_bldr_maybeStartBuild_fails_once(self):
        self.bldr.config.nextSlave = nth_slave(-1)
        # the builder fails to start the build; we'll see that the build
        # was requested, but the brids will get reclaimed

        def maybeStartBuild(slave, builds, _fail=[False]):
            self.startedBuilds.append((slave.name, builds))
            ret = _fail[0]
            _fail[0] = True
            return defer.succeed(ret)
        self.bldr.maybeStartBuild = maybeStartBuild

        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
        ]

        yield self.master.db.insertTestData(rows)

        # first time around, only #11 stays claimed
        yield self.brd._maybeStartBuildsOnBuilder(self.bldr)
        self.assertMyClaims([11])  # reclaimed so none taken!
        self.assertBuildsStarted([('test-slave2', [10]), ('test-slave1', [11])])

        # second time around the #10 will pass, adding another request and it is claimed
        yield self.brd._maybeStartBuildsOnBuilder(self.bldr)
        self.assertMyClaims([10, 11])
        self.assertBuildsStarted([('test-slave2', [10]), ('test-slave1', [11]), ('test-slave2', [10])])

    @defer.inlineCallbacks
    def test_limited_by_requests(self):
        self.bldr.config.nextSlave = nth_slave(1)
        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[11], exp_builds=[('test-slave2', [11])])

    @defer.inlineCallbacks
    def test_nextSlave_None(self):
        self.bldr.config.nextSlave = lambda _1, _2: defer.succeed(None)
        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_nextSlave_bogus(self):
        self.bldr.config.nextSlave = lambda _1, _2: defer.succeed(mock.Mock())
        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_nextSlave_fails(self):
        def nextSlaveRaises(*args):
            raise RuntimeError("xx")
        self.bldr.config.nextSlave = nextSlaveRaises
        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_nextBuild_None(self):
        self.bldr.config.nextBuild = lambda _1, _2: defer.succeed(None)
        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_nextBuild_bogus(self):
        self.bldr.config.nextBuild = lambda _1, _2: mock.Mock()
        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_nextBuild_fails(self):
        def nextBuildRaises(*args):
            raise RuntimeError("xx")
        self.bldr.config.nextBuild = nextBuildRaises
        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77),
        ]
        result = self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                        exp_claims=[], exp_builds=[])
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
        yield result

    # check concurrency edge cases
    @defer.inlineCallbacks
    def test_claim_race(self):
        self.bldr.config.nextSlave = nth_slave(0)
        # fake a race condition on the buildrequests table
        old_claimBuildRequests = self.master.db.buildrequests.claimBuildRequests

        def claimBuildRequests(brids, claimed_at=None, _reactor=None):
            # first, ensure this only happens the first time
            self.master.db.buildrequests.claimBuildRequests = old_claimBuildRequests
            # claim brid 10 for some other master
            assert 10 in brids
            self.master.db.buildrequests.fakeClaimBuildRequest(10, 136000,
                                                               masterid=9999)  # some other masterid
            # ..and fail
            return defer.fail(buildrequests.AlreadyClaimedError())
        self.master.db.buildrequests.claimBuildRequests = claimBuildRequests

        self.addSlaves({'test-slave1': 1, 'test-slave2': 1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, builderid=77,
                                submitted_at=130000),  # will turn out to be claimed!
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77,
                                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=[11], exp_builds=[('test-slave1', [11])])

    # nextSlave
    @defer.inlineCallbacks
    def do_test_nextSlave(self, nextSlave, exp_choice=None):
        rows = self.make_slaves(4)

        self.bldr.config.nextSlave = nextSlave
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, builderid=77),
        ]

        if exp_choice is None:
            exp_claims = []
            exp_builds = []
        else:
            exp_claims = [11]
            exp_builds = [('test-slave%d' % exp_choice, [11])]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=exp_claims, exp_builds=exp_builds)

    def test_nextSlave_gets_buildrequest(self):
        def nextSlave(bldr, lst, br=None):
            self.assertNotEqual(br, None)
        return self.do_test_nextSlave(nextSlave)

    def test_nextSlave_2args_in_signature(self):
        def nextSlave(builder, lst):
            return lst[0] if lst else None
        return self.do_test_nextSlave(nextSlave)

    def test_nextSlave_default(self):
        import random
        self.patch(random, 'choice', nth_slave(2))
        return self.do_test_nextSlave(None, exp_choice=2)

    def test_nextSlave_simple(self):
        def nextSlave(bldr, lst, br=None):
            self.assertIdentical(bldr, self.bldr)
            return lst[1]
        return self.do_test_nextSlave(nextSlave, exp_choice=1)

    def test_nextSlave_deferred(self):
        def nextSlave(bldr, lst, br=None):
            self.assertIdentical(bldr, self.bldr)
            return defer.succeed(lst[1])
        return self.do_test_nextSlave(nextSlave, exp_choice=1)

    def test_nextSlave_exception(self):
        def nextSlave(bldr, lst):
            raise RuntimeError("")
        return self.do_test_nextSlave(nextSlave)

    def test_nextSlave_failure(self):
        def nextSlave(bldr, lst):
            return defer.fail(failure.Failure(RuntimeError()))
        return self.do_test_nextSlave(nextSlave)

    # _nextBuild

    @defer.inlineCallbacks
    def do_test_nextBuild(self, nextBuild, exp_choice=None):
        self.bldr.config.nextSlave = nth_slave(-1)
        self.bldr.config.nextBuild = nextBuild

        rows = self.make_slaves(4)

        exp_claims = []
        exp_builds = []
        if exp_choice is not None:
            slave = 3
            for choice in exp_choice:
                exp_claims.append(choice)
                exp_builds.append(('test-slave%d' % slave, [choice]))
                slave = slave - 1

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                                                     exp_claims=sorted(exp_claims), exp_builds=exp_builds)

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
