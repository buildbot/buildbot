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
# Portions Copyright Buildbot Team Members

from twisted.internet import defer
from zope.interface import implementer

from buildbot import interfaces
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.test.fake.latent import ControllableLatentWorkerMixin
from buildbot.test.fake.latent import LatentController
from buildbot.test.fake.step import BuildStepController
from buildbot.test.util.integration import getMaster
from buildbot.test.util.misc import DebugIntegrationLogsMixin
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.misc import TimeoutableTestCase
from buildbot.worker.suspendable import SuspendableMachine
from buildbot.worker.suspendable import SuspendableWorker


class ControllableSuspendableWorker(ControllableLatentWorkerMixin,
                                    SuspendableWorker):

    def checkConfig(self, name, _, **kwargs):
        SuspendableWorker.checkConfig(self, name, None, **kwargs)

    def reconfigService(self, name, _, **kwargs):
        SuspendableWorker.reconfigService(self, name, None, **kwargs)

    @defer.inlineCallbacks
    def start_instance(self, build):
        yield ControllableLatentWorkerMixin.start_instance(self, build)
        ret = yield SuspendableWorker.start_instance(self, build)
        defer.returnValue(ret)

    @defer.inlineCallbacks
    def stop_instance(self, fast=False):
        yield ControllableLatentWorkerMixin.stop_instance(self, fast)
        ret = yield SuspendableWorker.stop_instance(self, fast)
        defer.returnValue(ret)


@implementer(interfaces.IMachineAction)
class FakeAction(object):
    def __init__(self, controller, attr):
        self._controller = controller
        self._attr = attr

    def perform(self, manager):
        deferred = defer.Deferred()
        setattr(self._controller, self._attr, deferred)
        return deferred


class SuspendableMachineController(object):
    ''' A controller for ``SuspendableMachine``
    '''

    def __init__(self, name, **kwargs):
        self._suspend_action = FakeAction(self, '_suspend_deferred')
        self._wake_action = FakeAction(self, '_wake_deferred')
        self._suspend_deferred = None
        self._wake_deferred = None
        self.manager = SuspendableMachine(
            name,
            wake_action=self._wake_action,
            suspend_action=self._suspend_action,
            **kwargs)

    def wake(self, result):
        assert self.manager.state == SuspendableMachine.STATE_STARTING
        d, self._wake_deferred = self._wake_deferred, None
        if isinstance(result, Exception):
            d.errback(result)
        else:
            d.callback(result)

    def suspend(self, result=None):
        assert self.manager.state == SuspendableMachine.STATE_SUSPENDING
        d, self._suspend_deferred = self._suspend_deferred, None
        if isinstance(result, Exception):
            d.errback(result)
        else:
            d.callback(result)


class TestSuspendable(TimeoutableTestCase, TestReactorMixin,
                      DebugIntegrationLogsMixin):

    def setUp(self):
        self.setUpTestReactor()
        self.setupDebugIntegrationLogs()

    def tearDown(self):
        # Flush the errors logged by the master stop cancelling the builds.
        self.flushLoggedErrors(interfaces.LatentWorkerSubstantiatiationCancelled)
        self.assertFalse(self.master.running, "master is still running!")

    @defer.inlineCallbacks
    def getMaster(self, config_dict):
        self.master = master = yield getMaster(self, self.reactor, config_dict)
        return master

    # returns Deferred
    def createBuildrequest(self, master, builder_ids):
        return master.data.updates.addBuildset(
            waited_for=False,
            builderids=builder_ids,
            sourcestamps=[
                {'codebase': '',
                 'repository': '',
                 'branch': None,
                 'revision': None,
                 'project': ''},
            ],
        )

    def createLatentController(self, name):
        return LatentController(self, name,
                                worker_class=ControllableSuspendableWorker)

    @defer.inlineCallbacks
    def create_single_worker_config(self, build_wait_timeout=0):
        manager_controller = SuspendableMachineController(
            name='a', workernames=['worker1'],
            build_wait_timeout=build_wait_timeout)

        worker_controller = self.createLatentController('worker1')
        step_controller = BuildStepController()

        config_dict = {
            'suspendableMachines': [
                manager_controller.manager
            ],
            'builders': [
                BuilderConfig(name="builder1",
                              workernames=["worker1"],
                              factory=BuildFactory([step_controller.step]),
                              ),
            ],
            'workers': [worker_controller.worker],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }

        master = yield self.getMaster(config_dict)
        builder_id = yield master.data.updates.findBuilderId('builder1')

        return (manager_controller, worker_controller, step_controller,
                master, builder_id)

    @defer.inlineCallbacks
    def create_two_worker_config(self, build_wait_timeout=0):
        manager_controller = SuspendableMachineController(
            name='a', workernames=['worker1', 'worker2'],
            build_wait_timeout=build_wait_timeout)

        worker1_controller = self.createLatentController('worker1')
        worker2_controller = self.createLatentController('worker2')
        step1_controller = BuildStepController()
        step2_controller = BuildStepController()

        config_dict = {
            'suspendableMachines': [
                manager_controller.manager
            ],
            'builders': [
                BuilderConfig(name="builder1",
                              workernames=["worker1"],
                              factory=BuildFactory([step1_controller.step]),
                              ),
                BuilderConfig(name="builder2",
                              workernames=["worker2"],
                              factory=BuildFactory([step2_controller.step]),
                              ),
            ],
            'workers': [worker1_controller.worker,
                        worker2_controller.worker],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }

        master = yield self.getMaster(config_dict)
        builder1_id = yield master.data.updates.findBuilderId('builder1')
        builder2_id = yield master.data.updates.findBuilderId('builder2')

        return (manager_controller,
                [worker1_controller, worker2_controller],
                [step1_controller, step2_controller],
                master,
                [builder1_id, builder2_id])

    @defer.inlineCallbacks
    def test_1worker_wakes_and_suspends_after_single_build_success(self):
        manager_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])
        # test explicitly that worker is substantiated before machine is woken
        self.assertTrue(worker_controller.started)

        manager_controller.wake(True)
        step_controller.finish_step(SUCCESS)
        self.reactor.advance(0)  # force deferred suspend call to be executed
        manager_controller.suspend()

        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)

    @defer.inlineCallbacks
    def test_1worker_wakes_and_suspends_after_single_build_failure(self):
        manager_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])
        self.assertTrue(worker_controller.started)

        manager_controller.wake(True)
        step_controller.finish_step(FAILURE)
        self.reactor.advance(0)  # force deferred suspend call to be executed
        manager_controller.suspend()

        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)

    @defer.inlineCallbacks
    def test_1worker_suspends_machine_after_timeout(self):
        manager_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config(
                build_wait_timeout=5)

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        manager_controller.wake(True)
        self.reactor.advance(10.0)
        step_controller.finish_step(SUCCESS)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_STARTED)

        self.reactor.advance(4.9)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_STARTED)

        # put clock 5s after step finish, machine should start suspending
        self.reactor.advance(0.1)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDING)

        manager_controller.suspend()

        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)

    @defer.inlineCallbacks
    def test_1worker_does_not_suspend_machine_after_timeout_during_build(self):
        manager_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config(
                build_wait_timeout=5)

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        manager_controller.wake(True)
        self.reactor.advance(10.0)
        step_controller.finish_step(SUCCESS)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_STARTED)

        # create build request while machine is still awake. It should not
        # suspend regardless of how much time passes
        self.reactor.advance(4.9)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_STARTED)
        yield self.createBuildrequest(master, [builder_id])

        self.reactor.advance(5.1)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_STARTED)

        step_controller.finish_step(SUCCESS)
        self.reactor.advance(4.9)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_STARTED)

        # put clock 5s after step finish, machine should start suspending
        self.reactor.advance(0.1)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDING)

        manager_controller.suspend()

        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)

    @defer.inlineCallbacks
    def test_1worker_insubstantiated_after_wake_failure(self):
        manager_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_connect_worker = False
        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        manager_controller.wake(False)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)
        self.assertEqual(worker_controller.started, False)

    @defer.inlineCallbacks
    def test_1worker_eats_exception_from_wake(self):
        manager_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_connect_worker = False
        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        class FakeWakeError(Exception):
            pass

        manager_controller.wake(FakeWakeError('wake error'))
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)
        self.assertEqual(worker_controller.started, False)

        self.flushLoggedErrors(FakeWakeError)

    @defer.inlineCallbacks
    def test_1worker_eats_exception_from_suspend(self):
        manager_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        manager_controller.wake(True)
        step_controller.finish_step(SUCCESS)
        self.reactor.advance(0)  # force deferred suspend call to be executed

        class FakeSuspendError(Exception):
            pass

        manager_controller.suspend(FakeSuspendError('wake error'))

        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)
        self.flushLoggedErrors(FakeSuspendError)

    @defer.inlineCallbacks
    def test_2workers_build_substantiates_insubstantiates_both_workers(self):
        manager_controller, worker_controllers, step_controllers, \
            master, builder_ids = yield self.create_two_worker_config()

        for wc in worker_controllers:
            wc.auto_start(True)
            wc.auto_stop(True)

        yield self.createBuildrequest(master, [builder_ids[0]])

        manager_controller.wake(True)
        for wc in worker_controllers:
            self.assertTrue(wc.started)

        step_controllers[0].finish_step(SUCCESS)
        self.reactor.advance(0)  # force deferred suspend call to be executed
        manager_controller.suspend()

        for wc in worker_controllers:
            self.assertFalse(wc.started)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)

    @defer.inlineCallbacks
    def test_2workers_two_builds_wake_machine_concurrently(self):
        manager_controller, worker_controllers, step_controllers, \
            master, builder_ids = yield self.create_two_worker_config()

        for wc in worker_controllers:
            wc.auto_start(True)
            wc.auto_stop(True)

        yield self.createBuildrequest(master, [builder_ids[0]])
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_STARTING)

        yield self.createBuildrequest(master, [builder_ids[1]])

        manager_controller.wake(True)
        for wc in worker_controllers:
            self.assertTrue(wc.started)

        step_controllers[0].finish_step(SUCCESS)
        step_controllers[1].finish_step(SUCCESS)
        self.reactor.advance(0)  # force deferred suspend call to be executed
        manager_controller.suspend()

        for wc in worker_controllers:
            self.assertFalse(wc.started)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)

    @defer.inlineCallbacks
    def test_2workers_insubstantiated_after_one_wake_failure(self):
        manager_controller, worker_controllers, step_controllers, \
            master, builder_ids = yield self.create_two_worker_config()

        for wc in worker_controllers:
            wc.auto_connect_worker = False
            wc.auto_start(True)
            wc.auto_stop(True)

        yield self.createBuildrequest(master, [builder_ids[0]])

        manager_controller.wake(False)
        self.assertEqual(manager_controller.manager.state,
                         SuspendableMachine.STATE_SUSPENDED)

        for wc in worker_controllers:
            self.assertEqual(wc.started, False)
