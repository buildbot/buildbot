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
from buildbot.util import epoch2datetime
from buildbot.test.util.katanabuildrequestdistributor import KatanaBuildRequestDistributorTestSetup
from buildbot.status.results import SUCCESS, BEGINNING, RETRY

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

    def makeBuilder(self, patch_random=False, startBuildsForSucceeds=True,
                    patch_startbuildfor=True, **config_kwargs):
        d = BuilderMixin.makeBuilder(self, patch_random=patch_random, **config_kwargs)
        def patch_startBuildsFor(_):
            # patch into the _startBuildsFor method
            self.builds_started = []
            def _startBuildFor(slavebuilder, buildrequests):
                self.builds_started.append((slavebuilder, buildrequests))
                return defer.succeed(startBuildsForSucceeds)
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


    # services

    def setupMethods(self, newBuild):
        self.bldr.config.factory.newBuild = newBuild
        self.bldr.notifyRequestsRemoved = lambda x: True
        self.bldr.buildFinished = lambda build, sb, bids: True

    # services

    @defer.inlineCallbacks
    def test_maybeStartBuild_builder_stopped(self):
        yield self.makeBuilder()

        # this will cause an exception if maybeStartBuild tries to start
        self.bldr.slaves = None

        # so we just hope this does not fail
        yield self.bldr.stopService()
        started = yield self.bldr.maybeStartBuild(None, [])
        self.assertEquals(started, False)

    # maybeStartBuild

    # maybeStartBuild

    def _makeMocks(self):
        slave = mock.Mock()
        slave.name = 'slave'
        buildrequest = mock.Mock()
        buildrequest.id = 10
        buildrequests = [buildrequest]
        return slave, buildrequests

    @defer.inlineCallbacks
    def test_maybeStartBuild(self):
        yield self.makeBuilder()

        slave, buildrequests = self._makeMocks()

        started = yield self.bldr.maybeStartBuild(slave, buildrequests)
        self.assertEqual(started, True)
        self.assertBuildsStarted([('slave', [10])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_failsToStart(self):
        yield self.makeBuilder(startBuildsForSucceeds=False)

        slave, buildrequests = self._makeMocks()

        started = yield self.bldr.maybeStartBuild(slave, buildrequests)
        self.assertEqual(started, False)
        self.assertBuildsStarted([('slave', [10])])

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

        fn = self.bldr.getMergeRequestsFn()

        if fn == builder.Builder._defaultMergeRequestFn:
            fn = "default"
        elif fn is cble or fn == builder.Builder._skipMergeRequestFn:
            fn = 'callable'
        self.assertEqual(fn, expected)

    def test_getMergeRequestsFn_defaults(self):
        self.do_test_getMergeRequestsFn(None, None, 'default')

    def test_getMergeRequestsFn_global_True(self):
        self.do_test_getMergeRequestsFn(None, True, 'default')

    def test_getMergeRequestsFn_global_False(self):
        self.do_test_getMergeRequestsFn(None, False, 'callable')

    def test_getMergeRequestsFn_global_function(self):
        self.do_test_getMergeRequestsFn(None, 'callable', 'callable')

    def test_getMergeRequestsFn_builder_True(self):
        self.do_test_getMergeRequestsFn(True, False, "default")

    def test_getMergeRequestsFn_builder_False(self):
        self.do_test_getMergeRequestsFn(False, None, 'callable')

    def test_getMergeRequestsFn_builder_function(self):
        self.do_test_getMergeRequestsFn('callable', None, 'callable')

    @defer.inlineCallbacks
    def test_canStartBuild(self):
        yield self.makeBuilder()

        # by default, it returns True
        startable = yield self.bldr.canStartBuild('slave', 100)
        self.assertEqual(startable, True)

        startable = yield self.bldr.canStartBuild('slave', 101)
        self.assertEqual(startable, True)

        # set a configurable one
        record = []
        def canStartBuild(bldr, slave, breq):
            record.append((bldr, slave, breq))
            return (slave,breq)==('slave',100)
        self.bldr.config.canStartBuild = canStartBuild

        startable = yield self.bldr.canStartBuild('slave', 100)
        self.assertEqual(startable, True)
        self.assertEqual(record, [(self.bldr, 'slave', 100)])

        startable = yield self.bldr.canStartBuild('slave', 101)
        self.assertEqual(startable, False)
        self.assertEqual(record, [(self.bldr, 'slave', 100), (self.bldr, 'slave', 101)])

        # set a configurable one to return Deferred
        record = []
        def canStartBuild_deferred(bldr, slave, breq):
            record.append((bldr, slave, breq))
            return (slave,breq)==('slave',100)
            return defer.succeed((slave,breq)==('slave',100))
        self.bldr.config.canStartBuild = canStartBuild_deferred

        startable = yield self.bldr.canStartBuild('slave', 100)
        self.assertEqual(startable, True)
        self.assertEqual(record, [(self.bldr, 'slave', 100)])

        startable = yield self.bldr.canStartBuild('slave', 101)
        self.assertEqual(startable, False)
        self.assertEqual(record, [(self.bldr, 'slave', 100), (self.bldr, 'slave', 101)])

    # other methods

    @defer.inlineCallbacks
    def test_enforceChosenSlave(self):
        """enforceChosenSlave rejects and accepts builds"""
        yield self.makeBuilder()

        self.bldr.config.canStartBuild = builder.enforceChosenSlave

        slave = mock.Mock()
        slave.slave.slavename = 'slave5'

        breq = mock.Mock()

        # no buildslave requested
        breq.properties = {}
        result = yield self.bldr.canStartBuild(slave, breq)
        self.assertIdentical(True, result)

        # buildslave requested as the right one
        breq.properties = { 'slavename': 'slave5' }
        result = yield self.bldr.canStartBuild(slave, breq)
        self.assertIdentical(True, result)

        # buildslave requested as the wrong one
        breq.properties = { 'slavename': 'slave4' }
        result = yield self.bldr.canStartBuild(slave, breq)
        self.assertIdentical(False, result)

        # buildslave set to non string value gets skipped
        breq.properties = { 'slavename': 0 }
        result = yield self.bldr.canStartBuild(slave, breq)
        self.assertIdentical(True, result)

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


class TestFinishBuildRequests(unittest.TestCase, KatanaBuildRequestDistributorTestSetup):

    @defer.inlineCallbacks
    def setupBuildRequets(self):
        self.bldr = self.setupBuilderInMaster(name='bldr1', slavenames={'slave-01': False,
                                                                        'slave-02': True})
        self.bldr.master = self.master
        build = mock.Mock()
        build.finished = False
        build.build_status = mock.Mock()
        build.build_status.number = 1
        build.build_status.getResults.return_value = SUCCESS

        def createRequest(id):
            req = mock.Mock()
            req.id = id
            return req

        build.requests = [createRequest(1), createRequest(2)]
        self.bldr.building = [build]
        self.build = build

        testdata = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                       submitted_at=1300305712),
                    fakedb.BuildRequest(id=2,
                                        buildsetid=2,
                                        buildername="bldr1",
                                        submitted_at=1300305712,
                                        mergebrid=1,
                                        artifactbrid=1),
                    fakedb.Build(id=1, number=1, brid=1, start_time=1300305712),
                    fakedb.Build(id=2, number=1, brid=2, start_time=1300305712),
                    fakedb.BuildRequestClaim(brid=1, objectid=1, claimed_at=1300305712),
                    fakedb.BuildRequestClaim(brid=2, objectid=1, claimed_at=1300305712)]

        yield  self.insertTestData(testdata)

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpComponents()
        yield self.setupBuildRequets()


    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tearDownComponents()

    @defer.inlineCallbacks
    def checkBuilds(self, brids, finish):
        for brid in brids:
            build = yield self.master.db.builds.getBuildsForRequest(brid)
            self.assertEqual(len(build), 1)
            self.assertTrue(build[0]['finish_time'] is None if not finish else build[0]['finish_time'])

    @defer.inlineCallbacks
    def checkBuildRequests(self, brids, complete, results, claimed=True):
        brdicts = yield self.master.db.buildrequests.getBuildRequests(buildername='bldr1',
                                                                      brids=[1, 2],
                                                                      claimed=claimed)
        self.assertTrue(len(brdicts) == 2)
        self.assertTrue(all([br['complete'] == complete and br['results'] == results
                             and (br['complete_at'] is not None if complete else br['complete_at'] is None)
                             and (br['claimed_at'] is not None if claimed else br['claimed_at'] is None)
                             for br in brdicts]))

    @defer.inlineCallbacks
    def test_finishBuildRequests(self):
        brids = [1, 2]
        yield self.checkBuilds(brids=brids, finish=False)
        yield self.checkBuildRequests(brids=brids, complete=0, results=BEGINNING)

        yield self.bldr.finishBuildRequests(brids=[1, 2],
                                            requests=self.build.requests,
                                            build=self.build,
                                            bids=[1, 2])

        yield self.checkBuilds(brids=brids, finish=True)
        yield self.checkBuildRequests(brids=brids, complete=1, results=SUCCESS)

    @defer.inlineCallbacks
    def test_finishBuildRequestsRetryBuild(self):
        brids = [1, 2]
        yield self.checkBuilds(brids=brids, finish=False)
        yield self.checkBuildRequests(brids=brids, complete=0, results=BEGINNING)

        self.build.build_status.getResults.return_value = RETRY

        yield self.bldr.finishBuildRequests([1, 2], self.build.requests, self.build, [1, 2])

        yield self.checkBuilds(brids=brids, finish=True)
        yield self.checkBuildRequests(brids=brids, complete=0, results=BEGINNING, claimed=False)

    @defer.inlineCallbacks
    def test_finishBuildRequestsWhileMergingBuild(self):
        brids = [1, 2]
        yield self.checkBuilds(brids=brids, finish=False)
        yield self.checkBuildRequests(brids=brids, complete=0, results=BEGINNING)

        yield self.bldr.finishBuildRequests(brids=[1], requests=self.build.requests[:1], build=self.build, bids=[1])

        yield self.bldr.finishBuildRequests(brids=[2], requests=self.build.requests[1:], build=self.build,
                                            mergedbrids=[1, 2])

        yield self.checkBuilds(brids=brids, finish=True)
        yield self.checkBuildRequests(brids=brids, complete=1, results=SUCCESS)
