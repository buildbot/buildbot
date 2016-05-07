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

from twisted.internet.defer import Deferred
from twisted.python import threadpool
from twisted.python.failure import Failure
from twisted.python.filepath import FilePath
from twisted.trial.unittest import SynchronousTestCase

from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.process.results import SUCCESS
from buildbot.test.fake.reactor import NonThreadPool
from buildbot.test.fake.reactor import TestReactor
from buildbot.test.util.integration import getMaster
from buildbot.worker.base import AbstractLatentWorker

try:
    from buildbot_worker.bot import LocalWorker
except ImportError:
    LocalWorker = None


class LatentController(object):

    """
    A controller for ``ControllableLatentWorker``.

    https://glyph.twistedmatrix.com/2015/05/separate-your-fakes-and-your-inspectors.html
    """

    def __init__(self, name):
        self.worker = ControllableLatentWorker(name, self)
        self.started = False

    def start_instance(self, result):
        assert self.started
        self.started = False
        d, self._start_deferred = self._start_deferred, None
        d.callback(result)

    def connect_worker(self, workdir):
        LocalWorker(self.worker.name, workdir.path, False).setServiceParent(
            self.worker)


class ControllableLatentWorker(AbstractLatentWorker):

    """
    A latent worker that can be contolled by tests.
    """

    def __init__(self, name, controller):
        AbstractLatentWorker.__init__(self, name, None)
        self._controller = controller

    def checkConfig(self, name, _):
        AbstractLatentWorker.checkConfig(self, name, None)

    def reconfigService(self, name, _):
        AbstractLatentWorker.reconfigService(self, name, None)

    def start_instance(self, build):
        self._controller.started = True
        self._controller._start_deferred = Deferred()
        return self._controller._start_deferred

    def stop_instance(self, build):
        return Deferred()


class TestException(Exception):

    """
    An exception thrown in tests.
    """


class Tests(SynchronousTestCase):

    def setUp(self):
        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.reactor = TestReactor()

    def test_refused_substantiations_get_requeued(self):
        """
        If a latent worker refuses to substantiate, the build request becomes unclaimed.
        """
        controller = LatentController('local')
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
        master = self.successResultOf(
            getMaster(self, self.reactor, config_dict))
        builder_id = self.successResultOf(
            master.data.updates.findBuilderId('testy'))

        # Trigger a buildrequest
        bsid, brids = self.successResultOf(
            master.data.updates.addBuildset(
                waited_for=False,
                builderids=[builder_id],
                sourcestamps=[
                    {'codebase': '',
                     'repository': '',
                     'branch': None,
                     'revision': None,
                     'project': ''},
                ],
            )
        )

        unclaimed_build_requests = []
        self.successResultOf(master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed')))

        # Indicate that the worker can't start an instance.
        controller.start_instance(False)

        # When the substantiation fails, the buildrequest becomes unclaimed.
        self.assertEqual(
            set(brids),
            set([req['buildrequestid'] for req in unclaimed_build_requests]),
        )

    def test_failed_substantiations_get_requeued(self):
        """
        If a latent worker fails to substantiate, the build request becomes unclaimed.
        """
        controller = LatentController('local')
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
        master = self.successResultOf(
            getMaster(self, self.reactor, config_dict))
        builder_id = self.successResultOf(
            master.data.updates.findBuilderId('testy'))

        # Trigger a buildrequest
        bsid, brids = self.successResultOf(
            master.data.updates.addBuildset(
                waited_for=False,
                builderids=[builder_id],
                sourcestamps=[
                    {'codebase': '',
                     'repository': '',
                     'branch': None,
                     'revision': None,
                     'project': ''},
                ],
            )
        )

        unclaimed_build_requests = []
        self.successResultOf(master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed')))

        # The worker fails to substantiate.
        controller.start_instance(
            Failure(TestException("substantiation failed")))
        # Flush the errors logged by the failure.
        self.flushLoggedErrors(TestException)

        # When the substantiation fails, the buildrequest becomes unclaimed.
        self.assertEqual(
            set(brids),
            set([req['buildrequestid'] for req in unclaimed_build_requests]),
        )

    def test_worker_accepts_builds_after_failure(self):
        """
        If a latent worker fails to substantiate, the worker is still able to accept jobs.
        """
        controller = LatentController('local')
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
        master = self.successResultOf(
            getMaster(self, self.reactor, config_dict))
        builder_id = self.successResultOf(
            master.data.updates.findBuilderId('testy'))

        # Trigger a buildrequest
        bsid, brids = self.successResultOf(
            master.data.updates.addBuildset(
                waited_for=False,
                builderids=[builder_id],
                sourcestamps=[
                    {'codebase': '',
                     'repository': '',
                     'branch': None,
                     'revision': None,
                     'project': ''},
                ],
            )
        )

        unclaimed_build_requests = []
        self.successResultOf(master.mq.startConsuming(
            lambda key, request: unclaimed_build_requests.append(request),
            ('buildrequests', None, 'unclaimed')))

        # The worker fails to substantiate.
        controller.start_instance(
            Failure(TestException("substantiation failed")))
        # Flush the errors logged by the failure.
        self.flushLoggedErrors(TestException)

        # If the worker started again after the failure, then the retry logic will have
        # already kicked in to start a new build on this (the only) worker. We check that
        # a new instance was requested, which indicates that the worker
        # accepted the build.
        self.assertEqual(controller.started, True)

    def test_worker_multiple_substantiations_succeed(self):
        """
        If multiple builders trigger try to substantiate a worker at
        the same time, if the substantiation succeeds then all of
        the builds proceeed.
        """
        controller = LatentController('local')
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
            'multiMaster': True,
        }
        master = self.successResultOf(
            getMaster(self, self.reactor, config_dict))
        builder_ids = [
            self.successResultOf(master.data.updates.findBuilderId('testy-1')),
            self.successResultOf(master.data.updates.findBuilderId('testy-2')),
        ]

        finished_builds = []
        self.successResultOf(master.mq.startConsuming(
            lambda key, build: finished_builds.append(build),
            ('builds', None, 'finished')))

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

        local_workdir = FilePath(self.mktemp())
        local_workdir.createDirectory()
        controller.connect_worker(local_workdir)

        # We check that there were two builds that finished, and
        # that they both finished with success
        self.assertEqual([build['results']
                          for build in finished_builds], [SUCCESS] * 2)

    if LocalWorker is None:
        test_worker_multiple_substantiations_succeed.skip = "buildbot-slave package is not installed"
