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


from twisted.internet import defer
from zope.interface import implementer

from buildbot.config import BuilderConfig
from buildbot.interfaces import IBuildStepFactory
from buildbot.machine.base import Machine
from buildbot.process.buildstep import BuildStep
from buildbot.process.factory import BuildFactory
from buildbot.process.results import CANCELLED
from buildbot.test.fake.latent import LatentController
from buildbot.test.util.integration import RunFakeMasterTestCase

try:
    from buildbot_worker.bot import LocalWorker as RemoteWorker
except ImportError:
    RemoteWorker = None


@implementer(IBuildStepFactory)
class StepController:

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.steps = []

    def buildStep(self):
        step_deferred = defer.Deferred()
        step = ControllableStep(step_deferred, **self.kwargs)
        self.steps.append((step, step_deferred))
        return step


class ControllableStep(BuildStep):

    def run(self):
        return self._step_deferred

    def __init__(self, step_deferred, **kwargs):
        super().__init__(**kwargs)
        self._step_deferred = step_deferred

    def interrupt(self, reason):
        self._step_deferred.callback(CANCELLED)


class Tests(RunFakeMasterTestCase):

    @defer.inlineCallbacks
    def test_latent_max_builds(self):
        """
        If max_builds is set, only one build is started on a latent
        worker at a time.
        """
        controller = LatentController(self, 'local', max_builds=1)
        step_controller = StepController()
        config_dict = {
            'builders': [
                BuilderConfig(name="testy-1",
                              workernames=["local"],
                              factory=BuildFactory([step_controller]),
                              ),
                BuilderConfig(name="testy-2",
                              workernames=["local"],
                              factory=BuildFactory([step_controller]),
                              ),
            ],
            'workers': [controller.worker],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_ids = [
            (yield master.data.updates.findBuilderId('testy-1')),
            (yield master.data.updates.findBuilderId('testy-2')),
        ]

        started_builds = []
        yield master.mq.startConsuming(
            lambda key, build: started_builds.append(build),
            ('builds', None, 'new'))

        # Trigger a buildrequest
        bsid, brids = yield master.data.updates.addBuildset(
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

        # The worker fails to substantiate.
        controller.start_instance(True)

        controller.connect_worker()

        self.assertEqual(len(started_builds), 1)
        yield controller.auto_stop(True)

    @defer.inlineCallbacks
    def test_local_worker_max_builds(self):
        """
        If max_builds is set, only one build is started on a worker
        at a time.
        """
        step_controller = StepController()
        config_dict = {
            'builders': [
                BuilderConfig(name="testy-1",
                              workernames=["local"],
                              factory=BuildFactory([step_controller]),
                              ),
                BuilderConfig(name="testy-2",
                              workernames=["local"],
                              factory=BuildFactory([step_controller]),
                              ),
            ],
            'workers': [self.createLocalWorker('local', max_builds=1)],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_ids = [
            (yield master.data.updates.findBuilderId('testy-1')),
            (yield master.data.updates.findBuilderId('testy-2')),
        ]

        started_builds = []
        yield master.mq.startConsuming(
            lambda key, build: started_builds.append(build),
            ('builds', None, 'new'))

        # Trigger a buildrequest
        bsid, brids = yield master.data.updates.addBuildset(
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

        self.assertEqual(len(started_builds), 1)

    @defer.inlineCallbacks
    def test_worker_registered_to_machine(self):
        worker = self.createLocalWorker('worker1', machine_name='machine1')
        machine = Machine('machine1')

        config_dict = {
            'builders': [
                BuilderConfig(name="builder1",
                              workernames=["worker1"],
                              factory=BuildFactory(),
                              ),
            ],
            'workers': [worker],
            'machines': [machine],
            'protocols': {'null': {}},
            'multiMaster': True,
        }

        yield self.getMaster(config_dict)

        self.assertIs(worker.machine, machine)

    @defer.inlineCallbacks
    def test_worker_reconfigure_with_new_builder(self):
        """
        Checks if we can successfully reconfigure if we add new builders to worker.
        """
        config_dict = {
            'builders': [
                BuilderConfig(name="builder1",
                              workernames=['local1'],
                              factory=BuildFactory()),
            ],
            'workers': [self.createLocalWorker('local1', max_builds=1)],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }
        yield self.getMaster(config_dict)

        config_dict['builders'] += [
            BuilderConfig(name="builder2",
                          workernames=['local1'],
                          factory=BuildFactory()),
        ]
        config_dict['workers'] = [self.createLocalWorker('local1', max_builds=2)]

        # reconfig should succeed
        yield self.reconfigMaster(config_dict)

    @defer.inlineCallbacks
    def test_worker_os_release_info_roundtrip(self):
        """
        Checks if we can successfully get information about the platform the worker is running on.
        This is very similar to test_worker_comm.TestWorkerComm.test_worker_info, except that
        we check details such as whether the information is passed in correct encoding.
        """
        worker = self.createLocalWorker('local1')

        config_dict = {
            'builders': [
                BuilderConfig(name="builder1",
                              workernames=['local1'],
                              factory=BuildFactory()),
            ],
            'workers': [worker],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }
        yield self.getMaster(config_dict)

        props = worker.worker_status.info

        from buildbot_worker.base import BotBase

        expected_props_dict = {}
        BotBase._read_os_release(BotBase.os_release_file, expected_props_dict)

        for key, value in expected_props_dict.items():
            self.assertTrue(isinstance(key, str))
            self.assertTrue(isinstance(value, str))
            self.assertEqual(props.getProperty(key), value)

    if RemoteWorker is None:
        skip = "buildbot-worker package is not installed"
