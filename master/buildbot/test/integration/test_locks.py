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
