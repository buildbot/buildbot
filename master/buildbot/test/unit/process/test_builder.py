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
from twisted.trial import unittest

from buildbot import config
from buildbot.config.master import MasterConfig
from buildbot.process import builder
from buildbot.process import factory
from buildbot.process.properties import Properties
from buildbot.process.properties import renderer
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.util import epoch2datetime
from buildbot.worker import AbstractLatentWorker


class BuilderMixin:
    def setUpBuilderMixin(self):
        self.factory = factory.BuildFactory()
        self.master = fakemaster.make_master(self, wantData=True)
        self.mq = self.master.mq
        self.db = self.master.db

    # returns a Deferred that returns None
    def makeBuilder(self, name="bldr", patch_random=False, noReconfig=False, **config_kwargs):
        """Set up C{self.bldr}"""
        # only include the necessary required config, plus user-requested
        self.config_args = {
            'name': name,
            'workername': 'wrk',
            'builddir': 'bdir',
            'workerbuilddir': "wbdir",
            'factory': self.factory,
        }
        self.config_args.update(config_kwargs)
        self.builder_config = config.BuilderConfig(**self.config_args)

        self.bldr = builder.Builder(self.builder_config.name)
        self.bldr.master = self.master
        self.bldr.botmaster = self.master.botmaster

        # patch into the _startBuildsFor method
        self.builds_started = []

        def _startBuildFor(workerforbuilder, buildrequests):
            self.builds_started.append((workerforbuilder, buildrequests))
            return defer.succeed(True)

        self.bldr._startBuildFor = _startBuildFor

        if patch_random:
            # patch 'random.choice' to always take the worker that sorts
            # last, based on its name
            self.patch(random, "choice", lambda lst: sorted(lst, key=lambda m: m.name)[-1])

        self.bldr.startService()

        mastercfg = MasterConfig()
        mastercfg.builders = [self.builder_config]
        if not noReconfig:
            return self.bldr.reconfigServiceWithBuildbotConfig(mastercfg)


class FakeWorker:
    builds_may_be_incompatible = False

    def __init__(self, workername):
        self.workername = workername


class FakeLatentWorker(AbstractLatentWorker):
    builds_may_be_incompatible = True

    def __init__(self, is_compatible_with_build):
        self.is_compatible_with_build = is_compatible_with_build

    def isCompatibleWithBuild(self, build_props):
        return defer.succeed(self.is_compatible_with_build)

    def checkConfig(self, name, _, **kwargs):
        pass

    def reconfigService(self, name, _, **kwargs):
        pass


class TestBuilder(TestReactorMixin, BuilderMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        # a collection of rows that would otherwise clutter up every test
        self.setUpBuilderMixin()
        self.base_rows = [
            fakedb.SourceStamp(id=21),
            fakedb.Buildset(id=11, reason='because'),
            fakedb.BuildsetSourceStamp(buildsetid=11, sourcestampid=21),
        ]

    async def makeBuilder(self, patch_random=False, startBuildsForSucceeds=True, **config_kwargs):
        await super().makeBuilder(patch_random=patch_random, **config_kwargs)

        # patch into the _startBuildsFor method
        self.builds_started = []

        def _startBuildFor(workerforbuilder, buildrequests):
            self.builds_started.append((workerforbuilder, buildrequests))
            return defer.succeed(startBuildsForSucceeds)

        self.bldr._startBuildFor = _startBuildFor

    def assertBuildsStarted(self, exp):
        # munge builds_started into a list of (worker, [brids])
        builds_started = [
            (wrk.name, [br.id for br in buildreqs]) for (wrk, buildreqs) in self.builds_started
        ]
        self.assertEqual(sorted(builds_started), sorted(exp))

    def setWorkerForBuilders(self, workerforbuilders):
        """C{workerforbuilders} maps name : available"""
        self.bldr.workers = []
        for name, avail in workerforbuilders.items():
            wfb = mock.Mock(spec=['isAvailable'], name=name)
            wfb.name = name
            wfb.isAvailable.return_value = avail
            self.bldr.workers.append(wfb)

    # services

    async def test_maybeStartBuild_builder_stopped(self):
        await self.makeBuilder()

        # this will cause an exception if maybeStartBuild tries to start
        self.bldr.workers = None

        # so we just hope this does not fail
        await self.bldr.stopService()
        started = await self.bldr.maybeStartBuild(None, [])
        self.assertEqual(started, False)

    # maybeStartBuild
    def _makeMocks(self):
        worker = mock.Mock()
        worker.name = 'worker'
        buildrequest = mock.Mock()
        buildrequest.id = 10
        buildrequests = [buildrequest]
        return worker, buildrequests

    async def test_maybeStartBuild(self):
        await self.makeBuilder()

        worker, buildrequests = self._makeMocks()

        started = await self.bldr.maybeStartBuild(worker, buildrequests)
        self.assertEqual(started, True)
        self.assertBuildsStarted([('worker', [10])])

    async def test_maybeStartBuild_failsToStart(self):
        await self.makeBuilder(startBuildsForSucceeds=False)

        worker, buildrequests = self._makeMocks()

        started = await self.bldr.maybeStartBuild(worker, buildrequests)
        self.assertEqual(started, False)
        self.assertBuildsStarted([('worker', [10])])

    async def do_test_getCollapseRequestsFn(
        self, builder_param=None, global_param=None, expected=0
    ):
        def cble():
            pass

        builder_param = cble if builder_param == 'callable' else builder_param
        global_param = cble if global_param == 'callable' else global_param

        # omit the constructor parameter if None was given
        if builder_param is None:
            await self.makeBuilder()
        else:
            await self.makeBuilder(collapseRequests=builder_param)

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

    # canStartBuild

    async def test_canStartBuild_no_constraints(self):
        await self.makeBuilder()

        wfb = mock.Mock()
        wfb.worker = FakeWorker('worker')

        startable = await self.bldr.canStartBuild(wfb, 100)
        self.assertEqual(startable, True)

        startable = await self.bldr.canStartBuild(wfb, 101)
        self.assertEqual(startable, True)

    async def test_canStartBuild_config_canStartBuild_returns_value(self):
        await self.makeBuilder()

        def canStartBuild(bldr, worker, breq):
            return breq == 100

        canStartBuild = mock.Mock(side_effect=canStartBuild)

        self.bldr.config.canStartBuild = canStartBuild

        wfb = mock.Mock()
        wfb.worker = FakeWorker('worker')

        startable = await self.bldr.canStartBuild(wfb, 100)
        self.assertEqual(startable, True)
        canStartBuild.assert_called_with(self.bldr, wfb, 100)
        canStartBuild.reset_mock()

        startable = await self.bldr.canStartBuild(wfb, 101)
        self.assertEqual(startable, False)
        canStartBuild.assert_called_with(self.bldr, wfb, 101)
        canStartBuild.reset_mock()

    async def test_canStartBuild_config_canStartBuild_returns_deferred(self):
        await self.makeBuilder()

        wfb = mock.Mock()
        wfb.worker = FakeWorker('worker')

        def canStartBuild(bldr, wfb, breq):
            return defer.succeed(breq == 100)

        canStartBuild = mock.Mock(side_effect=canStartBuild)

        self.bldr.config.canStartBuild = canStartBuild

        startable = await self.bldr.canStartBuild(wfb, 100)
        self.assertEqual(startable, True)
        canStartBuild.assert_called_with(self.bldr, wfb, 100)
        canStartBuild.reset_mock()

        startable = await self.bldr.canStartBuild(wfb, 101)
        self.assertEqual(startable, False)
        canStartBuild.assert_called_with(self.bldr, wfb, 101)
        canStartBuild.reset_mock()

    async def test_canStartBuild_cant_acquire_locks_but_no_locks(self):
        await self.makeBuilder()

        self.bldr.config.locks = [mock.Mock]
        self.bldr.botmaster.getLockFromLockAccesses = mock.Mock(return_value=[])
        self.bldr._can_acquire_locks = lambda _: False

        wfb = mock.Mock()
        wfb.worker = FakeWorker('worker')

        startable = await self.bldr.canStartBuild(wfb, 100)
        self.assertEqual(startable, True)

    async def test_canStartBuild_with_locks(self):
        await self.makeBuilder()

        self.bldr.config.locks = [mock.Mock]
        self.bldr.botmaster.getLockFromLockAccesses = mock.Mock(
            return_value=[(mock.Mock(), mock.Mock())]
        )
        self.bldr._can_acquire_locks = lambda _: False

        wfb = mock.Mock()
        wfb.worker = FakeWorker('worker')

        startable = await self.bldr.canStartBuild(wfb, 100)
        self.assertEqual(startable, False)

    async def test_canStartBuild_with_renderable_locks(self):
        await self.makeBuilder()

        self.bldr.botmaster.getLockFromLockAccesses = mock.Mock(
            return_value=[(mock.Mock(), mock.Mock())]
        )

        renderedLocks = [False]

        @renderer
        def rendered_locks(props):
            renderedLocks[0] = True
            return [mock.Mock()]

        self.bldr.config.locks = rendered_locks
        self.bldr._can_acquire_locks = lambda _: False

        wfb = mock.Mock()
        wfb.worker = FakeWorker('worker')

        with mock.patch(
            'buildbot.process.build.Build.setup_properties_known_before_build_starts', mock.Mock()
        ):
            startable = await self.bldr.canStartBuild(wfb, 100)
            self.assertEqual(startable, False)

        self.assertTrue(renderedLocks[0])

    async def test_canStartBuild_with_incompatible_latent_worker(self):
        await self.makeBuilder()

        wfb = mock.Mock()
        wfb.worker = FakeLatentWorker(is_compatible_with_build=False)

        with mock.patch(
            'buildbot.process.build.Build.setup_properties_known_before_build_starts', mock.Mock()
        ):
            startable = await self.bldr.canStartBuild(wfb, 100)
        self.assertFalse(startable)

    async def test_canStartBuild_with_renderable_locks_with_compatible_latent_worker(self):
        await self.makeBuilder()

        self.bldr.config.locks = [mock.Mock]
        self.bldr.botmaster.getLockFromLockAccesses = mock.Mock(
            return_value=[(mock.Mock(), mock.Mock())]
        )

        rendered_locks = [False]

        @renderer
        def locks_renderer(props):
            rendered_locks[0] = True
            return [mock.Mock()]

        self.bldr.config.locks = locks_renderer
        self.bldr._can_acquire_locks = lambda _: False

        wfb = mock.Mock()
        wfb.worker = FakeLatentWorker(is_compatible_with_build=True)

        with mock.patch(
            'buildbot.process.build.Build.setup_properties_known_before_build_starts', mock.Mock()
        ):
            startable = await self.bldr.canStartBuild(wfb, 100)
            self.assertEqual(startable, False)
        self.assertFalse(startable)
        self.assertTrue(rendered_locks[0])

    async def test_canStartBuild_enforceChosenWorker(self):
        """enforceChosenWorker rejects and accepts builds"""
        await self.makeBuilder()

        self.bldr.config.canStartBuild = builder.enforceChosenWorker

        workerforbuilder = mock.Mock()
        workerforbuilder.worker = FakeWorker('worker5')

        breq = mock.Mock()

        # no worker requested
        breq.properties = {}
        result = await self.bldr.canStartBuild(workerforbuilder, breq)
        self.assertIdentical(True, result)

        # worker requested as the right one
        breq.properties = {'workername': 'worker5'}
        result = await self.bldr.canStartBuild(workerforbuilder, breq)
        self.assertIdentical(True, result)

        # worker requested as the wrong one
        breq.properties = {'workername': 'worker4'}
        result = await self.bldr.canStartBuild(workerforbuilder, breq)
        self.assertIdentical(False, result)

        # worker set to non string value gets skipped
        breq.properties = {'workername': 0}
        result = await self.bldr.canStartBuild(workerforbuilder, breq)
        self.assertIdentical(True, result)

    # other methods

    async def test_getBuilderId(self):
        self.factory = factory.BuildFactory()
        self.master = fakemaster.make_master(self, wantData=True)
        # only include the necessary required config, plus user-requested
        self.bldr = builder.Builder('bldr')
        self.bldr.master = self.master
        self.master.data.updates.findBuilderId = fbi = mock.Mock()
        fbi.return_value = defer.succeed(13)

        builderid = await self.bldr.getBuilderId()
        self.assertEqual(builderid, 13)
        fbi.assert_called_with('bldr')
        fbi.reset_mock()

        builderid = await self.bldr.getBuilderId()
        self.assertEqual(builderid, 13)
        fbi.assert_not_called()

    async def test_expectations_deprecated(self):
        await self.makeBuilder()

        with assertProducesWarning(
            Warning, message_pattern="'Builder.expectations' is deprecated."
        ):
            deprecated = self.bldr.expectations

        self.assertIdentical(deprecated, None)

    async def test_defaultProperties(self):
        props = Properties()
        props.setProperty('foo', 1, 'Scheduler')
        props.setProperty('bar', 'bleh', 'Change')

        await self.makeBuilder(defaultProperties={'bar': 'onoes', 'cuckoo': 42})

        await self.bldr.setup_properties(props)

        self.assertEqual(props.getProperty('bar'), 'bleh')
        self.assertEqual(props.getProperty('cuckoo'), 42)


class TestGetBuilderId(TestReactorMixin, BuilderMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.setUpBuilderMixin()

    async def test_getBuilderId(self):
        # noReconfig because reconfigService calls getBuilderId, and we haven't
        # set up the mock findBuilderId yet.
        await self.makeBuilder(name='b1', noReconfig=True)
        fbi = self.master.data.updates.findBuilderId = mock.Mock(name='fbi')
        fbi.side_effect = lambda name: defer.succeed(13)
        # call twice..
        self.assertEqual((yield self.bldr.getBuilderId()), 13)
        self.assertEqual((yield self.bldr.getBuilderId()), 13)
        # and see that fbi was only called once
        fbi.assert_called_once_with('b1')
        # check that the name was unicodified
        arg = fbi.mock_calls[0][1][0]
        self.assertIsInstance(arg, str)


class TestGetOldestRequestTime(TestReactorMixin, BuilderMixin, unittest.TestCase):
    async def setUp(self):
        self.setup_test_reactor()
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
            fakedb.BuildRequest(id=111, submitted_at=1000, builderid=77, buildsetid=11),
            fakedb.BuildRequest(id=222, submitted_at=2000, builderid=77, buildsetid=11),
            fakedb.BuildRequestClaim(brid=222, masterid=master_id, claimed_at=2001),
            fakedb.BuildRequest(id=333, submitted_at=3000, builderid=77, buildsetid=11),
            fakedb.BuildRequest(id=444, submitted_at=2500, builderid=78, buildsetid=11),
            fakedb.BuildRequestClaim(brid=444, masterid=master_id, claimed_at=2501),
            fakedb.BuildRequest(id=555, submitted_at=2800, builderid=182, buildsetid=11),
        ]
        await self.db.insert_test_data(self.base_rows)

    async def test_gort_unclaimed(self):
        await self.makeBuilder(name='bldr1')
        rqtime = await self.bldr.getOldestRequestTime()
        self.assertEqual(rqtime, epoch2datetime(1000))

    async def test_gort_bldr_name_not_identifier(self):
        # this is a regression test for #2940
        await self.makeBuilder(name='foo@bar')
        rqtime = await self.bldr.getOldestRequestTime()
        self.assertEqual(rqtime, epoch2datetime(2800))

    async def test_gort_all_claimed(self):
        await self.makeBuilder(name='bldr2')
        rqtime = await self.bldr.getOldestRequestTime()
        self.assertEqual(rqtime, None)


class TestGetNewestCompleteTime(TestReactorMixin, BuilderMixin, unittest.TestCase):
    async def setUp(self):
        self.setup_test_reactor()
        self.setUpBuilderMixin()

        # a collection of rows that would otherwise clutter up every test
        master_id = fakedb.FakeBuildRequestsComponent.MASTER_ID
        self.base_rows = [
            fakedb.SourceStamp(id=21),
            fakedb.Buildset(id=11, reason='because'),
            fakedb.BuildsetSourceStamp(buildsetid=11, sourcestampid=21),
            fakedb.Builder(id=77, name='bldr1'),
            fakedb.Builder(id=78, name='bldr2'),
            fakedb.BuildRequest(
                id=111, submitted_at=1000, complete=1, complete_at=1000, builderid=77, buildsetid=11
            ),
            fakedb.BuildRequest(
                id=222, submitted_at=2000, complete=1, complete_at=4000, builderid=77, buildsetid=11
            ),
            fakedb.BuildRequest(
                id=333, submitted_at=3000, complete=1, complete_at=3000, builderid=77, buildsetid=11
            ),
            fakedb.BuildRequest(id=444, submitted_at=2500, builderid=78, buildsetid=11),
            fakedb.BuildRequestClaim(brid=444, masterid=master_id, claimed_at=2501),
        ]
        await self.db.insert_test_data(self.base_rows)

    async def test_gnct_completed(self):
        await self.makeBuilder(name='bldr1')
        rqtime = await self.bldr.getNewestCompleteTime()
        self.assertEqual(rqtime, epoch2datetime(4000))

    async def test_gnct_no_completed(self):
        await self.makeBuilder(name='bldr2')
        rqtime = await self.bldr.getNewestCompleteTime()
        self.assertEqual(rqtime, None)


class TestGetHighestPriority(TestReactorMixin, BuilderMixin, unittest.TestCase):
    async def setUp(self):
        self.setup_test_reactor()
        self.setUpBuilderMixin()

        # a collection of rows that would otherwise clutter up every test
        master_id = fakedb.FakeBuildRequestsComponent.MASTER_ID
        self.base_rows = [
            fakedb.SourceStamp(id=21),
            fakedb.Buildset(id=11, reason='because'),
            fakedb.BuildsetSourceStamp(buildsetid=11, sourcestampid=21),
            fakedb.Builder(id=77, name='bldr1'),
            fakedb.Builder(id=78, name='bldr2'),
            fakedb.BuildRequest(id=111, submitted_at=1000, builderid=77, buildsetid=11, priority=0),
            fakedb.BuildRequest(
                id=222, submitted_at=2000, builderid=77, buildsetid=11, priority=10
            ),
            fakedb.BuildRequestClaim(brid=222, masterid=master_id, claimed_at=2001),
            fakedb.BuildRequest(id=333, submitted_at=3000, builderid=77, buildsetid=11, priority=5),
            fakedb.BuildRequest(id=444, submitted_at=3001, builderid=77, buildsetid=11, priority=3),
            fakedb.BuildRequest(id=555, submitted_at=2500, builderid=78, buildsetid=11),
            fakedb.BuildRequestClaim(brid=555, masterid=master_id, claimed_at=2501),
        ]
        await self.db.insert_test_data(self.base_rows)

    async def test_ghp_unclaimed(self):
        await self.makeBuilder(name='bldr1')
        priority = await self.bldr.get_highest_priority()
        self.assertEqual(priority, 5)

    async def test_ghp_all_claimed(self):
        await self.makeBuilder(name='bldr2')
        priority = await self.bldr.get_highest_priority()
        self.assertEqual(priority, None)


class TestReconfig(TestReactorMixin, BuilderMixin, unittest.TestCase):
    """Tests that a reconfig properly updates all attributes"""

    async def setUp(self):
        self.setup_test_reactor()
        self.setUpBuilderMixin()

        await self.db.insert_test_data([
            fakedb.Project(id=301, name='old_project'),
            fakedb.Project(id=302, name='new_project'),
        ])

    async def test_reconfig(self):
        await self.makeBuilder(description="Old", project="old_project", tags=["OldTag"])
        new_builder_config = config.BuilderConfig(**self.config_args)
        new_builder_config.description = "New"
        new_builder_config.project = "new_project"
        new_builder_config.tags = ["NewTag"]

        mastercfg = MasterConfig()
        mastercfg.builders = [new_builder_config]
        await self.bldr.reconfigServiceWithBuildbotConfig(mastercfg)

        # check that the reconfig grabbed a builderid
        self.assertIsNotNone(self.bldr._builderid)

        builder_dict = await self.master.data.get(('builders', self.bldr._builderid))
        self.assertEqual(builder_dict['description'], 'New')
        self.assertEqual(builder_dict['projectid'], 302)
        self.assertEqual(builder_dict['tags'], ['NewTag'])

        self.assertIdentical(self.bldr.config, new_builder_config)

    @parameterized.expand([
        ('only_description', 'New', 'old_project', ['OldTag'], 301),
        ('only_project', 'Old', 'new_project', ['OldTag'], 302),
        ('only_tags', 'Old', 'old_project', ['NewTag'], 301),
    ])
    async def test_reconfig_changed(self, name, new_desc, new_project, new_tags, expect_project_id):
        await self.makeBuilder(description="Old", project='old_project', tags=["OldTag"])
        new_builder_config = config.BuilderConfig(**self.config_args)
        new_builder_config.description = new_desc
        new_builder_config.tags = new_tags
        new_builder_config.project = new_project

        mastercfg = MasterConfig()
        mastercfg.builders = [new_builder_config]

        builder_updates = []
        self.master.data.updates.updateBuilderInfo = (
            lambda builderid,
            desc,
            desc_format,
            desc_html,
            projectid,
            tags: builder_updates.append((builderid, desc, desc_format, desc_html, projectid, tags))
        )

        await self.bldr.reconfigServiceWithBuildbotConfig(mastercfg)
        self.assertEqual(builder_updates, [(1, new_desc, None, None, expect_project_id, new_tags)])

    async def test_does_not_reconfig_identical(self):
        await self.makeBuilder(description="Old", project="old_project", tags=["OldTag"])
        new_builder_config = config.BuilderConfig(**self.config_args)

        mastercfg = MasterConfig()
        mastercfg.builders = [new_builder_config]

        builder_updates = []
        self.master.data.updates.updateBuilderInfo = (
            lambda builderid,
            desc,
            desc_format,
            desc_html,
            projectid,
            tags: builder_updates.append((builderid, desc, desc_format, desc_html, projectid, tags))
        )

        await self.bldr.reconfigServiceWithBuildbotConfig(mastercfg)
        self.assertEqual(builder_updates, [])
