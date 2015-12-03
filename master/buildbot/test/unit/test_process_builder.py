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
import random

from buildbot import config
from buildbot.process import builder
from buildbot.process import factory
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.util import epoch2datetime
from twisted.internet import defer
from twisted.trial import unittest


class BuilderMixin(object):

    def setUpBuilderMixin(self):
        self.factory = factory.BuildFactory()
        self.master = fakemaster.make_master(testcase=self, wantData=True)
        self.mq = self.master.mq
        self.db = self.master.db

    @defer.inlineCallbacks
    def makeBuilder(self, name="bldr", patch_random=False, noReconfig=False,
                    **config_kwargs):
        """Set up C{self.bldr}"""
        # only include the necessary required config, plus user-requested
        config_args = dict(name=name, slavename="slv", builddir="bdir",
                           slavebuilddir="sbdir", factory=self.factory)
        config_args.update(config_kwargs)
        self.builder_config = config.BuilderConfig(**config_args)
        self.bldr = builder.Builder(self.builder_config.name, _addServices=False)
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
                       lambda lst: sorted(lst, key=lambda m: m.name)[-1])

        self.bldr.startService()

        mastercfg = config.MasterConfig()
        mastercfg.builders = [self.builder_config]
        if not noReconfig:
            defer.returnValue((yield self.bldr.reconfigServiceWithBuildbotConfig(mastercfg)))


class TestBuilder(BuilderMixin, unittest.TestCase):

    def setUp(self):
        # a collection of rows that would otherwise clutter up every test
        self.setUpBuilderMixin()
        self.base_rows = [
            fakedb.SourceStamp(id=21),
            fakedb.Buildset(id=11, reason='because'),
            fakedb.BuildsetSourceStamp(buildsetid=11, sourcestampid=21),
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
            (sl.name, [br.id for br in buildreqs])
            for (sl, buildreqs) in self.builds_started]
        self.assertEqual(sorted(builds_started), sorted(exp))

    def setSlaveBuilders(self, slavebuilders):
        """C{slaves} maps name : available"""
        self.bldr.slaves = []
        for name, avail in iteritems(slavebuilders):
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

    @defer.inlineCallbacks
    def do_test_getCollapseRequestsFn(self, builder_param=None,
                                      global_param=None, expected=0):
        cble = lambda: None
        builder_param = builder_param == 'callable' and cble or builder_param
        global_param = global_param == 'callable' and cble or global_param

        # omit the constructor parameter if None was given
        if builder_param is None:
            yield self.makeBuilder()
        else:
            yield self.makeBuilder(collapseRequests=builder_param)

        self.master.config.collapseRequests = global_param

        fn = self.bldr.getCollapseRequestsFn()

        if fn == builder.Builder._defaultCollapseRequestFn:
            fn = "default"
        elif fn is cble:
            fn = 'callable'
        self.assertEqual(fn, expected)

    def test_getCollapseRequestsFn_defaults(self):
        self.do_test_getCollapseRequestsFn(None, None, "default")

    def test_getCollapseRequestsFn_global_True(self):
        self.do_test_getCollapseRequestsFn(None, True, "default")

    def test_getCollapseRequestsFn_global_False(self):
        self.do_test_getCollapseRequestsFn(None, False, None)

    def test_getCollapseRequestsFn_global_function(self):
        self.do_test_getCollapseRequestsFn(None, 'callable', 'callable')

    def test_getCollapseRequestsFn_builder_True(self):
        self.do_test_getCollapseRequestsFn(True, False, "default")

    def test_getCollapseRequestsFn_builder_False(self):
        self.do_test_getCollapseRequestsFn(False, True, None)

    def test_getCollapseRequestsFn_builder_function(self):
        self.do_test_getCollapseRequestsFn('callable', None, 'callable')

    # other methods

    @defer.inlineCallbacks
    def test_reclaimAllBuilds_empty(self):
        yield self.makeBuilder()

        # just to be sure this doesn't crash
        yield self.bldr.reclaimAllBuilds()

    @defer.inlineCallbacks
    def test_reclaimAllBuilds(self):
        yield self.makeBuilder()

        def mkbld(brids):
            bld = mock.Mock(name='Build')
            bld.requests = []
            for brid in brids:
                br = mock.Mock(name='BuildRequest %d' % brid)
                br.id = brid
                bld.requests.append(br)
            return bld

        old = mkbld([15])  # keep a reference to the "old" build
        self.bldr.old_building[old] = None
        self.bldr.building.append(mkbld([10, 11, 12]))

        yield self.bldr.reclaimAllBuilds()

        self.assertEqual(self.master.data.updates.claimedBuildRequests,
                         set([10, 11, 12, 15]))

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
            return (slave, breq) == ('slave', 100)
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
            return defer.succeed((slave, breq) == ('slave', 100))
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
        breq.properties = {'slavename': 'slave5'}
        result = yield self.bldr.canStartBuild(slave, breq)
        self.assertIdentical(True, result)

        # buildslave requested as the wrong one
        breq.properties = {'slavename': 'slave4'}
        result = yield self.bldr.canStartBuild(slave, breq)
        self.assertIdentical(False, result)

        # buildslave set to non string value gets skipped
        breq.properties = {'slavename': 0}
        result = yield self.bldr.canStartBuild(slave, breq)
        self.assertIdentical(True, result)

    @defer.inlineCallbacks
    def test_getBuilderId(self):
        self.factory = factory.BuildFactory()
        self.master = fakemaster.make_master(testcase=self, wantData=True)
        # only include the necessary required config, plus user-requested
        self.bldr = builder.Builder('bldr', _addServices=False)
        self.bldr.master = self.master
        self.master.data.updates.findBuilderId = fbi = mock.Mock()
        fbi.return_value = defer.succeed(13)

        builderid = yield self.bldr.getBuilderId()
        self.assertEqual(builderid, 13)
        fbi.assert_called_with('bldr')
        fbi.reset_mock()

        builderid = yield self.bldr.getBuilderId()
        self.assertEqual(builderid, 13)
        fbi.assert_not_called()


class TestGetBuilderId(BuilderMixin, unittest.TestCase):

    def setUp(self):
        self.setUpBuilderMixin()

    @defer.inlineCallbacks
    def test_getBuilderId(self):
        # noReconfig because reconfigService calls getBuilderId, and we haven't
        # set up the mock findBuilderId yet.
        yield self.makeBuilder(name='b1', noReconfig=True)
        fbi = self.master.data.updates.findBuilderId = mock.Mock(name='fbi')
        fbi.side_effect = lambda name: defer.succeed(13)
        # call twice..
        self.assertEqual((yield self.bldr.getBuilderId()), 13)
        self.assertEqual((yield self.bldr.getBuilderId()), 13)
        # and see that fbi was only called once
        fbi.assert_called_once_with(u'b1')
        # check that the name was uniciodified
        arg = fbi.mock_calls[0][1][0]
        self.assertIsInstance(arg, unicode)


class TestGetOldestRequestTime(BuilderMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpBuilderMixin()

        # a collection of rows that would otherwise clutter up every test
        master_id = fakedb.FakeBuildRequestsComponent.MASTER_ID
        self.base_rows = [
            fakedb.SourceStamp(id=21),
            fakedb.Buildset(id=11, reason='because'),
            fakedb.BuildsetSourceStamp(buildsetid=11, sourcestampid=21),
            fakedb.Builder(id=77, name='bldr1'),
            fakedb.Builder(id=78, name='bldr2'),
            fakedb.Builder(id=182, name='foo@bar'),
            fakedb.BuildRequest(id=111, submitted_at=1000,
                                builderid=77, buildsetid=11),
            fakedb.BuildRequest(id=222, submitted_at=2000,
                                builderid=77, buildsetid=11),
            fakedb.BuildRequestClaim(brid=222, masterid=master_id,
                                     claimed_at=2001),
            fakedb.BuildRequest(id=333, submitted_at=3000,
                                builderid=77, buildsetid=11),
            fakedb.BuildRequest(id=444, submitted_at=2500,
                                builderid=78, buildsetid=11),
            fakedb.BuildRequestClaim(brid=444, masterid=master_id,
                                     claimed_at=2501),
            fakedb.BuildRequest(id=555, submitted_at=2800,
                                builderid=182, buildsetid=11),
        ]
        yield self.db.insertTestData(self.base_rows)

    @defer.inlineCallbacks
    def test_gort_unclaimed(self):
        yield self.makeBuilder(name='bldr1')
        rqtime = yield self.bldr.getOldestRequestTime()
        self.assertEqual(rqtime, epoch2datetime(1000))

    @defer.inlineCallbacks
    def test_gort_bldr_name_not_identifier(self):
        # this is a regression test for #2940
        yield self.makeBuilder(name='foo@bar')
        rqtime = yield self.bldr.getOldestRequestTime()
        self.assertEqual(rqtime, epoch2datetime(2800))

    @defer.inlineCallbacks
    def test_gort_all_claimed(self):
        yield self.makeBuilder(name='bldr2')
        rqtime = yield self.bldr.getOldestRequestTime()
        self.assertEqual(rqtime, None)


class TestReconfig(BuilderMixin, unittest.TestCase):

    """Tests that a reconfig properly updates all attributes"""

    def setUp(self):
        self.setUpBuilderMixin()

    @defer.inlineCallbacks
    def test_reconfig(self):
        yield self.makeBuilder(description="Old", tags=["OldTag"])
        config_args = dict(name='bldr', slavename="slv", builddir="bdir",
                           slavebuilddir="sbdir", factory=self.factory,
                           description='Noe', tags=['NewTag'])
        new_builder_config = config.BuilderConfig(**config_args)
        new_builder_config.description = "New"
        new_builder_config.tags = ["NewTag"]

        mastercfg = config.MasterConfig()
        mastercfg.builders = [new_builder_config]
        yield self.bldr.reconfigServiceWithBuildbotConfig(mastercfg)
        self.assertEqual(
            dict(description=self.bldr.builder_status.getDescription(),
                 tags=self.bldr.builder_status.getTags()),
            dict(description="New",
                 tags=["NewTag"]))
        self.assertIdentical(self.bldr.config, new_builder_config)

        # check that the reconfig grabbed a buliderid
        self.assertNotEqual(self.bldr._builderid, None)
