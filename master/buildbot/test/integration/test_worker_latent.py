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
from twisted.python.failure import Failure
from twisted.spread import pb

from buildbot.config import BuilderConfig
from buildbot.config import MasterConfig
from buildbot.interfaces import LatentWorkerCannotSubstantiate
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.interfaces import LatentWorkerSubstantiatiationCancelled
from buildbot.machine.latent import States as MachineStates
from buildbot.process.factory import BuildFactory
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.test.fake.latent import LatentController
from buildbot.test.fake.machine import LatentMachineController
from buildbot.test.fake.step import BuildStepController
from buildbot.test.util.integration import RunFakeMasterTestCase
from buildbot.test.util.misc import TimeoutableTestCase
from buildbot.test.util.patch_delay import patchForDelay
from buildbot.worker.latent import States


class TestException(Exception):

    """
    An exception thrown in tests.
    """


class Latent(TimeoutableTestCase, RunFakeMasterTestCase):

    def tearDown(self):
        # Flush the errors logged by the master stop cancelling the builds.
        self.flushLoggedErrors(LatentWorkerSubstantiatiationCancelled)
        super().tearDown()

    @defer.inlineCallbacks
    def create_single_worker_config(self, controller_kwargs=None):
        if not controller_kwargs:
            controller_kwargs = {}

        controller = LatentController(self, 'local', **controller_kwargs)
        config_dict = {
            'builders': [
                BuilderConfig(name="testy",
                              workernames=["local"],
                              factory=BuildFactory(),
                              ),
            ],
            'workers': [controller.worker],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_id = yield master.data.updates.findBuilderId('testy')

        return controller, master, builder_id

    @defer.inlineCallbacks
    def create_single_worker_config_with_step(self, controller_kwargs=None):
        if not controller_kwargs:
            controller_kwargs = {}

        controller = LatentController(self, 'local', **controller_kwargs)
        stepcontroller = BuildStepController()
        config_dict = {
            'builders': [
                BuilderConfig(name="testy",
                              workernames=["local"],
                              factory=BuildFactory([stepcontroller.step]),
                              ),
            ],
            'workers': [controller.worker],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_id = yield master.data.updates.findBuilderId('testy')

        return controller, stepcontroller, master, builder_id

    @defer.inlineCallbacks
    def create_single_worker_two_builder_config(self, controller_kwargs=None):
        if not controller_kwargs:
            controller_kwargs = {}

        controller = LatentController(self, 'local', **controller_kwargs)
        config_dict = {
            'builders': [
                BuilderConfig(name="testy-1",
                              workernames=["local"],
                              factory=BuildFactory(),
                              ),
                BuilderConfig(name="testy-2",
                              workernames=["local"],
                              factory=BuildFactory(),
                              ),
            ],
            'workers': [controller.worker],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_ids = [
            (yield master.data.updates.findBuilderId('testy-1')),
            (yield master.data.updates.findBuilderId('testy-2')),
        ]

        return controller, master, builder_ids

    def reconfig_workers_remove_all(self, master):
        # returns a deferred that fires when the worker has been successfully removed
        config_dict = {
            'workers': [],
            'multiMaster': True
        }
        config = MasterConfig.loadFromDict(config_dict, '<dict>')
        return master.workers.reconfigServiceWithBuildbotConfig(config)

    @defer.inlineCallbacks
    def test_latent_workers_start_in_parallel(self):
        """
        If there are two latent workers configured, and two build
        requests for them, both workers will start substantiating
        concurrently.
        """
        controllers = [
            LatentController(self, 'local1'),
            LatentController(self, 'local2'),
        ]
        config_dict = {
            'builders': [
                BuilderConfig(name="testy",
                              workernames=["local1", "local2"],
                              factory=BuildFactory()),
            ],
            'workers': [controller.worker for controller in controllers],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_id = yield master.data.updates.findBuilderId('testy')

        # Request two builds.
        for i in range(2):
            yield self.createBuildrequest(master, [builder_id])

        # Check that both workers were requested to start.
        self.assertEqual(controllers[0].starting, True)
        self.assertEqual(controllers[1].starting, True)
        for controller in controllers:
            controller.start_instance(True)
            yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_refused_substantiations_get_requeued(self):
        """
        If a latent worker refuses to substantiate, the build request becomes
        unclaimed.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config()

        # Trigger a buildrequest
        bsid, brids = yield self.createBuildrequest(master, [builder_id])

        unclaimed_build_requests = []
        yield master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed'))

        # Indicate that the worker can't start an instance.
        controller.start_instance(False)

        # When the substantiation fails, the buildrequest becomes unclaimed.
        self.assertEqual(
            set(brids),
            {req['buildrequestid'] for req in unclaimed_build_requests}
        )

        yield self.assertBuildResults(1, RETRY)
        yield controller.auto_stop(True)
        self.flushLoggedErrors(LatentWorkerFailedToSubstantiate)

    @defer.inlineCallbacks
    def test_failed_substantiations_get_requeued(self):
        """
        If a latent worker fails to substantiate, the build request becomes
        unclaimed.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config()

        # Trigger a buildrequest
        bsid, brids = yield self.createBuildrequest(master, [builder_id])

        unclaimed_build_requests = []
        yield master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed'))

        # The worker fails to substantiate.
        controller.start_instance(
            Failure(TestException("substantiation failed")))
        # Flush the errors logged by the failure.
        self.flushLoggedErrors(TestException)

        # When the substantiation fails, the buildrequest becomes unclaimed.
        self.assertEqual(
            set(brids),
            {req['buildrequestid'] for req in unclaimed_build_requests}
        )
        yield self.assertBuildResults(1, RETRY)
        yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_failed_substantiations_get_exception(self):
        """
        If a latent worker fails to substantiate, the result is an exception.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config()

        # Trigger a buildrequest
        yield self.createBuildrequest(master, [builder_id])

        # The worker fails to substantiate.
        controller.start_instance(
            Failure(LatentWorkerCannotSubstantiate("substantiation failed")))
        # Flush the errors logged by the failure.
        self.flushLoggedErrors(LatentWorkerCannotSubstantiate)

        # When the substantiation fails, the result is an exception.
        yield self.assertBuildResults(1, EXCEPTION)
        yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_worker_accepts_builds_after_failure(self):
        """
        If a latent worker fails to substantiate, the worker is still able to
        accept jobs.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config()

        yield controller.auto_stop(True)
        # Trigger a buildrequest
        bsid, brids = yield self.createBuildrequest(master, [builder_id])

        unclaimed_build_requests = []
        yield master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed'))
        # The worker fails to substantiate.
        controller.start_instance(
            Failure(TestException("substantiation failed")))
        # Flush the errors logged by the failure.
        self.flushLoggedErrors(TestException)

        # The retry logic should only trigger after a exponential backoff
        self.assertEqual(controller.starting, False)

        # advance the time to the point where we should retry
        master.reactor.advance(controller.worker.quarantine_initial_timeout)

        # If the worker started again after the failure, then the retry logic will have
        # already kicked in to start a new build on this (the only) worker. We check that
        # a new instance was requested, which indicates that the worker
        # accepted the build.
        self.assertEqual(controller.starting, True)

        # The worker fails to substantiate(again).
        controller.start_instance(
            Failure(TestException("substantiation failed")))
        # Flush the errors logged by the failure.
        self.flushLoggedErrors(TestException)

        yield self.assertBuildResults(1, RETRY)

        # advance the time to the point where we should not retry
        master.reactor.advance(controller.worker.quarantine_initial_timeout)
        self.assertEqual(controller.starting, False)
        # advance the time to the point where we should retry
        master.reactor.advance(controller.worker.quarantine_initial_timeout)
        self.assertEqual(controller.starting, True)

        controller.auto_start(True)
        controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_worker_multiple_substantiations_succeed(self):
        """
        If multiple builders trigger try to substantiate a worker at
        the same time, if the substantiation succeeds then all of
        the builds proceed.
        """
        controller, master, builder_ids = \
            yield self.create_single_worker_two_builder_config()

        # Trigger a buildrequest
        bsid, brids = yield self.createBuildrequest(master, builder_ids)

        # The worker succeeds to substantiate.
        controller.start_instance(True)

        yield self.assertBuildResults(1, SUCCESS)
        yield self.assertBuildResults(2, SUCCESS)

        yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_very_late_detached_after_substantiation(self):
        '''
        A latent worker may detach at any time after stop_instance() call.
        Make sure it works at the most late detachment point, i.e. when we're
        substantiating again.
        '''
        controller, master, builder_id = \
            yield self.create_single_worker_config(
                controller_kwargs=dict(build_wait_timeout=1))

        yield self.createBuildrequest(master, [builder_id])

        self.assertTrue(controller.starting)

        controller.auto_disconnect_worker = False
        yield controller.start_instance(True)
        yield self.assertBuildResults(1, SUCCESS)

        self.reactor.advance(1)

        # stop the instance, but don't disconnect the worker up to until just
        # before we complete start_instance()
        self.assertTrue(controller.stopping)
        yield controller.stop_instance(True)

        self.assertTrue(controller.stopped)
        yield self.createBuildrequest(master, [builder_id])
        self.assertTrue(controller.starting)
        yield controller.disconnect_worker()
        yield controller.start_instance(True)

        yield self.assertBuildResults(2, SUCCESS)
        self.reactor.advance(1)

        yield controller.stop_instance(True)
        yield controller.disconnect_worker()

    @defer.inlineCallbacks
    def test_substantiation_during_stop_instance(self):
        '''
        If a latent worker detaches before stop_instance() completes and we
        start a build then it should start successfully without causing an
        erroneous cancellation of the substantiation request.
        '''
        controller, master, builder_id = \
            yield self.create_single_worker_config(
                controller_kwargs=dict(build_wait_timeout=1))

        # Trigger a single buildrequest
        yield self.createBuildrequest(master, [builder_id])

        self.assertEqual(True, controller.starting)

        # start instance
        controller.auto_disconnect_worker = False
        controller.start_instance(True)
        yield self.assertBuildResults(1, SUCCESS)

        self.reactor.advance(1)

        self.assertTrue(controller.stopping)
        yield controller.disconnect_worker()
        # now create a buildrequest that will substantiate the build. It should
        # either not start at all until the instance finished substantiating,
        # or the substantiation request needs to be recorded and start
        # immediately after stop_instance completes.
        yield self.createBuildrequest(master, [builder_id])
        yield controller.stop_instance(True)

        yield controller.start_instance(True)
        yield self.assertBuildResults(2, SUCCESS)

        self.reactor.advance(1)
        yield controller.stop_instance(True)
        yield controller.disconnect_worker()

    @defer.inlineCallbacks
    def test_substantiation_during_stop_instance_canStartBuild_race(self):
        '''
        If build attempts substantiation after the latent worker detaches,
        but stop_instance() is not completed yet, then we should successfully
        complete substantiation without causing an erroneous cancellation.
        The above sequence of events was possible even if canStartBuild
        checked for a in-progress insubstantiation, as if the build is scheduled
        before insubstantiation, its start could be delayed until when
        stop_instance() is in progress.
        '''
        controller, master, builder_ids = \
            yield self.create_single_worker_two_builder_config(
                controller_kwargs=dict(build_wait_timeout=1))

        # Trigger a single buildrequest
        yield self.createBuildrequest(master, [builder_ids[0]])

        self.assertEqual(True, controller.starting)

        # start instance
        controller.start_instance(True)
        yield self.assertBuildResults(1, SUCCESS)

        with patchForDelay('buildbot.process.builder.Builder.maybeStartBuild') as delay:
            # create a build request which will result in a build, but it won't
            # attempt to substantiate until after stop_instance() is in progress
            yield self.createBuildrequest(master, [builder_ids[1]])
            self.assertEqual(len(delay), 1)
            self.reactor.advance(1)

            self.assertTrue(controller.stopping)
            delay.fire()
            yield controller.stop_instance(True)

        self.assertTrue(controller.starting)
        yield controller.start_instance(True)
        yield self.assertBuildResults(2, SUCCESS)

        self.reactor.advance(1)
        yield controller.stop_instance(True)

    @defer.inlineCallbacks
    def test_insubstantiation_during_substantiation_refuses_substantiation(self):
        """
        If a latent worker gets insubstantiation() during substantiation, then it should refuse
        to substantiate.
        """
        controller, master, builder_id = yield self.create_single_worker_config(
            controller_kwargs=dict(build_wait_timeout=1))

        # insubstantiate during start_instance(). Note that failed substantiation is notified only
        # after the latent workers completes start-stop cycle.
        yield self.createBuildrequest(master, [builder_id])
        d = controller.worker.insubstantiate()
        controller.start_instance(False)
        controller.stop_instance(True)
        yield d

        yield self.assertBuildResults(1, RETRY)

    @defer.inlineCallbacks
    def test_stopservice_during_insubstantiation_completes(self):
        """
        When stopService is called and a worker is insubstantiating, we should wait for this
        process to complete.
        """
        controller, master, builder_id = yield self.create_single_worker_config(
            controller_kwargs=dict(build_wait_timeout=1))

        # Substantiate worker via a build
        yield self.createBuildrequest(master, [builder_id])
        yield controller.start_instance(True)

        yield self.assertBuildResults(1, SUCCESS)
        self.assertTrue(controller.started)

        # Wait until worker starts insubstantiation and then shutdown worker
        self.reactor.advance(1)
        self.assertTrue(controller.stopping)

        d = self.reconfig_workers_remove_all(master)
        self.assertFalse(d.called)
        yield controller.stop_instance(True)
        yield d

    @parameterized.expand([
        ('with_substantiation_failure', False, False),
        ('without_worker_connecting', True, False),
        ('with_worker_connecting', True, True),
    ])
    @defer.inlineCallbacks
    def test_stopservice_during_substantiation_completes(self, name, subst_success,
                                                         worker_connects):
        """
        When stopService is called and a worker is substantiating, we should wait for this
        process to complete.
        """
        controller, master, builder_id = yield self.create_single_worker_config(
            controller_kwargs=dict(build_wait_timeout=1))
        controller.auto_connect_worker = worker_connects

        # Substantiate worker via a build
        yield self.createBuildrequest(master, [builder_id])
        self.assertTrue(controller.starting)

        d = self.reconfig_workers_remove_all(master)
        self.assertFalse(d.called)

        yield controller.start_instance(subst_success)

        # we should stop the instance immediately after it substantiates regardless of the result
        self.assertTrue(controller.stopping)

        yield controller.stop_instance(True)
        yield d

    @defer.inlineCallbacks
    def test_substantiation_cancelled_by_insubstantiation_when_waiting_for_insubstantiation(self):
        """
        We should cancel substantiation if we insubstantiate when that substantiation is waiting
        on current insubstantiation to finish
        """
        controller, master, builder_id = yield self.create_single_worker_config(
            controller_kwargs=dict(build_wait_timeout=1))

        yield self.createBuildrequest(master, [builder_id])

        # put the worker into insubstantiation phase
        controller.start_instance(True)
        yield self.assertBuildResults(1, SUCCESS)

        self.reactor.advance(1)
        self.assertTrue(controller.stopping)

        # build should wait on the insubstantiation
        yield self.createBuildrequest(master, [builder_id])
        self.assertEqual(controller.worker.state, States.INSUBSTANTIATING_SUBSTANTIATING)

        # build should be requeued if we insubstantiate.
        d = controller.worker.insubstantiate()
        controller.stop_instance(True)
        yield d

        yield self.assertBuildResults(2, RETRY)

    @defer.inlineCallbacks
    def test_stalled_substantiation_then_timeout_get_requeued(self):
        """
        If a latent worker substantiate, but not connect, and then be
        unsubstantiated, the build request becomes unclaimed.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config()

        # Trigger a buildrequest
        bsid, brids = yield self.createBuildrequest(master, [builder_id])

        unclaimed_build_requests = []
        yield master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed'))

        # We never start the worker, rather timeout it.
        master.reactor.advance(controller.worker.missing_timeout)
        # Flush the errors logged by the failure.
        self.flushLoggedErrors(defer.TimeoutError)

        # When the substantiation fails, the buildrequest becomes unclaimed.
        self.assertEqual(
            set(brids),
            {req['buildrequestid'] for req in unclaimed_build_requests}
        )
        yield controller.start_instance(False)
        yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_sever_connection_before_ping_then_timeout_get_requeued(self):
        """
        If a latent worker connects, but its connection is severed without
        notification in the TCP layer, we successfully wait until TCP times
        out and requeue the build.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config(
                controller_kwargs=dict(build_wait_timeout=1))

        bsid, brids = yield self.createBuildrequest(master, [builder_id])

        # sever connection just before ping()
        with patchForDelay('buildbot.process.workerforbuilder.AbstractWorkerForBuilder.ping') as delay:
            yield controller.start_instance(True)
            controller.sever_connection()
            delay.fire()

        # lose connection after TCP times out
        self.reactor.advance(100)
        yield controller.disconnect_worker()
        yield self.assertBuildResults(1, RETRY)

        # the worker will be put into quarantine
        self.reactor.advance(controller.worker.quarantine_initial_timeout)

        yield controller.stop_instance(True)
        yield controller.start_instance(True)
        yield self.assertBuildResults(2, SUCCESS)

        self.reactor.advance(1)
        yield controller.stop_instance(True)

        self.flushLoggedErrors(pb.PBConnectionLost)

    @defer.inlineCallbacks
    def test_failed_sendBuilderList_get_requeued(self):
        """
        sendBuilderList can fail due to missing permissions on the workdir,
        the build request becomes unclaimed
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config()

        # Trigger a buildrequest
        bsid, brids = yield self.createBuildrequest(master, [builder_id])

        unclaimed_build_requests = []
        yield master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed'))
        logs = []
        yield master.mq.startConsuming(
            lambda key, log: logs.append(log),
            ('logs', None, 'new'))

        # The worker succeed to substantiate
        def remote_setBuilderList(self, dirs):
            raise TestException("can't create dir")
        controller.patchBot(self, 'remote_setBuilderList',
                            remote_setBuilderList)
        controller.start_instance(True)

        # Flush the errors logged by the failure.
        self.flushLoggedErrors(TestException)

        # When the substantiation fails, the buildrequest becomes unclaimed.
        self.assertEqual(
            set(brids),
            {req['buildrequestid'] for req in unclaimed_build_requests}
        )
        # should get 2 logs (html and txt) with proper information in there
        self.assertEqual(len(logs), 2)
        logs_by_name = {}
        for _log in logs:
            fulllog = yield master.data.get(("logs", str(_log['logid']),
                                            "raw"))
            logs_by_name[fulllog['filename']] = fulllog['raw']

        for i in ["err_text", "err_html"]:
            self.assertIn("can't create dir", logs_by_name[i])
            # make sure stacktrace is present in html
            self.assertIn("buildbot.test.integration.test_worker_latent.TestException",
                logs_by_name[i])
        yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_failed_ping_get_requeued(self):
        """
        sendBuilderList can fail due to missing permissions on the workdir,
        the build request becomes unclaimed
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config()

        # Trigger a buildrequest
        bsid, brids = yield self.createBuildrequest(master, [builder_id])

        unclaimed_build_requests = []
        yield master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed'))
        logs = []
        yield master.mq.startConsuming(
            lambda key, log: logs.append(log),
            ('logs', None, 'new'))

        # The worker succeed to substantiate
        def remote_print(self, msg):
            if msg == "ping":
                raise TestException("can't ping")
        controller.patchBot(self, 'remote_print', remote_print)
        controller.start_instance(True)

        # Flush the errors logged by the failure.
        self.flushLoggedErrors(TestException)

        # When the substantiation fails, the buildrequest becomes unclaimed.
        self.assertEqual(
            set(brids),
            {req['buildrequestid'] for req in unclaimed_build_requests}
        )
        # should get 2 logs (html and txt) with proper information in there
        self.assertEqual(len(logs), 2)
        logs_by_name = {}
        for _log in logs:
            fulllog = yield master.data.get(("logs", str(_log['logid']),
                                            "raw"))
            logs_by_name[fulllog['filename']] = fulllog['raw']

        for i in ["err_text", "err_html"]:
            self.assertIn("can't ping", logs_by_name[i])
            # make sure stacktrace is present in html
            self.assertIn("buildbot.test.integration.test_worker_latent.TestException",
                logs_by_name[i])
        yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_worker_close_connection_while_building(self):
        """
        If the worker close connection in the middle of the build, the next
        build can start correctly
        """
        controller, stepcontroller, master, builder_id = \
            yield self.create_single_worker_config_with_step(
                controller_kwargs=dict(build_wait_timeout=0)
            )

        # Request a build and disconnect midway
        controller.auto_disconnect_worker = False
        yield self.createBuildrequest(master, [builder_id])
        yield controller.auto_stop(True)

        self.assertTrue(controller.starting)
        controller.start_instance(True)

        yield self.assertBuildResults(1, None)
        yield controller.disconnect_worker()
        yield self.assertBuildResults(1, RETRY)

        # Now check that the build requeued and finished with success
        controller.start_instance(True)

        yield self.assertBuildResults(2, None)
        stepcontroller.finish_step(SUCCESS)
        yield self.assertBuildResults(2, SUCCESS)
        yield controller.disconnect_worker()

    @defer.inlineCallbacks
    def test_negative_build_timeout_reattach_substantiated(self):
        """
        When build_wait_timeout is negative, we don't disconnect the worker from
        our side. We should still support accidental disconnections from
        worker side due to, e.g. network problems.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config(
                controller_kwargs=dict(build_wait_timeout=-1)
            )

        controller.auto_disconnect_worker = False
        controller.auto_connect_worker = False

        # Substantiate worker via a build
        yield self.createBuildrequest(master, [builder_id])
        yield controller.start_instance(True)
        yield controller.connect_worker()

        yield self.assertBuildResults(1, SUCCESS)
        self.assertTrue(controller.started)

        # Now disconnect and reconnect worker and check whether we can still
        # build. This should not change the worker state from our side.
        yield controller.disconnect_worker()
        self.assertTrue(controller.started)
        yield controller.connect_worker()
        self.assertTrue(controller.started)

        yield self.createBuildrequest(master, [builder_id])
        yield self.assertBuildResults(1, SUCCESS)

        # The only way to stop worker with negative build timeout is to
        # insubstantiate explicitly
        yield controller.auto_stop(True)
        yield controller.worker.insubstantiate()
        yield controller.disconnect_worker()

    @defer.inlineCallbacks
    def test_sever_connection_while_building(self):
        """
        If the connection to worker is severed without TCP notification in the
        middle of the build, the build is re-queued and successfully restarted.
        """
        controller, stepcontroller, master, builder_id = \
            yield self.create_single_worker_config_with_step(
                controller_kwargs=dict(build_wait_timeout=0)
            )

        # Request a build and disconnect midway
        yield self.createBuildrequest(master, [builder_id])
        yield controller.auto_stop(True)

        self.assertTrue(controller.starting)
        controller.start_instance(True)

        yield self.assertBuildResults(1, None)
        # sever connection and lose it after TCP times out
        controller.sever_connection()
        self.reactor.advance(100)
        yield controller.disconnect_worker()

        yield self.assertBuildResults(1, RETRY)

        # Request one build.
        yield self.createBuildrequest(master, [builder_id])
        controller.start_instance(True)
        yield self.assertBuildResults(2, None)
        stepcontroller.finish_step(SUCCESS)
        yield self.assertBuildResults(2, SUCCESS)

    @defer.inlineCallbacks
    def test_sever_connection_during_insubstantiation(self):
        """
        If latent worker connection is severed without notification in the TCP
        layer, we successfully wait until TCP times out, insubstantiate and
        can substantiate after that.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config(
                controller_kwargs=dict(build_wait_timeout=1))

        yield self.createBuildrequest(master, [builder_id])

        controller.start_instance(True)
        yield self.assertBuildResults(1, SUCCESS)

        # sever connection just before insubstantiation and lose it after TCP
        # times out
        with patchForDelay('buildbot.worker.base.AbstractWorker.disconnect') as delay:
            self.reactor.advance(1)
            self.assertTrue(controller.stopping)
            controller.sever_connection()
            delay.fire()

        yield controller.stop_instance(True)
        self.reactor.advance(100)
        yield controller.disconnect_worker()

        # create new build request and verify it works
        yield self.createBuildrequest(master, [builder_id])

        yield controller.start_instance(True)
        yield self.assertBuildResults(1, SUCCESS)
        self.reactor.advance(1)
        yield controller.stop_instance(True)

        self.flushLoggedErrors(pb.PBConnectionLost)

    @defer.inlineCallbacks
    def test_sever_connection_during_insubstantiation_and_buildrequest(self):
        """
        If latent worker connection is severed without notification in the TCP
        layer, we successfully wait until TCP times out, insubstantiate and
        can substantiate after that. In this the subsequent build request is
        created during insubstantiation
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config(
                controller_kwargs=dict(build_wait_timeout=1))

        yield self.createBuildrequest(master, [builder_id])

        controller.start_instance(True)
        yield self.assertBuildResults(1, SUCCESS)

        # sever connection just before insubstantiation and lose it after TCP
        # times out
        with patchForDelay('buildbot.worker.base.AbstractWorker.disconnect') as delay:
            self.reactor.advance(1)
            self.assertTrue(controller.stopping)
            yield self.createBuildrequest(master, [builder_id])
            controller.sever_connection()
            delay.fire()

        yield controller.stop_instance(True)
        self.reactor.advance(100)
        yield controller.disconnect_worker()

        # verify the previously created build successfully completes
        yield controller.start_instance(True)
        yield self.assertBuildResults(1, SUCCESS)
        self.reactor.advance(1)
        yield controller.stop_instance(True)

        self.flushLoggedErrors(pb.PBConnectionLost)

    @defer.inlineCallbacks
    def test_negative_build_timeout_reattach_insubstantiating(self):
        """
        When build_wait_timeout is negative, we don't disconnect the worker from
        our side, but it can disconnect and reattach from worker side due to,
        e.g. network problems.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config(
                controller_kwargs=dict(build_wait_timeout=-1)
            )

        controller.auto_disconnect_worker = False
        controller.auto_connect_worker = False

        # Substantiate worker via a build
        yield self.createBuildrequest(master, [builder_id])
        yield controller.start_instance(True)
        yield controller.connect_worker()

        yield self.assertBuildResults(1, SUCCESS)
        self.assertTrue(controller.started)

        # Now start insubstantiation and disconnect and reconnect the worker.
        # It should not change worker state from master side.
        d = controller.worker.insubstantiate()
        self.assertTrue(controller.stopping)
        yield controller.disconnect_worker()
        self.assertTrue(controller.stopping)
        yield controller.connect_worker()
        self.assertTrue(controller.stopping)
        yield controller.stop_instance(True)
        yield d

        self.assertTrue(controller.stopped)
        yield controller.disconnect_worker()

        # Now substantiate the worker and verify build succeeds
        yield self.createBuildrequest(master, [builder_id])
        yield controller.start_instance(True)
        yield controller.connect_worker()
        yield self.assertBuildResults(1, SUCCESS)

        controller.auto_disconnect_worker = True
        yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_negative_build_timeout_no_disconnect_insubstantiating(self):
        """
        When build_wait_timeout is negative, we don't disconnect the worker from
        our side, so it should be possible to insubstantiate and substantiate
        it without problems if the worker does not disconnect either.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config(
                controller_kwargs=dict(build_wait_timeout=-1)
            )

        controller.auto_disconnect_worker = False
        controller.auto_connect_worker = False

        # Substantiate worker via a build
        yield self.createBuildrequest(master, [builder_id])
        yield controller.start_instance(True)
        yield controller.connect_worker()

        yield self.assertBuildResults(1, SUCCESS)
        self.assertTrue(controller.started)

        # Insubstantiate worker without disconnecting it
        d = controller.worker.insubstantiate()
        self.assertTrue(controller.stopping)
        yield controller.stop_instance(True)
        yield d

        self.assertTrue(controller.stopped)

        # Now substantiate the worker without connecting it
        yield self.createBuildrequest(master, [builder_id])
        yield controller.start_instance(True)
        yield self.assertBuildResults(1, SUCCESS)

        controller.auto_disconnect_worker = True
        yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_negative_build_timeout_insubstantiates_on_master_shutdown(self):
        """
        When build_wait_timeout is negative, we should still insubstantiate when master shuts down.
        """
        controller, master, builder_id = yield self.create_single_worker_config(
            controller_kwargs=dict(build_wait_timeout=-1))

        # Substantiate worker via a build
        yield self.createBuildrequest(master, [builder_id])
        yield controller.start_instance(True)

        yield self.assertBuildResults(1, SUCCESS)
        self.assertTrue(controller.started)

        # Shutdown master
        d = master.stopService()
        yield controller.stop_instance(True)
        yield d

    @defer.inlineCallbacks
    def test_stop_instance_synchronous_exception(self):
        """
        Throwing a synchronous exception from stop_instance should allow subsequent build to start.
        """
        controller, master, builder_id = yield self.create_single_worker_config(
            controller_kwargs=dict(build_wait_timeout=1))

        controller.auto_stop(True)

        # patch stop_instance() to raise exception synchronously
        def raise_stop_instance(fast):
            raise TestException()

        real_stop_instance = controller.worker.stop_instance
        controller.worker.stop_instance = raise_stop_instance

        # create a build and wait for stop
        yield self.createBuildrequest(master, [builder_id])
        yield controller.start_instance(True)
        self.reactor.advance(1)
        yield self.assertBuildResults(1, SUCCESS)
        self.flushLoggedErrors(TestException)

        # unpatch stop_instance() and call it to cleanup state of fake worker controller
        controller.worker.stop_instance = real_stop_instance
        yield controller.worker.stop_instance(False)

        self.reactor.advance(1)

        # subsequent build should succeed
        yield self.createBuildrequest(master, [builder_id])
        yield controller.start_instance(True)
        self.reactor.advance(1)
        yield self.assertBuildResults(2, SUCCESS)

    @defer.inlineCallbacks
    def test_build_stop_with_cancelled_during_substantiation(self):
        """
        If a build is stopping during latent worker substantiating, the build
        becomes cancelled
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config()

        builder = master.botmaster.builders['testy']

        # Trigger a buildrequest
        yield self.createBuildrequest(master, [builder_id])

        # Stop the build
        build = builder.getBuild(0)
        build.stopBuild('no reason', results=CANCELLED)

        # Indicate that the worker can't start an instance.
        controller.start_instance(False)

        yield self.assertBuildResults(1, CANCELLED)

        yield controller.auto_stop(True)
        self.flushLoggedErrors(LatentWorkerFailedToSubstantiate)

    @defer.inlineCallbacks
    def test_build_stop_with_retry_during_substantiation(self):
        """
        If master is shutting down during latent worker substantiating, the build becomes retry.
        """
        controller, master, builder_id = \
            yield self.create_single_worker_config()

        builder = master.botmaster.builders['testy']

        # Trigger a buildrequest
        _, brids = yield self.createBuildrequest(master, [builder_id])

        unclaimed_build_requests = []
        yield master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed'))

        # Stop the build
        build = builder.getBuild(0)
        build.stopBuild('no reason', results=RETRY)

        # Indicate that the worker can't start an instance.
        controller.start_instance(False)

        yield self.assertBuildResults(1, RETRY)
        self.assertEqual(
            set(brids),
            {req['buildrequestid'] for req in unclaimed_build_requests}
        )
        yield controller.auto_stop(True)
        self.flushLoggedErrors(LatentWorkerFailedToSubstantiate)

    @defer.inlineCallbacks
    def test_rejects_build_on_instance_with_different_type_timeout_zero(self):
        """
        If latent worker supports getting its instance type from properties that
        are rendered from build then the buildrequestdistributor must not
        schedule any builds on workers that are running different instance type
        than what these builds will require.
        """
        controller, stepcontroller, master, builder_id = \
            yield self.create_single_worker_config_with_step(
                controller_kwargs=dict(
                    kind=Interpolate('%(prop:worker_kind)s'),
                    build_wait_timeout=0
                )
            )

        # create build request
        yield self.createBuildrequest(master, [builder_id],
                                      properties=Properties(worker_kind='a'))

        # start the build and verify the kind of the worker. Note that the
        # buildmaster needs to restart the worker in order to change the worker
        # kind, so we allow it both to auto start and stop
        self.assertEqual(True, controller.starting)

        controller.auto_start(True)
        yield controller.auto_stop(True)
        self.assertEqual((yield controller.get_started_kind()),
                         'a')

        # before the other build finished, create another build request
        yield self.createBuildrequest(master, [builder_id],
                                      properties=Properties(worker_kind='b'))
        stepcontroller.finish_step(SUCCESS)

        # give the botmaster chance to insubstantiate the worker and
        # maybe substantiate it for the pending build the builds on worker
        self.reactor.advance(0.1)

        # verify that the second build restarted with the expected instance
        # kind
        self.assertEqual((yield controller.get_started_kind()),
                         'b')
        stepcontroller.finish_step(SUCCESS)

        yield self.assertBuildResults(1, SUCCESS)
        yield self.assertBuildResults(2, SUCCESS)

    @defer.inlineCallbacks
    def test_rejects_build_on_instance_with_different_type_timeout_nonzero(self):
        """
        If latent worker supports getting its instance type from properties that
        are rendered from build then the buildrequestdistributor must not
        schedule any builds on workers that are running different instance type
        than what these builds will require.
        """

        controller, stepcontroller, master, builder_id = \
            yield self.create_single_worker_config_with_step(
                controller_kwargs=dict(
                    kind=Interpolate('%(prop:worker_kind)s'),
                    build_wait_timeout=5
                )
            )

        # create build request
        yield self.createBuildrequest(master, [builder_id],
                                      properties=Properties(worker_kind='a'))

        # start the build and verify the kind of the worker. Note that the
        # buildmaster needs to restart the worker in order to change the worker
        # kind, so we allow it both to auto start and stop
        self.assertEqual(True, controller.starting)

        controller.auto_start(True)
        yield controller.auto_stop(True)
        self.assertEqual((yield controller.get_started_kind()),
                         'a')

        # before the other build finished, create another build request
        yield self.createBuildrequest(master, [builder_id],
                                      properties=Properties(worker_kind='b'))
        stepcontroller.finish_step(SUCCESS)

        # give the botmaster chance to insubstantiate the worker and
        # maybe substantiate it for the pending build the builds on worker
        self.reactor.advance(0.1)

        # verify build has not started, even though the worker is waiting
        # for one
        self.assertIsNone((yield master.db.builds.getBuild(2)))
        self.assertTrue(controller.started)

        # wait until the latent worker times out, is insubstantiated,
        # is substantiated because of pending buildrequest and starts the build
        self.reactor.advance(6)
        self.assertIsNotNone((yield master.db.builds.getBuild(2)))

        # verify that the second build restarted with the expected instance
        # kind
        self.assertEqual((yield controller.get_started_kind()),
                         'b')
        stepcontroller.finish_step(SUCCESS)

        yield self.assertBuildResults(1, SUCCESS)
        yield self.assertBuildResults(2, SUCCESS)

    @defer.inlineCallbacks
    def test_supports_no_build_for_substantiation(self):
        """
        Abstract latent worker should support being substantiated without a
        build and then insubstantiated.
        """
        controller, _, _ = \
            yield self.create_single_worker_config()

        controller.worker.substantiate(None, None)
        controller.start_instance(True)
        self.assertTrue(controller.started)

        d = controller.worker.insubstantiate()
        controller.stop_instance(True)
        yield d

    @defer.inlineCallbacks
    def test_supports_no_build_for_substantiation_accepts_build_later(self):
        """
        Abstract latent worker should support being substantiated without a
        build and then accept a build request.
        """
        controller, stepcontroller, master, builder_id = \
            yield self.create_single_worker_config_with_step(
                controller_kwargs=dict(build_wait_timeout=1))

        controller.worker.substantiate(None, None)
        controller.start_instance(True)
        self.assertTrue(controller.started)

        self.createBuildrequest(master, [builder_id])
        stepcontroller.finish_step(SUCCESS)

        self.reactor.advance(1)
        controller.stop_instance(True)


class LatentWithLatentMachine(TimeoutableTestCase, RunFakeMasterTestCase):

    def tearDown(self):
        # Flush the errors logged by the master stop cancelling the builds.
        self.flushLoggedErrors(LatentWorkerSubstantiatiationCancelled)
        super().tearDown()

    @defer.inlineCallbacks
    def create_single_worker_config(self, build_wait_timeout=0):
        machine_controller = LatentMachineController(
            name='machine1',
            build_wait_timeout=build_wait_timeout)

        worker_controller = LatentController(self, 'worker1',
                                             machine_name='machine1')
        step_controller = BuildStepController()

        config_dict = {
            'machines': [machine_controller.machine],
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

        return (machine_controller, worker_controller, step_controller,
                master, builder_id)

    @defer.inlineCallbacks
    def create_two_worker_config(self, build_wait_timeout=0,
                                 controller_kwargs=None):
        if not controller_kwargs:
            controller_kwargs = {}

        machine_controller = LatentMachineController(
            name='machine1',
            build_wait_timeout=build_wait_timeout)

        worker1_controller = LatentController(self, 'worker1',
                                              machine_name='machine1',
                                              **controller_kwargs)
        worker2_controller = LatentController(self, 'worker2',
                                              machine_name='machine1',
                                              **controller_kwargs)
        step1_controller = BuildStepController()
        step2_controller = BuildStepController()

        config_dict = {
            'machines': [machine_controller.machine],
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

        return (machine_controller,
                [worker1_controller, worker2_controller],
                [step1_controller, step2_controller],
                master,
                [builder1_id, builder2_id])

    @defer.inlineCallbacks
    def test_1worker_starts_and_stops_after_single_build_success(self):
        machine_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])
        machine_controller.start_machine(True)
        self.assertTrue(worker_controller.started)

        step_controller.finish_step(SUCCESS)
        self.reactor.advance(0)  # force deferred suspend call to be executed
        machine_controller.stop_machine()

        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)

    @defer.inlineCallbacks
    def test_1worker_starts_and_stops_after_single_build_failure(self):
        machine_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])
        machine_controller.start_machine(True)
        self.assertTrue(worker_controller.started)

        step_controller.finish_step(FAILURE)
        self.reactor.advance(0)  # force deferred stop call to be executed
        machine_controller.stop_machine()

        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)

    @defer.inlineCallbacks
    def test_1worker_stops_machine_after_timeout(self):
        machine_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config(
                build_wait_timeout=5)

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        machine_controller.start_machine(True)
        self.reactor.advance(10.0)
        step_controller.finish_step(SUCCESS)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STARTED)

        self.reactor.advance(4.9)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STARTED)

        # put clock 5s after step finish, machine should start suspending
        self.reactor.advance(0.1)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPING)

        machine_controller.stop_machine()

        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)

    @defer.inlineCallbacks
    def test_1worker_does_not_stop_machine_machine_after_timeout_during_build(self):
        machine_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config(
                build_wait_timeout=5)

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        machine_controller.start_machine(True)
        self.reactor.advance(10.0)
        step_controller.finish_step(SUCCESS)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STARTED)

        # create build request while machine is still awake. It should not
        # suspend regardless of how much time passes
        self.reactor.advance(4.9)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STARTED)
        yield self.createBuildrequest(master, [builder_id])

        self.reactor.advance(5.1)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STARTED)

        step_controller.finish_step(SUCCESS)
        self.reactor.advance(4.9)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STARTED)

        # put clock 5s after step finish, machine should start suspending
        self.reactor.advance(0.1)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPING)

        machine_controller.stop_machine()

        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)

    @defer.inlineCallbacks
    def test_1worker_insubstantiated_after_start_failure(self):
        machine_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_connect_worker = False
        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        machine_controller.start_machine(False)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)
        self.assertEqual(worker_controller.started, False)

    @defer.inlineCallbacks
    def test_1worker_eats_exception_from_start_machine(self):
        machine_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_connect_worker = False
        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        class FakeError(Exception):
            pass

        machine_controller.start_machine(FakeError('start error'))
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)
        self.assertEqual(worker_controller.started, False)

        self.flushLoggedErrors(FakeError)

    @defer.inlineCallbacks
    def test_1worker_eats_exception_from_stop_machine(self):
        machine_controller, worker_controller, step_controller, \
            master, builder_id = yield self.create_single_worker_config()

        worker_controller.auto_start(True)
        worker_controller.auto_stop(True)

        yield self.createBuildrequest(master, [builder_id])

        machine_controller.start_machine(True)
        step_controller.finish_step(SUCCESS)
        self.reactor.advance(0)  # force deferred suspend call to be executed

        class FakeError(Exception):
            pass

        machine_controller.stop_machine(FakeError('stop error'))

        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)
        self.flushLoggedErrors(FakeError)

    @defer.inlineCallbacks
    def test_2workers_build_substantiates_insubstantiates_both_workers(self):
        machine_controller, worker_controllers, step_controllers, \
            master, builder_ids = yield self.create_two_worker_config(
                controller_kwargs=dict(starts_without_substantiate=True))

        for wc in worker_controllers:
            wc.auto_start(True)
            wc.auto_stop(True)

        yield self.createBuildrequest(master, [builder_ids[0]])

        machine_controller.start_machine(True)
        for wc in worker_controllers:
            self.assertTrue(wc.started)

        step_controllers[0].finish_step(SUCCESS)
        self.reactor.advance(0)  # force deferred suspend call to be executed
        machine_controller.stop_machine()

        for wc in worker_controllers:
            self.assertFalse(wc.started)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)

    @defer.inlineCallbacks
    def test_2workers_two_builds_start_machine_concurrently(self):
        machine_controller, worker_controllers, step_controllers, \
            master, builder_ids = yield self.create_two_worker_config()

        for wc in worker_controllers:
            wc.auto_start(True)
            wc.auto_stop(True)

        yield self.createBuildrequest(master, [builder_ids[0]])
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STARTING)

        yield self.createBuildrequest(master, [builder_ids[1]])

        machine_controller.start_machine(True)
        for wc in worker_controllers:
            self.assertTrue(wc.started)

        step_controllers[0].finish_step(SUCCESS)
        step_controllers[1].finish_step(SUCCESS)
        self.reactor.advance(0)  # force deferred suspend call to be executed
        machine_controller.stop_machine()

        for wc in worker_controllers:
            self.assertFalse(wc.started)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)

    @defer.inlineCallbacks
    def test_2workers_insubstantiated_after_one_start_failure(self):
        machine_controller, worker_controllers, step_controllers, \
            master, builder_ids = yield self.create_two_worker_config()

        for wc in worker_controllers:
            wc.auto_connect_worker = False
            wc.auto_start(True)
            wc.auto_stop(True)

        yield self.createBuildrequest(master, [builder_ids[0]])

        machine_controller.start_machine(False)
        self.assertEqual(machine_controller.machine.state,
                         MachineStates.STOPPED)

        for wc in worker_controllers:
            self.assertEqual(wc.started, False)
