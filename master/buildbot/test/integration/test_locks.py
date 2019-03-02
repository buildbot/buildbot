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

from parameterized import parameterized

from twisted.internet import defer

from buildbot.config import BuilderConfig
from buildbot.plugins import util
from buildbot.process.factory import BuildFactory
from buildbot.process.results import SUCCESS
from buildbot.test.fake.step import BuildStepController
from buildbot.test.util.integration import RunFakeMasterTestCase
from buildbot.util.eventual import flushEventualQueue


class Tests(RunFakeMasterTestCase):
    @defer.inlineCallbacks
    def create_single_worker_two_builder_lock_config(self, lock_cls, mode):
        stepcontrollers = [BuildStepController(), BuildStepController()]

        lock = lock_cls("lock1", maxCount=1)

        config_dict = {
            'builders': [
                BuilderConfig(name='builder1',
                              workernames=['worker1'],
                              factory=BuildFactory([stepcontrollers[0].step]),
                              locks=[lock.access(mode)]),
                BuilderConfig(name='builder2',
                              workernames=['worker1'],
                              factory=BuildFactory([stepcontrollers[1].step]),
                              locks=[lock.access(mode)]),
            ],
            'workers': [
                self.createLocalWorker('worker1'),
            ],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_ids = [
            (yield master.data.updates.findBuilderId('builder1')),
            (yield master.data.updates.findBuilderId('builder2')),
        ]

        return stepcontrollers, master, builder_ids

    @defer.inlineCallbacks
    def create_single_worker_two_builder_step_lock_config(self, lock_cls, mode):
        lock = lock_cls("lock1", maxCount=1)

        stepcontrollers = [BuildStepController(locks=[lock.access(mode)]),
                           BuildStepController(locks=[lock.access(mode)])]

        config_dict = {
            'builders': [
                BuilderConfig(name='builder1',
                              workernames=['worker1'],
                              factory=BuildFactory([stepcontrollers[0].step])),
                BuilderConfig(name='builder2',
                              workernames=['worker1'],
                              factory=BuildFactory([stepcontrollers[1].step])),
            ],
            'workers': [
                self.createLocalWorker('worker1'),
            ],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_ids = [
            (yield master.data.updates.findBuilderId('builder1')),
            (yield master.data.updates.findBuilderId('builder2')),
        ]

        return stepcontrollers, master, builder_ids

    @defer.inlineCallbacks
    def create_two_worker_two_builder_lock_config(self, mode):
        stepcontrollers = [BuildStepController(), BuildStepController()]

        master_lock = util.MasterLock("lock1", maxCount=1)

        config_dict = {
            'builders': [
                BuilderConfig(name='builder1',
                              workernames=['worker1'],
                              factory=BuildFactory([stepcontrollers[0].step]),
                              locks=[master_lock.access(mode)]),
                BuilderConfig(name='builder2',
                              workernames=['worker2'],
                              factory=BuildFactory([stepcontrollers[1].step]),
                              locks=[master_lock.access(mode)]),
            ],
            'workers': [
                self.createLocalWorker('worker1'),
                self.createLocalWorker('worker2'),
            ],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_ids = [
            (yield master.data.updates.findBuilderId('builder1')),
            (yield master.data.updates.findBuilderId('builder2')),
        ]

        return stepcontrollers, master, builder_ids

    @defer.inlineCallbacks
    def assert_two_builds_created_one_after_another(self, stepcontrollers,
                                                    master, builder_ids):
        # start two builds and verify that a second build starts after the
        # first is finished
        yield self.createBuildrequest(master, [builder_ids[0]])
        yield self.createBuildrequest(master, [builder_ids[1]])

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0]['results'], None)
        self.assertEqual(builds[0]['builderid'], builder_ids[0])

        stepcontrollers[0].finish_step(SUCCESS)

        # execute Build.releaseLocks which is called eventually
        yield flushEventualQueue()

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), 2)
        self.assertEqual(builds[0]['results'], SUCCESS)
        self.assertEqual(builds[1]['results'], None)
        self.assertEqual(builds[1]['builderid'], builder_ids[1])

        stepcontrollers[1].finish_step(SUCCESS)

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), 2)
        self.assertEqual(builds[0]['results'], SUCCESS)
        self.assertEqual(builds[1]['results'], SUCCESS)

    @defer.inlineCallbacks
    def assert_two_steps_created_one_after_another(self, stepcontrollers,
                                                   master, builder_ids):
        # start two builds and verify that a second build starts after the
        # first is finished
        yield self.createBuildrequest(master, [builder_ids[0]])
        yield self.createBuildrequest(master, [builder_ids[1]])

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), 2)
        self.assertEqual(builds[0]['results'], None)
        self.assertEqual(builds[0]['builderid'], builder_ids[0])
        self.assertEqual(builds[1]['results'], None)
        self.assertEqual(builds[1]['builderid'], builder_ids[1])

        self.assertTrue(stepcontrollers[0].running)
        self.assertFalse(stepcontrollers[1].running)

        stepcontrollers[0].finish_step(SUCCESS)
        yield flushEventualQueue()

        self.assertFalse(stepcontrollers[0].running)
        self.assertTrue(stepcontrollers[1].running)

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), 2)
        self.assertEqual(builds[0]['results'], SUCCESS)
        self.assertEqual(builds[1]['results'], None)

        stepcontrollers[1].finish_step(SUCCESS)
        yield flushEventualQueue()

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), 2)
        self.assertEqual(builds[0]['results'], SUCCESS)
        self.assertEqual(builds[1]['results'], SUCCESS)

    @parameterized.expand([
        (util.MasterLock, 'counting'),
        (util.MasterLock, 'exclusive'),
        (util.WorkerLock, 'counting'),
        (util.WorkerLock, 'exclusive'),
    ])
    @defer.inlineCallbacks
    def test_builder_lock_prevents_concurrent_builds(self, lock_cls, mode):
        '''
        Tests whether a builder lock works at all in preventing a build when
        the lock is taken.
        '''
        stepcontrollers, master, builder_ids = \
            yield self.create_single_worker_two_builder_lock_config(lock_cls,
                                                                    mode)

        yield self.assert_two_builds_created_one_after_another(
            stepcontrollers, master, builder_ids)

    @parameterized.expand([
        (util.MasterLock, 'counting'),
        (util.MasterLock, 'exclusive'),
        (util.WorkerLock, 'counting'),
        (util.WorkerLock, 'exclusive'),
    ])
    @defer.inlineCallbacks
    def test_step_lock_prevents_concurrent_builds(self, lock_cls, mode):
        '''
        Tests whether a builder lock works at all in preventing a build when
        the lock is taken.
        '''
        stepcontrollers, master, builder_ids = \
            yield self.create_single_worker_two_builder_step_lock_config(
                lock_cls, mode)
        yield self.assert_two_steps_created_one_after_another(
            stepcontrollers, master, builder_ids)

    @parameterized.expand(['counting', 'exclusive'])
    @defer.inlineCallbacks
    def test_builder_lock_release_wakes_builds_for_another_builder(self, mode):
        """
        If a builder locks a master lock then the build request distributor
        must retry running any buildrequests that might have been not scheduled
        due to unavailability of that lock when the lock becomes available.
        """
        stepcontrollers, master, builder_ids = \
            yield self.create_two_worker_two_builder_lock_config(mode)

        yield self.assert_two_builds_created_one_after_another(
            stepcontrollers, master, builder_ids)


class TestReconfig(RunFakeMasterTestCase):

    def create_stepcontrollers(self, count, lock, mode):
        stepcontrollers = []
        for i in range(count):
            locks = [lock.access(mode)] if lock is not None else []
            stepcontrollers.append(BuildStepController(locks=locks))
        return stepcontrollers

    def update_builder_config(self, config_dict, stepcontrollers, lock, mode):
        config_dict['builders'] = []
        for i, stepcontroller in enumerate(stepcontrollers):
            locks = [lock.access(mode)] if lock is not None else []
            b = BuilderConfig(name='builder{}'.format(i),
                              workernames=['worker1'],
                              factory=BuildFactory([stepcontroller.step]),
                              locks=locks)
            config_dict['builders'].append(b)

    @defer.inlineCallbacks
    def create_single_worker_n_builder_lock_config(self, builder_count,
                                                   lock_cls, max_count, mode):
        stepcontrollers = self.create_stepcontrollers(builder_count, None, None)

        lock = lock_cls("lock1", maxCount=max_count)

        config_dict = {
            'builders': [],
            'workers': [
                self.createLocalWorker('worker1'),
            ],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        self.update_builder_config(config_dict, stepcontrollers, lock, mode)

        master = yield self.getMaster(config_dict)

        builder_ids = []
        for i in range(builder_count):
            builder_ids.append((
                yield master.data.updates.findBuilderId('builder{}'.format(i))))

        return stepcontrollers, master, config_dict, lock, builder_ids

    @defer.inlineCallbacks
    def create_single_worker_n_builder_step_lock_config(self, builder_count,
                                                        lock_cls, max_count,
                                                        mode):
        lock = lock_cls("lock1", maxCount=max_count)
        stepcontrollers = self.create_stepcontrollers(builder_count, lock, mode)

        config_dict = {
            'builders': [],
            'workers': [
                self.createLocalWorker('worker1'),
            ],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        self.update_builder_config(config_dict, stepcontrollers, None, None)

        master = yield self.getMaster(config_dict)

        builder_ids = []
        for i in range(builder_count):
            builder_ids.append((
                yield master.data.updates.findBuilderId('builder{}'.format(i))))

        return stepcontrollers, master, config_dict, lock, builder_ids

    @parameterized.expand([
        (3, util.MasterLock, 'counting', 1, 2, 1, 3),
        (3, util.WorkerLock, 'counting', 1, 2, 1, 3),
        (3, util.MasterLock, 'counting', 2, 1, 2, 3),
        (3, util.WorkerLock, 'counting', 2, 1, 2, 3),
        (2, util.MasterLock, 'exclusive', 1, 2, 1, 2),
        (2, util.WorkerLock, 'exclusive', 1, 2, 1, 2),
        (2, util.MasterLock, 'exclusive', 2, 1, 1, 2),
        (2, util.WorkerLock, 'exclusive', 2, 1, 1, 2),
    ])
    @defer.inlineCallbacks
    def test_changing_max_lock_count_does_not_break_builder_locks(
            self, builder_count, lock_cls, mode, max_count_before,
            max_count_after, allowed_builds_before, allowed_builds_after):
        # TODO: the test currently demonstrates broken behavior
        '''
        Check that Buildbot does not allow extra claims on a claimed lock after
        a reconfig that changed the maxCount of that lock. Some Buildbot
        versions created a completely separate real lock after each maxCount
        change, which allowed to e.g. take an exclusive lock twice.
        '''
        stepcontrollers, master, config_dict, lock, builder_ids = \
            yield self.create_single_worker_n_builder_lock_config(
                builder_count, lock_cls, max_count_before, mode)

        # create a number of builds and check that the expected number of them
        # start
        for i in range(builder_count):
            yield self.createBuildrequest(master, [builder_ids[i]])

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), allowed_builds_before)

        # update the config and reconfig the master
        lock = lock_cls(lock.name, maxCount=max_count_after)
        self.update_builder_config(config_dict, stepcontrollers, lock, mode)
        yield master.reconfig()
        yield flushEventualQueue()

        # check that the number of running builds matches expectation
        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), allowed_builds_after)

        # finish the steps and check that builds finished as expected
        for stepcontroller in stepcontrollers:
            stepcontroller.finish_step(SUCCESS)
            yield flushEventualQueue()

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), allowed_builds_after)
        for b in builds:
            self.assertEqual(b['results'], SUCCESS)

    @parameterized.expand([
        (3, util.MasterLock, 'counting', 1, 2, 1, 3),
        (3, util.WorkerLock, 'counting', 1, 2, 1, 3),
        (3, util.MasterLock, 'counting', 2, 1, 2, 3),
        (3, util.WorkerLock, 'counting', 2, 1, 2, 3),
        (2, util.MasterLock, 'exclusive', 1, 2, 1, 2),
        (2, util.WorkerLock, 'exclusive', 1, 2, 1, 2),
        (2, util.MasterLock, 'exclusive', 2, 1, 1, 2),
        (2, util.WorkerLock, 'exclusive', 2, 1, 1, 2),
    ])
    @defer.inlineCallbacks
    def test_changing_max_lock_count_does_not_break_step_locks(
            self, builder_count, lock_cls, mode, max_count_before,
            max_count_after, allowed_steps_before, allowed_steps_after):
        # TODO: the test currently demonstrates broken behavior
        '''
        Check that Buildbot does not allow extra claims on a claimed lock after
        a reconfig that changed the maxCount of that lock. Some Buildbot
        versions created a completely separate real lock after each maxCount
        change, which allowed to e.g. take an exclusive lock twice.
        '''
        stepcontrollers, master, config_dict, lock, builder_ids = \
            yield self.create_single_worker_n_builder_step_lock_config(
                builder_count, lock_cls, max_count_before, mode)

        # create a number of builds and check that the expected number of them
        # start their steps
        for i in range(builder_count):
            yield self.createBuildrequest(master, [builder_ids[i]])

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), builder_count)

        self.assertEqual(sum(sc.running for sc in stepcontrollers),
                         allowed_steps_before)

        # update the config and reconfig the master
        lock = lock_cls(lock.name, maxCount=max_count_after)
        new_stepcontrollers = \
            self.create_stepcontrollers(builder_count, lock, mode)

        self.update_builder_config(config_dict, new_stepcontrollers, lock, mode)
        yield master.reconfig()
        yield flushEventualQueue()

        # check that all builds are still running
        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), builder_count)

        # check that the expected number of steps has been started and that
        # none of the new steps has been started
        self.assertEqual(sum(sc.running for sc in stepcontrollers),
                         allowed_steps_before)
        self.assertEqual(sum(sc.running for sc in new_stepcontrollers), 0)

        # finish the steps and check that builds finished as expected
        for stepcontroller in stepcontrollers:
            stepcontroller.finish_step(SUCCESS)
            yield flushEventualQueue()

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), builder_count)
        for b in builds:
            self.assertEqual(b['results'], SUCCESS)

        self.assertEqual(sum(sc.running for sc in stepcontrollers), 0)
        self.assertEqual(sum(sc.running for sc in new_stepcontrollers), 0)
