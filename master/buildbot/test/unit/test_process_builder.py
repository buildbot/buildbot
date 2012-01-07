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
from buildbot import config
from buildbot.test.fake import fakedb, fakemaster
from buildbot.process import builder
from buildbot.db import buildrequests
from buildbot.util import epoch2datetime

class TestBuilderBuildCreation(unittest.TestCase):

    def setUp(self):
        # a collection of rows that would otherwise clutter up every test
        self.base_rows = [
            fakedb.SourceStampSet(id=21),
            fakedb.SourceStamp(id=21, sourcestampsetid=21),
            fakedb.Buildset(id=11, reason='because', sourcestampsetid=21),
        ]

    def makeBuilder(self, patch_random=False, **config_kwargs):
        """Set up C{self.bldr}"""
        self.bstatus = mock.Mock()
        self.factory = mock.Mock()
        self.master = fakemaster.make_master()
        # only include the necessary required config, plus user-requested
        config_args = dict(name="bldr", slavename="slv", builddir="bdir",
                     slavebuilddir="sbdir", factory=self.factory)
        config_args.update(config_kwargs)
        builder_config = config.BuilderConfig(**config_args)
        self.bldr = builder.Builder(builder_config.name)
        self.master.db = self.db = fakedb.FakeDBConnector(self)
        self.bldr.master = self.master
        self.bldr.botmaster = self.master.botmaster

        # patch into the _startBuildsFor method
        self.builds_started = []
        def _startBuildFor(slavebuilder, buildrequests):
            self.builds_started.append((slavebuilder, buildrequests))
            return defer.succeed(True)
        self.bldr._startBuildFor = _startBuildFor

        if patch_random:
            # patch 'random.choice' to always take the slave that sorts
            # last, based on its name
            self.patch(random, "choice",
                    lambda lst : sorted(lst, key=lambda m : m.name)[-1])

        # we don't want the reclaim service running during tests..
        self.bldr.reclaim_svc.disownServiceParent()

        self.bldr.startService()

        mastercfg = config.MasterConfig()
        mastercfg.builders = [ builder_config ]
        return self.bldr.reconfigService(mastercfg)

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

    @defer.deferredGenerator
    def test_stopService_flushes(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

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

        wfd = defer.waitForDeferred(stop_d)
        yield wfd
        wfd.getResult()

        # and then check that things happened in the right order
        self.assertEqual(events, [ 'long_d', 'stop_d' ])

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

    @defer.deferredGenerator
    def test_maybeStartBuild_no_buildreqests(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        self.setSlaveBuilders({'test-slave11':1})

        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(exp_claims=[], exp_builds=[]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_no_slavebuilders(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        rows = [
            fakedb.BuildRequest(id=11, buildsetid=10, buildername="bldr"),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_limited_by_slaves(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder(mergeRequests=False))
        yield wfd
        wfd.getResult()

        self.setSlaveBuilders({'test-slave1':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10], exp_builds=[('test-slave1', [10])]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_limited_by_available_slaves(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder(mergeRequests=False))
        yield wfd
        wfd.getResult()

        self.setSlaveBuilders({'test-slave1':0, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10], exp_builds=[('test-slave2', [10])]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_unlimited(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder(mergeRequests=False, patch_random=True))
        yield wfd
        wfd.getResult()

        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10, 11],
                exp_builds=[('test-slave2', [10]), ('test-slave1', [11])]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_limited_by_requests(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder(mergeRequests=False, patch_random=True))
        yield wfd
        wfd.getResult()

        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[11], exp_builds=[('test-slave2', [11])]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_chooseSlave_None(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        self.bldr._chooseSlave = lambda avail : defer.succeed(None)
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_chooseSlave_bogus(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        self.bldr._chooseSlave = lambda avail : defer.succeed(mock.Mock())
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_chooseSlave_fails(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        self.bldr._chooseSlave = lambda avail : defer.fail(RuntimeError("xx"))
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[], exp_fail=RuntimeError))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_chooseBuild_None(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        self.bldr._chooseBuild = lambda reqs : defer.succeed(None)
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_chooseBuild_bogus(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        self.bldr._chooseBuild = lambda reqs : defer.succeed(mock.Mock())
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_chooseBuild_fails(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder(patch_random=True))
        yield wfd
        wfd.getResult()

        self.bldr._chooseBuild = lambda reqs : defer.fail(RuntimeError("xx"))
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[], exp_fail=RuntimeError))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_mergeRequests_fails(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder(patch_random=True))
        yield wfd
        wfd.getResult()

        def _mergeRequests(breq, unclaimed_requests, mergeRequests_fn):
            return defer.fail(RuntimeError("xx"))
        self.bldr._mergeRequests = _mergeRequests
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[], exp_fail=RuntimeError))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_claim_race(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder(patch_random=True))
        yield wfd
        wfd.getResult()

        # fake a race condition on the buildrequests table
        old_claimBuildRequests = self.db.buildrequests.claimBuildRequests
        def claimBuildRequests(brids):
            # first, ensure this only happens the first time
            self.db.buildrequests.claimBuildRequests = old_claimBuildRequests
            # claim brid 10 for some other master
            assert 10 in brids
            self.db.buildrequests.fakeClaimBuildRequest(10, 136000,
                    objectid=9999) # some other objectid
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
        wfd = defer.waitForDeferred(
            self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[11], exp_builds=[('test-slave2', [11])]))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_maybeStartBuild_builder_stopped(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        # this will cause an exception if maybeStartBuild tries to start
        self.bldr.slaves = None

        # so we just hope this does not fail
        wfd = defer.waitForDeferred(
            self.bldr.stopService())
        yield wfd
        wfd.getResult()

        wfd = defer.waitForDeferred(
            self.bldr.maybeStartBuild())
        yield wfd
        wfd.getResult()

    # _chooseSlave

    def do_test_chooseSlave(self, nextSlave, exp_choice=None, exp_fail=None):
        slavebuilders = [ mock.Mock(name='sb%d' % i) for i in range(4) ]

        d = self.makeBuilder(nextSlave=nextSlave)
        d.addCallback(lambda _ : self.bldr._chooseSlave(slavebuilders))
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

        def mkrq(n):
            brdict = dict(brobj=mock.Mock(name='br%d' % n))
            brdict['brobj'].brdict = brdict
            return brdict
        requests = [ mkrq(i) for i in range(4) ]

        d = self.makeBuilder(nextBuild=nextBuild)
        d.addCallback(lambda _ : self.bldr._chooseBuild(requests))
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
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        # set up all of the data required for a BuildRequest object
        wfd = defer.waitForDeferred(
            self.db.insertTestData([
                fakedb.SourceStampSet(id=234),
                fakedb.SourceStamp(id=234,sourcestampsetid=234),
                fakedb.Buildset(id=30, sourcestampsetid=234, reason='foo',
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

    @defer.deferredGenerator
    def do_test_getMergeRequestsFn(self, builder_param=None,
                    global_param=None, expected=0):
        cble = lambda : None
        builder_param = builder_param == 'callable' and cble or builder_param
        global_param = global_param == 'callable' and cble or global_param

        # omit the constructor parameter if None was given
        if builder_param is None:
            wfd = defer.waitForDeferred(
                self.makeBuilder())
            yield wfd
            wfd.getResult()
        else:
            wfd = defer.waitForDeferred(
                self.makeBuilder(mergeRequests=builder_param))
            yield wfd
            wfd.getResult()

        self.master.config.mergeRequests = global_param

        fn = self.bldr._getMergeRequestsFn()

        if fn == builder.Builder._defaultMergeRequestFn:
            fn = "default"
        elif fn is cble:
            fn = 'callable'
        self.assertEqual(fn, expected)

    def test_getMergeRequestsFn_defaults(self):
        self.do_test_getMergeRequestsFn(None, None, "default")

    def test_getMergeRequestsFn_global_True(self):
        self.do_test_getMergeRequestsFn(None, True, "default")

    def test_getMergeRequestsFn_global_False(self):
        self.do_test_getMergeRequestsFn(None, False, None)

    def test_getMergeRequestsFn_global_function(self):
        self.do_test_getMergeRequestsFn(None, 'callable', 'callable')

    def test_getMergeRequestsFn_builder_True(self):
        self.do_test_getMergeRequestsFn(True, False, "default")

    def test_getMergeRequestsFn_builder_False(self):
        self.do_test_getMergeRequestsFn(False, True, None)

    def test_getMergeRequestsFn_builder_function(self):
        self.do_test_getMergeRequestsFn('callable', None, 'callable')

    # _mergeRequests

    @defer.deferredGenerator
    def test_mergeRequests(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        # set up all of the data required for a BuildRequest object
        wfd = defer.waitForDeferred(
            self.db.insertTestData([
                fakedb.SourceStampSet(id=234),
                fakedb.SourceStamp(id=234, sourcestampsetid=234),
                fakedb.Buildset(id=30, sourcestampsetid=234, reason='foo',
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

        def mergeRequests_fn(builder, breq, other):
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

    @defer.deferredGenerator
    def test_mergeRequests_no_merging(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        breq = dict(dummy=1)
        wfd = defer.waitForDeferred(
            self.bldr._mergeRequests(breq, [ breq, breq ], None))
        yield wfd
        merged = wfd.getResult()

        self.assertEqual(merged, [breq])

    @defer.deferredGenerator
    def test_mergeRequests_singleton_list(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        breq = dict(dummy=1)
        def is_not_called(*args):
            self.fail("should not be called")
        self.bldr._brdictToBuildRequest = is_not_called

        wfd = defer.waitForDeferred(
            self.bldr._mergeRequests(breq, [ breq ], lambda x,y : None))
        yield wfd
        merged = wfd.getResult()

        self.assertEqual(merged, [breq])

    # other methods

    @defer.deferredGenerator
    def test_reclaimAllBuilds_empty(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        # just to be sure this doesn't crash
        wfd = defer.waitForDeferred(
            self.bldr.reclaimAllBuilds())
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def test_reclaimAllBuilds(self):
        wfd = defer.waitForDeferred(
            self.makeBuilder())
        yield wfd
        wfd.getResult()

        claims = []
        def fakeClaimBRs(*args):
            claims.append(args)
            return defer.succeed(None)
        self.bldr.master.db.buildrequests.claimBuildRequests = fakeClaimBRs
        self.bldr.master.db.buildrequests.reclaimBuildRequests = fakeClaimBRs

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

        wfd = defer.waitForDeferred(
            self.bldr.reclaimAllBuilds())
        yield wfd
        wfd.getResult()

        self.assertEqual(claims, [ (set([10,11,12,15]),) ])

class TestGetOldestRequestTime(unittest.TestCase):

    def setUp(self):
        # a collection of rows that would otherwise clutter up every test
        master_id = fakedb.FakeBuildRequestsComponent.MASTER_ID
        self.base_rows = [
            fakedb.SourceStampSet(id=21),
            fakedb.SourceStamp(id=21, sourcestampsetid=21),
            fakedb.Buildset(id=11, reason='because', sourcestampsetid=21),
            fakedb.BuildRequest(id=111, submitted_at=1000,
                        buildername='bldr1', buildsetid=11),
            fakedb.BuildRequest(id=222, submitted_at=2000,
                        buildername='bldr1', buildsetid=11),
            fakedb.BuildRequestClaim(brid=222, objectid=master_id,
                        claimed_at=2001),
            fakedb.BuildRequest(id=333, submitted_at=3000,
                        buildername='bldr1', buildsetid=11),
            fakedb.BuildRequest(id=444, submitted_at=2500,
                        buildername='bldr2', buildsetid=11),
            fakedb.BuildRequestClaim(brid=444, objectid=master_id,
                        claimed_at=2501),
        ]

    def makeBuilder(self, name):
        self.bstatus = mock.Mock()
        self.factory = mock.Mock()
        self.master = fakemaster.make_master()
        # only include the necessary required config
        builder_config = config.BuilderConfig(
                        name=name, slavename="slv", builddir="bdir",
                        slavebuilddir="sbdir", factory=self.factory)
        self.bldr = builder.Builder(builder_config.name)
        self.master.db = self.db = fakedb.FakeDBConnector(self)
        self.bldr.master = self.master

        # we don't want the reclaim service running during tests..
        self.bldr.reclaim_svc.disownServiceParent()

        self.bldr.startService()

        mastercfg = config.MasterConfig()
        mastercfg.builders = [ builder_config ]
        return self.bldr.reconfigService(mastercfg)

    def test_gort_unclaimed(self):
        d = self.makeBuilder(name='bldr1')
        d.addCallback(lambda _ : self.db.insertTestData(self.base_rows))
        d.addCallback(lambda _ : self.bldr.getOldestRequestTime())
        def check(rqtime):
            self.assertEqual(rqtime, epoch2datetime(1000))
        d.addCallback(check)
        return d

    def test_gort_all_claimed(self):
        d = self.makeBuilder(name='bldr2')
        d.addCallback(lambda _ : self.db.insertTestData(self.base_rows))
        d.addCallback(lambda _ : self.bldr.getOldestRequestTime())
        def check(rqtime):
            self.assertEqual(rqtime, None)
        d.addCallback(check)
        return d

