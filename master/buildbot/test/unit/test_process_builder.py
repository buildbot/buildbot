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
from buildbot.test.fake import fakebuild
from buildbot.process import builder, factory
from buildbot.db import buildrequests
from buildbot.util import epoch2datetime

class BuilderMixin(object):
    def makeBuilder(self, name="bldr", patch_random=False, **config_kwargs):
        """Set up C{self.bldr}"""
        self.bstatus = mock.Mock()
        self.factory = factory.BuildFactory()
        self.master = fakemaster.make_master()
        # only include the necessary required config, plus user-requested
        config_args = dict(name=name, slavename="slv", builddir="bdir",
                     slavebuilddir="sbdir", project='default', factory=self.factory)
        config_args.update(config_kwargs)
        self.builder_config = config.BuilderConfig(**config_args)
        self.bldr = builder.Builder(self.builder_config.name, _addServices=False)
        self.master.db = self.db = fakedb.FakeDBConnector(self)
        self.bldr.master = self.master
        self.bldr.botmaster = self.master.botmaster

        if patch_random:
            # patch 'random.choice' to always take the slave that sorts
            # last, based on its name
            self.patch(random, "choice",
                    lambda lst : sorted(lst, key=lambda m : m.name)[-1])

        self.bldr.startService()

        mastercfg = config.MasterConfig()
        mastercfg.builders = [ self.builder_config ]
        return self.bldr.reconfigService(mastercfg)

class TestBuilderBuildCreation(BuilderMixin, unittest.TestCase):

    def setUp(self):
        # a collection of rows that would otherwise clutter up every test
        self.base_rows = [
            fakedb.SourceStampSet(id=21),
            fakedb.SourceStamp(id=21, sourcestampsetid=21),
            fakedb.Buildset(id=11, reason='because', sourcestampsetid=21),
        ]

    def makeBuilder(self, patch_random=False, patch_startbuildfor=True, **config_kwargs):
        d = BuilderMixin.makeBuilder(self, patch_random=patch_random, **config_kwargs)
        def patch_startBuildsFor(_):
            # patch into the _startBuildsFor method
            self.builds_started = []
            def _startBuildFor(slavebuilder, buildrequests):
                self.builds_started.append((slavebuilder, buildrequests))
                return defer.succeed(True)
            self.bldr._startBuildFor = _startBuildFor

        if patch_startbuildfor:
            d.addCallback(patch_startBuildsFor)

        return d

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
            sb.slave = mock.Mock()
            sb.slave.slave_status = mock.Mock(spec=['getName'])
            sb.slave.slave_status.getName.return_value = name
            sb.isAvailable.return_value = avail
            sb.prepare = lambda x, y: True
            sb.ping = lambda: True
            sb.buildStarted = lambda: True
            sb.buildFinished = lambda: False
            sb.remote = mock.Mock()
            self.bldr.slaves.append(sb)

    # services

    @defer.inlineCallbacks
    def test_stopService_flushes(self):
        yield self.makeBuilder()

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

        yield stop_d

        # and then check that things happened in the right order
        self.assertEqual(events, [ 'long_d', 'stop_d' ])

    # maybeStartBuild

    def assertBuildingRequets(self, exp):
        builds_started = [br.id for br in self.bldr.building[0].requests]
        self.assertEqual(sorted(builds_started), sorted(exp))

    def do_test_maybeStartBuild(self, rows=None, exp_claims=[], exp_builds=None, exp_brids=None,
                exp_fail=None):
        d = defer.succeed(True)
        if rows:
            d = self.db.insertTestData(rows)
        d.addCallback(lambda _ :
                self.bldr.maybeStartBuild())
        def check(_):
            self.failIf(exp_fail)
            self.db.buildrequests.assertMyClaims(exp_claims)
            if exp_builds:
                self.assertBuildsStarted(exp_builds)
            if exp_brids:
                self.assertBuildingRequets(exp_brids)
        d.addCallback(check)
        def eb(f):
            f.trap(exp_fail)
        d.addErrback(eb)
        return d

    @defer.inlineCallbacks
    def test_maybeStartBuild_selectedSlave(self):
        yield self.makeBuilder()

        self.setSlaveBuilders({'slave-01': 1, 'slave-02': 1, 'slave-03': 1, 'slave-04': 1})

        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildsetProperty(buildsetid=11, property_name='selected_slave',
                                        property_value='["slave-03", "Force Build Form"]')
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10], exp_builds=[('slave-03', [10])])

    @defer.inlineCallbacks
    def test_maybeStartBuildByPriority(self):
        yield self.makeBuilder(mergeRequests=False)

        self.setSlaveBuilders({'slave-01': 1})

        rows = [fakedb.SourceStampSet(id=1),
                fakedb.SourceStamp(id=1, sourcestampsetid=1, branch='az', revision='az', codebase='c', repository='z'),
                fakedb.SourceStamp(id=2, sourcestampsetid=1, branch='bw', revision='bz', codebase='f', repository='w'),
                fakedb.SourceStampSet(id=2),
                fakedb.SourceStamp(id=3, sourcestampsetid=2, branch='a', revision='az', codebase='c', repository='z'),
                fakedb.SourceStamp(id=4, sourcestampsetid=2, branch='bw', revision='wz', codebase='f', repository='w'),
                fakedb.Buildset(id=1, sourcestampsetid=1, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.Buildset(id=2, sourcestampsetid=2, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=1, buildsetid=1, buildername='bldr',
                                    submitted_at=1300305712, priority=15, results=-1),
                fakedb.BuildRequest(id=2, buildsetid=2, buildername='bldr',
                                    submitted_at=1300305712, priority=75, results=-1)]

        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[2], exp_builds=[('slave-01', [2])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_mergeBuilding(self):
        yield self.makeBuilder(patch_startbuildfor=False)
        def newBuild(buildrequests):
            return fakebuild.FakeBuild(buildrequests)

        self.bldr.config.factory.newBuild = newBuild

        self.bldr.notifyRequestsRemoved = lambda x: True

        self.setSlaveBuilders({'test-slave11':1})
        rows = [fakedb.SourceStampSet(id=1),
                fakedb.SourceStamp(id=1, sourcestampsetid=1, codebase='c', branch="az", repository="xz", revision="ww"),
                fakedb.Buildset(id=1, reason='because', sourcestampsetid=1),
                fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr", submitted_at=130000)]

        yield self.db.insertTestData(rows)
        yield self.do_test_maybeStartBuild(exp_claims=[1], exp_brids=[1])

        self.db.sourcestampsets.insertTestData([fakedb.SourceStampSet(id=2)])
        self.db.sourcestamps.insertTestData([fakedb.SourceStamp(id=2, sourcestampsetid=2, codebase='c', branch="az",
                                                                repository="xz", revision="ww")])
        self.db.buildsets.insertTestData([fakedb.Buildset(id=2, reason='because', sourcestampsetid=2)])
        self.db.buildrequests.insertTestData([fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr",
                                                                  submitted_at=130000)])

        yield self.do_test_maybeStartBuild(exp_claims=[1, 2], exp_brids=[1, 2])


    @defer.inlineCallbacks
    def test_maybeStartBuild_mergeBuildingCouldNotMerge(self):
        yield self.makeBuilder(patch_startbuildfor=False)
        def newBuild(buildrequests):
            return fakebuild.FakeBuild(buildrequests)

        self.bldr.config.factory.newBuild = newBuild

        self.bldr.notifyRequestsRemoved = lambda x: True

        self.setSlaveBuilders({'test-slave11':1})
        rows = [fakedb.SourceStampSet(id=1),
                fakedb.SourceStamp(id=1, sourcestampsetid=1, codebase='c', branch="az", repository="xz", revision="ww"),
                fakedb.Buildset(id=1, reason='because', sourcestampsetid=1),
                fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr", submitted_at=130000)]

        yield self.db.insertTestData(rows)
        yield self.do_test_maybeStartBuild(exp_claims=[1], exp_brids=[1])

        self.db.sourcestampsets.insertTestData([fakedb.SourceStampSet(id=2)])
        self.db.sourcestamps.insertTestData([fakedb.SourceStamp(id=2, sourcestampsetid=2, codebase='c', branch="az",
                                                                repository="xz", revision="bb")])
        self.db.buildsets.insertTestData([fakedb.Buildset(id=2, reason='because', sourcestampsetid=2)])
        self.db.buildrequests.insertTestData([fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr",
                                                                  submitted_at=130000)])

        yield self.do_test_maybeStartBuild(exp_claims=[1, 2], exp_brids=[1])

    @defer.inlineCallbacks
    def test_maybeStartBuild_no_buildreqests(self):
        yield self.makeBuilder()
        self.setSlaveBuilders({'test-slave11':1})
        yield self.do_test_maybeStartBuild(exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_maybeStartBuild_no_slavebuilders(self):
        yield self.makeBuilder()
        rows = [
            fakedb.BuildRequest(id=11, buildsetid=10, buildername="bldr"),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_maybeStartBuild_limited_by_slaves(self):
        yield self.makeBuilder(mergeRequests=False)

        self.setSlaveBuilders({'test-slave1':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10, 11], exp_builds=[('test-slave1', [10, 11])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_limited_by_available_slaves(self):
        yield self.makeBuilder(mergeRequests=False)

        self.setSlaveBuilders({'test-slave1':0, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10, 11], exp_builds=[('test-slave2', [10, 11])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_unlimited(self):
        yield self.makeBuilder(mergeRequests=False, patch_random=True)

        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=10, buildsetid=11, buildername="bldr",
                submitted_at=130000),
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr",
                submitted_at=135000),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10, 11],
                exp_builds=[('test-slave2', [10, 11])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_limited_by_requests(self):
        yield self.makeBuilder(mergeRequests=False, patch_random=True)

        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[11], exp_builds=[('test-slave2', [11])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_chooseSlave_None(self):
        yield self.makeBuilder()

        self.bldr._chooseSlave = lambda avail : defer.succeed(None)
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_maybeStartBuild_chooseSlave_bogus(self):
        yield self.makeBuilder()

        self.bldr._chooseSlave = lambda avail : defer.succeed(mock.Mock())
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_maybeStartBuild_chooseSlave_fails(self):
        yield self.makeBuilder()

        self.bldr._chooseSlave = lambda avail : defer.fail(RuntimeError("xx"))
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[], exp_fail=RuntimeError)

    @defer.inlineCallbacks
    def test_maybeStartBuild_chooseBuild_None(self):
        yield self.makeBuilder()

        self.bldr._chooseBuild = lambda reqs : defer.succeed(None)
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_maybeStartBuild_chooseBuild_bogus(self):
        yield self.makeBuilder()

        self.bldr._chooseBuild = lambda reqs : defer.succeed(mock.Mock())
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[])

    @defer.inlineCallbacks
    def test_maybeStartBuild_chooseBuild_fails(self):
        yield self.makeBuilder(patch_random=True)

        self.bldr._chooseBuild = lambda reqs : defer.fail(RuntimeError("xx"))
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[], exp_fail=RuntimeError)

    @defer.inlineCallbacks
    def test_maybeStartBuild_mergeRequests_fails(self):
        yield self.makeBuilder(patch_random=True)

        def _mergeRequests(breq, unclaimed_requests, mergeRequests_fn):
            return defer.fail(RuntimeError("xx"))
        self.bldr._mergeRequests = _mergeRequests
        self.setSlaveBuilders({'test-slave1':1, 'test-slave2':1})
        rows = self.base_rows + [
            fakedb.BuildRequest(id=11, buildsetid=11, buildername="bldr"),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[], exp_builds=[], exp_fail=RuntimeError)

    @defer.inlineCallbacks
    def test_maybeStartBuild_claim_race(self):
        yield self.makeBuilder(patch_random=True)

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
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[10, 11], exp_builds=[('test-slave2', [10, 11])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_builder_stopped(self):
        yield self.makeBuilder()

        # this will cause an exception if maybeStartBuild tries to start
        self.bldr.slaves = None

        # so we just hope this does not fail
        yield self.bldr.stopService()
        yield self.bldr.maybeStartBuild()

    @defer.inlineCallbacks
    def test_maybeStartBuild_merge_ordering(self):
        yield self.makeBuilder(patch_random=True)

        self.setSlaveBuilders({'bldr':1})

        # based on the build in bug #2249
        rows = [
            fakedb.SourceStampSet(id=1976),
            fakedb.SourceStamp(id=1976, sourcestampsetid=1976),
            fakedb.Buildset(id=1980, reason='scheduler', sourcestampsetid=1976,
                submitted_at=1332024020.67792),
            fakedb.BuildRequest(id=42880, buildsetid=1980,
                submitted_at=1332024020.67792, buildername="bldr"),

            fakedb.SourceStampSet(id=1977),
            fakedb.SourceStamp(id=1977, sourcestampsetid=1977),
            fakedb.Buildset(id=1981, reason='scheduler', sourcestampsetid=1977,
                submitted_at=1332025495.19141),
            fakedb.BuildRequest(id=42922, buildsetid=1981,
                buildername="bldr", submitted_at=1332025495.19141),
        ]
        yield self.do_test_maybeStartBuild(rows=rows,
                exp_claims=[42880, 42922],
                exp_builds=[('bldr', [42880, 42922])])

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
        d.addCallback(lambda _ : self.bldr._chooseNextBuild(requests))
        def check(sb):
            self.assertIdentical(sb, requests[exp_choice])
        def failed(f):
            f.trap(exp_fail)
        d.addCallbacks(check, failed)
        return d

    def test_chooseBuild_default(self):
        "default chooses the first in the list, which should be the earliest"
        def nextBuild(bldr, lst):
            self.assertIdentical(bldr, self.bldr)
            return lst[0]
        return self.do_test_chooseBuild(nextBuild, exp_choice=0)

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

    @defer.inlineCallbacks
    def test_brdictToBuildRequest(self):
        yield self.makeBuilder()

        # set up all of the data required for a BuildRequest object
        yield self.db.insertTestData([
                fakedb.SourceStampSet(id=234),
                fakedb.SourceStamp(id=234,sourcestampsetid=234),
                fakedb.Buildset(id=30, sourcestampsetid=234, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=19, buildsetid=30, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
            ])

        brdict = yield self.db.buildrequests.getBuildRequest(19)
        br = yield self.bldr._brdictToBuildRequest(brdict)

        # just check that the BuildRequest looks reasonable -
        # test_process_buildrequest checks the whole thing
        self.assertEqual(br.reason, 'foo')

        # and check that the cross-pointers are correct
        self.assertIdentical(br.brdict, brdict)
        self.assertIdentical(brdict['brobj'], br)

        self.bldr._breakBrdictRefloops([brdict])

    # _getMergeRequestsFn

    @defer.inlineCallbacks
    def do_test_getMergeRequestsFn(self, builder_param=None,
                    global_param=None, expected=0):
        cble = lambda : None
        builder_param = builder_param == 'callable' and cble or builder_param
        global_param = global_param == 'callable' and cble or global_param

        # omit the constructor parameter if None was given
        if builder_param is None:
            yield self.makeBuilder()
        else:
            yield self.makeBuilder(mergeRequests=builder_param)

        self.master.config.mergeRequests = global_param

        fn = self.bldr._getMergeRequestsFn()

        if fn == builder.Builder._defaultMergeRequestFn:
            fn = "default"
        elif fn is cble:
            fn = 'callable'
        self.assertEqual(fn, expected)

    def test_getMergeRequestsFn_defaults(self):
        self.do_test_getMergeRequestsFn(None, None, None)

    def test_getMergeRequestsFn_global_True(self):
        self.do_test_getMergeRequestsFn(None, True, None)

    def test_getMergeRequestsFn_global_False(self):
        self.do_test_getMergeRequestsFn(None, False, None)

    def test_getMergeRequestsFn_global_function(self):
        self.do_test_getMergeRequestsFn(None, 'callable', None)

    def test_getMergeRequestsFn_builder_True(self):
        self.do_test_getMergeRequestsFn(True, False, "default")

    def test_getMergeRequestsFn_builder_False(self):
        self.do_test_getMergeRequestsFn(False, True, None)

    def test_getMergeRequestsFn_builder_function(self):
        self.do_test_getMergeRequestsFn('callable', None, 'callable')

    # _mergeRequests
    @defer.inlineCallbacks
    def test_mergePending_CodebaseDoesNotMatch(self):
        yield self.makeBuilder()

        yield self.db.insertTestData([
                fakedb.SourceStampSet(id=1),
                fakedb.SourceStamp(id=1, sourcestampsetid=1, branch='az', revision='az', codebase='c', repository='z'),
                fakedb.SourceStamp(id=2, sourcestampsetid=1, branch='bw', revision='bz', codebase='f', repository='w'),
                fakedb.SourceStampSet(id=2),
                fakedb.SourceStamp(id=3, sourcestampsetid=2, branch='a', revision='az', codebase='c', repository='z'),
                fakedb.SourceStamp(id=4, sourcestampsetid=2, branch='bw', revision='wz', codebase='f', repository='w'),
                fakedb.Buildset(id=1, sourcestampsetid=1, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.Buildset(id=2, sourcestampsetid=2, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=1, buildsetid=1, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=2, buildsetid=2, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1)
            ])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])

    def compatiblePendingBuildRequests(self):
        return [
            fakedb.SourceStampSet(id=1),
            fakedb.SourceStamp(id=1, sourcestampsetid=1, branch='az', revision='az', codebase='c', repository='z'),
            fakedb.SourceStamp(id=2, sourcestampsetid=1, branch='bw', revision='bz', codebase='f', repository='w'),
            fakedb.SourceStampSet(id=2),
            fakedb.SourceStamp(id=3, sourcestampsetid=2, branch='az', revision='az', codebase='c', repository='z'),
            fakedb.SourceStamp(id=4, sourcestampsetid=2, branch='bw', revision='bz', codebase='f', repository='w'),
            fakedb.Buildset(id=1, sourcestampsetid=1, reason='foo',
                            submitted_at=1300305712, results=-1),
            fakedb.Buildset(id=2, sourcestampsetid=2, reason='foo',
                            submitted_at=1300305712, results=-1),
            fakedb.BuildRequest(id=1, buildsetid=1, buildername='bldr',
                                priority=13, submitted_at=1300305712, results=-1),
            fakedb.BuildRequest(id=2, buildsetid=2, buildername='bldr',
                                priority=13, submitted_at=1300305712, results=-1)
        ]

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatch(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests())

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0], brdicts[1]])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchSelectedSlave(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests() +
                                     [fakedb.BuildsetProperty(buildsetid = 1, property_name='selected_slave',
                                        property_value='["build-slave-01", "Force Build Form"]')])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchForceRebuild(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests() +
                                     [fakedb.BuildsetProperty(buildsetid = 1, property_name='force_rebuild',
                                        property_value='[true, "Force Build Form"]')])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchForceChainRebuild(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests() +
                                     [fakedb.BuildsetProperty(buildsetid = 1, property_name='force_chain_rebuild',
                                        property_value='[true, "Force Build Form"]')])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchBuildLatestRev(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests() +
                                     [fakedb.BuildsetProperty(buildsetid = 1, property_name='buildLatestRev',
                                        property_value='[true, "Force Build Form"]')])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])

    @defer.inlineCallbacks
    def test_mergeRequests(self):
        yield self.makeBuilder()

        # set up all of the data required for a BuildRequest object
        yield self.db.insertTestData([
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
            ])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (19, 20, 21)
            ])

        def mergeRequests_fn(builder, breq, other):
            # merge evens with evens, odds with odds
            return breq.id % 2 == other.id % 2

        # check odds
        odds = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, mergeRequests_fn)
        self.assertEqual(odds, [ brdicts[0], brdicts[2] ])

        # check evens
        evens = yield self.bldr._mergeRequests(brdicts[1],
                                brdicts, mergeRequests_fn)
        self.assertEqual(evens, [ brdicts[1] ])

        # check original relative order of requests within brdicts is maintained
        merged = yield self.bldr._mergeRequests(brdicts[2],
                                                brdicts, mergeRequests_fn)
        self.assertEqual(merged, [brdicts[0], brdicts[2]],
                         'relative order of merged requests was not maintained')

    @defer.inlineCallbacks
    def test_mergeRequest_no_other_request(self):
        """ Test if builder test for codebases in requests """
        yield self.makeBuilder()

        # set up all of the data required for a BuildRequest object
        yield self.db.insertTestData([
                fakedb.SourceStampSet(id=234),
                fakedb.SourceStamp(id=234, sourcestampsetid=234, codebase='A'),
                fakedb.Change(changeid=14, codebase='A'),
                fakedb.SourceStampChange(sourcestampid=234, changeid=14),
                fakedb.Buildset(id=30, sourcestampsetid=234, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=19, buildsetid=30, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
            ])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(19)
            ])

        def mergeRequests_fn(builder, breq, other):
            # Allow all requests
            return True

        # check if the request remains the same
        res = yield self.bldr._mergeRequests(brdicts[0], brdicts,
                                            mergeRequests_fn)
        self.assertEqual(res, [ brdicts[0] ])

    @defer.inlineCallbacks
    def test_mergeRequests_codebases_equal(self):
        """ Test if builder test for codebases in requests """
        yield self.makeBuilder()

        # set up all of the data required for a BuildRequest object
        yield self.db.insertTestData([
                fakedb.SourceStampSet(id=234),
                fakedb.SourceStamp(id=234, sourcestampsetid=234, codebase='A'),
                fakedb.Buildset(id=30, sourcestampsetid=234, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.SourceStampSet(id=235),
                fakedb.SourceStamp(id=235, sourcestampsetid=235, codebase='A'),
                fakedb.Buildset(id=31, sourcestampsetid=235, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.SourceStampSet(id=236),
                fakedb.SourceStamp(id=236, sourcestampsetid=236, codebase='A'),
                fakedb.Buildset(id=32, sourcestampsetid=236, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=19, buildsetid=30, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=20, buildsetid=31, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=21, buildsetid=32, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
            ])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (19, 20, 21)
            ])

        def mergeRequests_fn(builder, breq, other):
            # Allow all requests to test builder functionality
            return True

        # check if all are merged
        res = yield self.bldr._mergeRequests(brdicts[0], brdicts,
                                             mergeRequests_fn)
        self.assertEqual(res, [ brdicts[0], brdicts[1], brdicts[2] ])

    @defer.inlineCallbacks
    def test_mergeRequests_no_merging(self):
        yield self.makeBuilder()

        breq = dict(dummy=1)
        merged = yield self.bldr._mergeRequests(breq, [ breq, breq ], None)

        self.assertEqual(merged, [breq])

    @defer.inlineCallbacks
    def test_mergeRequests_singleton_list(self):
        yield self.makeBuilder()

        breq = dict(dummy=1)
        def is_not_called(*args):
            self.fail("should not be called")
        self.bldr._brdictToBuildRequest = is_not_called

        merged = yield self.bldr._mergeRequests(breq, [ breq ],
                                        lambda x,y : None)

        self.assertEqual(merged, [breq])

    # other methods

    @defer.inlineCallbacks
    def test_reclaimAllBuilds_empty(self):
        yield self.makeBuilder()

        # just to be sure this doesn't crash
        yield self.bldr.reclaimAllBuilds()

    @defer.inlineCallbacks
    def test_reclaimAllBuilds(self):
        yield self.makeBuilder()

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

        yield self.bldr.reclaimAllBuilds()

        self.assertEqual(claims, [ (set([10,11,12,15]),) ])

class TestGetOldestRequestTime(BuilderMixin, unittest.TestCase):

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

class TestRebuild(BuilderMixin, unittest.TestCase):

    def makeBuilder(self, name, sourcestamps):
        d = BuilderMixin.makeBuilder(self, name=name)
        @d.addCallback
        def setupBstatus(_):
            self.bstatus = mock.Mock()
            bstatus_properties = mock.Mock()
            bstatus_properties.properties = {}
            self.bstatus.getProperties.return_value = bstatus_properties
            self.bstatus.getSourceStamps.return_value = sourcestamps
            self.master.addBuildset = addBuildset = mock.Mock()
            addBuildset.return_value = (1, [100])
        return d

    @defer.inlineCallbacks
    def do_test_rebuild(self,
                        sourcestampsetid,
                        nr_of_sourcestamps):

        # Store combinations of sourcestampId and sourcestampSetId
        self.sslist = {}
        self.ssseq = 1
        def addSourceStampToDatabase(master, sourcestampsetid):
            self.sslist[self.ssseq] = sourcestampsetid
            self.ssseq += 1
            return defer.succeed(sourcestampsetid)
        def getSourceStampSetId(master):
            return addSourceStampToDatabase(master, sourcestampsetid = sourcestampsetid)

        sslist = []
        for x in range(nr_of_sourcestamps):
            ssx = mock.Mock()
            ssx.addSourceStampToDatabase = addSourceStampToDatabase
            ssx.getSourceStampSetId = getSourceStampSetId
            sslist.append(ssx)

        yield self.makeBuilder(name='bldr1', sourcestamps = sslist)
        control = mock.Mock(spec=['master'])
        control.master = self.master
        self.bldrctrl = builder.BuilderControl(self.bldr, control)

        yield self.bldrctrl.rebuildBuild(self.bstatus, reason = 'unit test', extraProperties = {})

    @defer.inlineCallbacks
    def test_rebuild_with_no_sourcestamps(self):
        yield self.do_test_rebuild(101, 0)
        self.assertEqual(self.sslist, {})

    @defer.inlineCallbacks
    def test_rebuild_with_single_sourcestamp(self):
        yield self.do_test_rebuild(101, 1)
        self.assertEqual(self.sslist, {1:101})
        self.master.addBuildset.assert_called_with(builderNames=['bldr1'],
                                                          sourcestampsetid=101,
                                                          reason = 'unit test',
                                                          properties = {})


    @defer.inlineCallbacks
    def test_rebuild_with_multiple_sourcestamp(self):
        yield self.do_test_rebuild(101, 3)
        self.assertEqual(self.sslist, {1:101, 2:101, 3:101})
        self.master.addBuildset.assert_called_with(builderNames=['bldr1'],
                                                          sourcestampsetid=101,
                                                          reason = 'unit test',
                                                          properties = {})


class TestReconfig(BuilderMixin, unittest.TestCase):
    """Tests that a reconfig properly updates all attributes"""

    @defer.inlineCallbacks
    def test_reconfig(self):
        yield self.makeBuilder(description="Old", category="OldCat")
        self.builder_config.description = "New"
        self.builder_config.category = "NewCat"

        mastercfg = config.MasterConfig()
        mastercfg.builders = [ self.builder_config ]
        yield self.bldr.reconfigService(mastercfg)
        self.assertEqual(
                dict(description=self.bldr.builder_status.getDescription(),
                    category=self.bldr.builder_status.getCategory()),
                dict(description="New",
                    category="NewCat"))
