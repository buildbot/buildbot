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
from twisted.internet import defer
from buildbot import config
from buildbot.test.fake import fakedb, fakemaster
from buildbot.process import builder, factory
from buildbot.util import epoch2datetime

class BuilderMixin(object):
    def makeBuilder(self, name="bldr", patch_random=False, **config_kwargs):
        """Set up C{self.bldr}"""
        self.factory = factory.BuildFactory()
        self.master = fakemaster.make_master()
        # only include the necessary required config, plus user-requested
        config_args = dict(name=name, slavename="slv", builddir="bdir",
                     slavebuilddir="sbdir", factory=self.factory)
        config_args.update(config_kwargs)
        self.builder_config = config.BuilderConfig(**config_args)
        self.bldr = builder.Builder(self.builder_config.name, _addServices=False)
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

    def makeBuilder(self, patch_random=False, startBuildsForSucceeds=True, **config_kwargs):
        d = BuilderMixin.makeBuilder(self, patch_random=patch_random, **config_kwargs)
        @d.addCallback
        def patch_startBuildsFor(_):
            # patch into the _startBuildsFor method
            self.builds_started = []
            def _startBuildFor(slavebuilder, buildrequests):
                self.builds_started.append((slavebuilder, buildrequests))
                return defer.succeed(startBuildsForSucceeds)
            self.bldr._startBuildFor = _startBuildFor
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
            sb.isAvailable.return_value = avail
            self.bldr.slaves.append(sb)

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

    @defer.inlineCallbacks
    def test_maybeStartBuild(self):
        yield self.makeBuilder()
        
        slave = mock.Mock()
        slave.name = 'slave'
        buildrequests = [mock.Mock(id=10)]
        
        started = yield self.bldr.maybeStartBuild(slave, buildrequests)
        self.assertEqual(started, True)
        self.assertBuildsStarted([('slave', [10])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_failsToStart(self):
        yield self.makeBuilder(startBuildsForSucceeds=False)
        
        slave = mock.Mock()
        slave.name = 'slave'
        buildrequests = [mock.Mock(id=10)]
        
        started = yield self.bldr.maybeStartBuild(slave, buildrequests)
        self.assertEqual(started, False)
        self.assertBuildsStarted([('slave', [10])])

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
