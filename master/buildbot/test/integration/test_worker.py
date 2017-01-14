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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet.defer import Deferred
from twisted.python import threadpool
from twisted.trial.unittest import SynchronousTestCase
from zope.interface import implementer

from buildbot.config import BuilderConfig
from buildbot.interfaces import IBuildStepFactory
from buildbot.process.buildstep import BuildStep
from buildbot.process.factory import BuildFactory
from buildbot.process.results import CANCELLED
from buildbot.test.fake.latent import LatentController
from buildbot.test.fake.reactor import NonThreadPool
from buildbot.test.fake.reactor import TestReactor
from buildbot.test.util.integration import getMaster
from buildbot.worker.local import LocalWorker

try:
    from buildbot_worker.bot import LocalWorker as RemoteWorker
except ImportError:
    RemoteWorker = None


@implementer(IBuildStepFactory)
class StepController(object):

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.steps = []

    def buildStep(self):
        step_deferred = Deferred()
        step = ControllableStep(step_deferred, **self.kwargs)
        self.steps.append((step, step_deferred))
        return step


class ControllableStep(BuildStep):

    def run(self):
        return self._step_deferred

    def __init__(self, step_deferred, **kwargs):
        BuildStep.__init__(self, **kwargs)
        self._step_deferred = step_deferred

    def interrupt(self, reason):
        self._step_deferred.callback(CANCELLED)


class Tests(SynchronousTestCase):

    def setUp(self):
        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.reactor = TestReactor()

    def tearDown(self):
        self.assertFalse(self.master.running, "master is still running!")

    def test_latent_max_builds(self):
        """
        If max_builds is set, only one build is started on a latent
        worker at a time.
        """
        controller = LatentController(
            'local',
            max_builds=1,
        )
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
        self.master = master = self.successResultOf(
            getMaster(self, self.reactor, config_dict))
        builder_ids = [
            self.successResultOf(master.data.updates.findBuilderId('testy-1')),
            self.successResultOf(master.data.updates.findBuilderId('testy-2')),
        ]

        started_builds = []
        self.successResultOf(master.mq.startConsuming(
            lambda key, build: started_builds.append(build),
            ('builds', None, 'new')))

        # Trigger a buildrequest
        bsid, brids = self.successResultOf(
            master.data.updates.addBuildset(
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
        )

        # The worker fails to substantiate.
        controller.start_instance(True)

        controller.connect_worker(self)

        self.assertEqual(len(started_builds), 1)
        controller.auto_stop(True)

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
            'workers': [LocalWorker('local', max_builds=1)],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        self.master = master = self.successResultOf(
            getMaster(self, self.reactor, config_dict))
        builder_ids = [
            self.successResultOf(master.data.updates.findBuilderId('testy-1')),
            self.successResultOf(master.data.updates.findBuilderId('testy-2')),
        ]

        started_builds = []
        self.successResultOf(master.mq.startConsuming(
            lambda key, build: started_builds.append(build),
            ('builds', None, 'new')))

        # Trigger a buildrequest
        bsid, brids = self.successResultOf(
            master.data.updates.addBuildset(
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
        )

        self.assertEqual(len(started_builds), 1)

    if RemoteWorker is None:
        skip = "buildbot-worker package is not installed"
