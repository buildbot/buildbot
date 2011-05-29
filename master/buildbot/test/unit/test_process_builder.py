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

import mock
import random
from twisted.trial import unittest
from twisted.python import failure
from twisted.internet import defer
from buildbot.test.fake import fakedb, fakemaster
from buildbot.process import builder, buildrequest
from buildbot.db import buildrequests
from buildbot.util import epoch2datetime

class TestBuilderBuildCreation(unittest.TestCase):

    def setUp(self):
        # a collection of rows that would otherwise clutter up every test
        self.base_rows = [
            fakedb.SourceStamp(id=21),
            fakedb.Buildset(id=11, reason='because', sourcestampid=21),
        ]

    def makeBuilder(self, patch_random=False, **config_kwargs):
        """Set up C{self.bldr}"""
        self.bstatus = mock.Mock()
        self.factory = mock.Mock()
        self.master = fakemaster.make_master()
        # only include the necessary required config, plus user-requested
        config = dict(name="bldr", slavename="slv", builddir="bdir",
                     slavebuilddir="sbdir", factory=self.factory)
        config.update(config_kwargs)
        self.bldr = builder.Builder(config, self.bstatus)
        self.master.db = self.db = db = fakedb.FakeDBConnector(self)
        self.master.master_name = db.buildrequests.MASTER_NAME
        self.master.master_incarnation = db.buildrequests.MASTER_INCARNATION
        self.bldr.master = self.master

        # patch into the _startBuildsFor method
        self.builds_started = []
        def _startBuildFor(slavebuilder, buildrequests):
            self.builds_started.append((slavebuilder, buildrequests))
            return defer.succeed(None)
        self.bldr._startBuildFor = _startBuildFor

        if patch_random:
            # patch 'random.choice' to always take the slave that sorts
            # last, based on its name
            self.patch(random, "choice",
                    lambda lst : sorted(lst, key=lambda m : m.name)[-1])

        # we don't want the reclaim service running during tests..
        self.bldr.reclaim_svc.disownServiceParent()

        self.bldr.startService()

    def assertBuildsStarted(self, exp):
        # munge builds_started into a list of (slave, [brids])
        builds_started = [
                (sl.name, [ br.id for br in buildreqs ])
                for (sl, buildreqs) in self.builds_started ]
        self.assertEqual(sorted(builds_started), sorted(exp))

    def setSlaveBuilders(self, slavebuilders):
        """C{slaves} maps name : available"""
        self.bldr.slaves = []
        for name, avail in slavebuilders.iteritems():
            sb = mock.Mock(spec=['isAvailable'], name=name)
            sb.name = name
            sb.isAvailable.return_value = avail
            self.bldr.slaves.append(sb)

    # services

    def test_stopService_flushes(self):
        self.makeBuilder()

        # just check that stopService calls this and waits
        # for the deferred to fire
        events = []

        long_d = defer.Deferred()
        long_d.addCallback(lambda _ : events.append('long_d'))
        self.bldr.maybeStartBuild = lambda : long_d

        stop_d = self.bldr.stopService()
        stop_d.addCallback(lambda _ : events.append('stop_d'))

        # nothing should have happened yet
        self.assertEqual(events, [])

        # finish the maybeStartBuild invocation..
        long_d.callback(None)

        # and then check that things happened in the right order
        def check(_):
            self.assertEqual(events, [ 'long_d', 'stop_d' ])
        stop_d.addCallback(check)

        return stop_d

    # maybeStartBuild

    def do_test_maybeStartBuild(self, rows=[], exp_claims=[], exp_builds=[],
                exp_fail=None):
        d = self.db.insertTestData(rows)
        d.addCallback(lambda _ :
                self.bldr.maybeStartBuild())
        def check(_):
            self.failIf(exp_fail)
            self.db.buildrequests.assertMyClaims(exp_claims)
            self.assertBuildsStarted(exp_builds)
        d.addCallback(check)
        def eb(f):
            f.trap(exp_fail)
        d.addErrback(eb)
        return d

    def test_maybeStartBuild_no_buildreqests(self):
        self.makeBuilder()
        self.setSlaveBuilders({'test-slave11':1})
        return self.do_test_maybeStartBuild(exp_claims=[], exp_builds=[])

    def test_maybeStartBuild_no_slavebuilders(self):
        self.makeBuilder()
        rows = [
            fakedb.BuildRequest(id=11, buildsetid=10, buildername="bldr"),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    def test_maybeStartBuild_limited_by_slaves(self):
        self.makeBuilder(mergeRequests=False)
        self.setSlaveBuilders({'test-slave1':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10], exp_builds=[('test-slave1', [10])])

    def test_maybeStartBuild_limited_by_available_slaves(self):
        self.makeBuilder(mergeRequests=False)
        self.setSlaveBuilders({'test-slave1':0, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10], exp_builds=[('test-slave2', [10])])

    def test_maybeStartBuild_unlimited(self):
        self.makeBuilder(mergeRequests=False, patch_random=True)
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10, 11],
                exp_builds=[('test-slave2', [10]), ('test-slave1', [11])])

    def test_maybeStartBuild_limited_by_requests(self):
        self.makeBuilder(mergeRequests=False, patch_random=True)
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[11], exp_builds=[('test-slave2', [11])])

    def test_maybeStartBuild_chooseSlave_None(self):
        self.makeBuilder()
        self.bldr._chooseSlave = lambda avail : defer.succeed(None)
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    def test_maybeStartBuild_chooseSlave_bogus(self):
        self.makeBuilder()
        self.bldr._chooseSlave = lambda avail : defer.succeed(mock.Mock())
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    def test_maybeStartBuild_chooseSlave_fails(self):
        self.makeBuilder()
        self.bldr._chooseSlave = lambda avail : defer.fail(RuntimeError("xx"))
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[], exp_fail=RuntimeError)

    def test_maybeStartBuild_chooseBuild_None(self):
        self.makeBuilder()
        self.bldr._chooseBuild = lambda reqs : defer.succeed(None)
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    def test_maybeStartBuild_chooseBuild_bogus(self):
        self.makeBuilder()
        self.bldr._chooseBuild = lambda reqs : defer.succeed(mock.Mock())
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    def test_maybeStartBuild_chooseBuild_fails(self):
        self.makeBuilder(patch_random=True)
        self.bldr._chooseBuild = lambda reqs : defer.fail(RuntimeError("xx"))
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[], exp_fail=RuntimeError)

    def test_maybeStartBuild_mergeRequests_fails(self):
        self.makeBuilder(patch_random=True)
        def _mergeRequests(breq, unclaimed_requests, mergeRequests_fn):
            return defer.fail(RuntimeError("xx"))
        self.bldr._mergeRequests = _mergeRequests
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[], exp_fail=RuntimeError)

    def test_maybeStartBuild_claim_race(self):
        self.makeBuilder(patch_random=True)

        # fake a race condition on the buildrequests table
        old_claimBuildRequests = self.db.buildrequests.claimBuildRequests
        def claimBuildRequests(brids):
            # first, ensure this only happens the first time
            self.db.buildrequests.claimBuildRequests = old_claimBuildRequests
            # claim brid 10 for some other master
            assert 10 in brids
            self.db.buildrequests.fakeClaimBuildRequest(10, 136000,
                    master_name="interloper", master_incarnation="interloper")
            # ..and fail
            return defer.fail(buildrequests.AlreadyClaimedError())
        self.db.buildrequests.claimBuildRequests = claimBuildRequests

        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000), # will turn out to be claimed!
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        return self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[11], exp_builds=[('test-slave2', [11])])

    def test_maybeStartBuild_builder_stopped(self):
        self.makeBuilder()

        # this will cause an exception if maybeStartBuild tries to start
        self.bldr.slaves = None

        # so we just hope this does not fail
        d = self.bldr.stopService()
        d.addCallback(lambda _ : self.bldr.maybeStartBuild())
        return d

    # _chooseSlave

    def do_test_chooseSlave(self, nextSlave, exp_choice=None, exp_fail=None):
        self.makeBuilder(nextSlave=nextSlave)
        slavebuilders = [ mock.Mock(name='sb%d' % i) for i in range(4) ]
        d = self.bldr._chooseSlave(slavebuilders)
        def check(sb):
            self.assertIdentical(sb, slavebuilders[exp_choice])
        def failed(f):
            f.trap(exp_fail)
        d.addCallbacks(check, failed)
        return d

    def test_chooseSlave_default(self):
        self.patch(random, "choice", lambda lst : lst[2])
        return self.do_test_chooseSlave(None, exp_choice=2)

    def test_chooseSlave_nextSlave_simple(self):
        def nextSlave(bldr, lst):
            self.assertIdentical(bldr, self.bldr)
            return lst[1]
        return self.do_test_chooseSlave(nextSlave, exp_choice=1)

    def test_chooseSlave_nextSlave_deferred(self):
        def nextSlave(bldr, lst):
            self.assertIdentical(bldr, self.bldr)
            return defer.succeed(lst[1])
        return self.do_test_chooseSlave(nextSlave, exp_choice=1)

    def test_chooseSlave_nextSlave_exception(self):
        def nextSlave(bldr, lst):
            raise RuntimeError
        return self.do_test_chooseSlave(nextSlave, exp_fail=RuntimeError)

    def test_chooseSlave_nextSlave_failure(self):
        def nextSlave(bldr, lst):
            return defer.fail(failure.Failure(RuntimeError()))
        return self.do_test_chooseSlave(nextSlave, exp_fail=RuntimeError)

    # _chooseBuild

    def do_test_chooseBuild(self, nextBuild, exp_choice=None, exp_fail=None):
        self.makeBuilder(nextBuild=nextBuild)
        def mkrq(n):
            brdict = dict(brobj=mock.Mock(name='br%d' % n))
            brdict['brobj'].brdict = brdict
            return brdict
        requests = [ mkrq(i) for i in range(4) ]
        d = self.bldr._chooseBuild(requests)
        def check(sb):
            self.assertIdentical(sb, requests[exp_choice])
        def failed(f):
            f.trap(exp_fail)
        d.addCallbacks(check, failed)
        return d

    def test_chooseBuild_default(self):
        "default chooses the first in the list, which should be the earliest"
        return self.do_test_chooseBuild(None, exp_choice=0)

    def test_chooseBuild_nextBuild_simple(self):
        def nextBuild(bldr, lst):
            self.assertIdentical(bldr, self.bldr)
            return lst[3]
        return self.do_test_chooseBuild(nextBuild, exp_choice=3)

    def test_chooseBuild_nextBuild_deferred(self):
        def nextBuild(bldr, lst):
            self.assertIdentical(bldr, self.bldr)
            return defer.succeed(lst[2])
        return self.do_test_chooseBuild(nextBuild, exp_choice=2)

    def test_chooseBuild_nextBuild_exception(self):
        def nextBuild(bldr, lst):
            raise RuntimeError
        return self.do_test_chooseBuild(nextBuild, exp_fail=RuntimeError)

    def test_chooseBuild_nextBuild_failure(self):
        def nextBuild(bldr, lst):
            return defer.fail(failure.Failure(RuntimeError()))
        return self.do_test_chooseBuild(nextBuild, exp_fail=RuntimeError)

    # _brdictToBuildRequest

    @defer.deferredGenerator
    def test_brdictToBuildRequest(self):
        self.makeBuilder()
        # set up all of the data required for a BuildRequest object
        wfd = defer.waitForDeferred(
            self.db.insertTestData([
                fakedb.SourceStamp(id=234),
                fakedb.Buildset(id=30, sourcestampid=234, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=19, buildsetid=30, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
            ]))
        yield wfd
        wfd.getResult()

        wfd = defer.waitForDeferred(
            self.db.buildrequests.getBuildRequest(19))
        yield wfd
        brdict = wfd.getResult()

        wfd = defer.waitForDeferred(
            self.bldr._brdictToBuildRequest(brdict))
        yield wfd
        br = wfd.getResult()

        # just check that the BuildRequest looks reasonable -
        # test_process_buildrequest checks the whole thing
        self.assertEqual(br.reason, 'foo')

        # and check that the cross-pointers are correct
        self.assertIdentical(br.brdict, brdict)
        self.assertIdentical(brdict['brobj'], br)

        self.bldr._breakBrdictRefloops([brdict])

    # _getMergeRequestsFn

    def do_test_getMergeRequestsFn(self, builder_param, global_param,
                                  expected):
        self.makeBuilder(mergeRequests=builder_param)
        self.master.mergeRequests=global_param
        self.assertEqual(self.bldr._getMergeRequestsFn(), expected)

    def test_getMergeRequestsFn_defaults(self):
        self.do_test_getMergeRequestsFn(None, None,
                buildrequest.BuildRequest.canBeMergedWith)

    def test_getMergeRequestsFn_global_True(self):
        self.do_test_getMergeRequestsFn(None, True,
                buildrequest.BuildRequest.canBeMergedWith)

    def test_getMergeRequestsFn_global_False(self):
        self.do_test_getMergeRequestsFn(None, False, None)

    def test_getMergeRequestsFn_global_function(self):
        function = lambda : None
        self.do_test_getMergeRequestsFn(None, function, function)

    def test_getMergeRequestsFn_builder_True(self):
        self.do_test_getMergeRequestsFn(True, False,
                buildrequest.BuildRequest.canBeMergedWith)

    def test_getMergeRequestsFn_builder_False(self):
        self.do_test_getMergeRequestsFn(False, True, None)

    def test_getMergeRequestsFn_builder_function(self):
        function = lambda : None
        self.do_test_getMergeRequestsFn(function, None, function)

    # _mergeRequests

    @defer.deferredGenerator
    def test_mergeRequests(self):
        self.makeBuilder()
        # set up all of the data required for a BuildRequest object
        wfd = defer.waitForDeferred(
            self.db.insertTestData([
                fakedb.SourceStamp(id=234),
                fakedb.Buildset(id=30, sourcestampid=234, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=19, buildsetid=30, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=20, buildsetid=30, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=21, buildsetid=30, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
            ]))
        yield wfd
        wfd.getResult()

        wfd = defer.waitForDeferred(
            defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (19, 20, 21)
            ]))
        yield wfd
        brdicts = wfd.getResult()

        def mergeRequests_fn(breq, other):
            # merge evens with evens, odds with odds
            return breq.id % 2 == other.id % 2

        # check odds
        wfd = defer.waitForDeferred(
            self.bldr._mergeRequests(brdicts[0], brdicts, mergeRequests_fn))
        yield wfd
        self.assertEqual(wfd.getResult(), [ brdicts[0], brdicts[2] ])

        # check evens
        wfd = defer.waitForDeferred(
            self.bldr._mergeRequests(brdicts[1], brdicts, mergeRequests_fn))
        yield wfd
        self.assertEqual(wfd.getResult(), [ brdicts[1] ])

    def test_mergeRequests_no_merging(self):
        self.makeBuilder()
        breq = dict(dummy=1)
        d = self.bldr._mergeRequests(breq, [ breq, breq ], None)
        def check(res):
            self.assertEqual(res, [breq])
        d.addCallback(check)
        return d

    def test_mergeRequests_singleton_list(self):
        self.makeBuilder()
        breq = dict(dummy=1)
        def is_not_called(*args):
            self.fail("should not be called")
        self.bldr._brdictToBuildRequest = is_not_called
        d = self.bldr._mergeRequests(breq, [ breq ], lambda x,y : None)
        def check(res):
            self.assertEqual(res, [breq])
        d.addCallback(check)
        return d

    # other methods

    def test_reclaimAllBuilds_empty(self):
        # just to be sure this doesn't crash
        self.makeBuilder()
        d = self.bldr.reclaimAllBuilds()
        return d

    def test_reclaimAllBuilds(self):
        self.makeBuilder()

        claims = []
        def fakeClaimBRs(*args):
            claims.append(args)
            return defer.succeed(None)
        self.bldr.master.db.buildrequests.claimBuildRequests = fakeClaimBRs

        def mkbld(brids):
            bld = mock.Mock(name='Build')
            bld.requests = []
            for brid in brids:
                br = mock.Mock(name='BuildRequest %d' % brid)
                br.id = brid
                bld.requests.append(br)
            return bld

        old = mkbld([15]) # keep a reference to the "old" build
        self.bldr.old_building[old] = None
        self.bldr.building.append(mkbld([10,11,12]))

        d = self.bldr.reclaimAllBuilds()
        def check(_):
            self.assertEqual(claims, [ (set([10,11,12,15]),) ])
        d.addCallback(check)
        return d

class TestGetOldestRequestTime(unittest.TestCase):

    def setUp(self):
        # a collection of rows that would otherwise clutter up every test
        self.base_rows = [
            fakedb.SourceStamp(id=21),
            fakedb.Buildset(id=11, reason='because', sourcestampid=21),
            fakedb.BuildRequest(id=111, submitted_at=1000,
                        buildername='bldr1', claimed_at=0, buildsetid=11),
            fakedb.BuildRequest(id=222, submitted_at=2000,
                        buildername='bldr1', claimed_at=2001, buildsetid=11),
            fakedb.BuildRequest(id=333, submitted_at=3000,
                        buildername='bldr1', claimed_at=0, buildsetid=11),
            fakedb.BuildRequest(id=444, submitted_at=2500,
                        buildername='bldr2', claimed_at=2501, buildsetid=11),
        ]

    def makeBuilder(self, name):
        self.bstatus = mock.Mock()
        self.factory = mock.Mock()
        self.master = mock.Mock()
        # only include the necessary required config
        config = dict(name=name, slavename="slv", builddir="bdir",
                     slavebuilddir="sbdir", factory=self.factory)
        self.bldr = builder.Builder(config, self.bstatus)
        self.master.db = self.db = db = fakedb.FakeDBConnector(self)
        self.master.master_name = db.buildrequests.MASTER_NAME
        self.master.master_incarnation = db.buildrequests.MASTER_INCARNATION
        self.bldr.master = self.master

        # we don't want the reclaim service running during tests..
        self.bldr.reclaim_svc.disownServiceParent()

        self.bldr.startService()

    def test_gort_unclaimed(self):
        self.makeBuilder(name='bldr1')
        d = self.db.insertTestData(self.base_rows)
        d.addCallback(lambda _ : self.bldr.getOldestRequestTime())
        def check(rqtime):
            self.assertEqual(rqtime, epoch2datetime(1000))
        d.addCallback(check)
        return d

    def test_gort_all_claimed(self):
        self.makeBuilder(name='bldr2')
        d = self.db.insertTestData(self.base_rows)
        d.addCallback(lambda _ : self.bldr.getOldestRequestTime())
        def check(rqtime):
            self.assertEqual(rqtime, None)
        d.addCallback(check)
        return d

