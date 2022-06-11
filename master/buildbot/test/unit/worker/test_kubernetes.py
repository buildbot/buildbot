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
from twisted.trial import unittest

from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.test.fake import fakemaster
from buildbot.test.fake.fakebuild import FakeBuildForRendering as FakeBuild
from buildbot.test.fake.fakeprotocol import FakeTrivialConnection as FakeBot
from buildbot.test.fake.kube import KubeClientService
from buildbot.test.reactor import TestReactorMixin
from buildbot.util.kubeclientservice import KubeError
from buildbot.util.kubeclientservice import KubeHardcodedConfig
from buildbot.worker import kubernetes


class FakeResult:
    code = 204


def mock_delete(*args):
    return defer.succeed(FakeResult())


class TestKubernetesWorker(TestReactorMixin, unittest.TestCase):
    worker = None

    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def setupWorker(self, *args, **kwargs):
        config = KubeHardcodedConfig(master_url="https://kube.example.com")
        self.worker = worker = kubernetes.KubeLatentWorker(
            *args, kube_config=config, **kwargs)
        master = fakemaster.make_master(self, wantData=True)
        self._kube = yield KubeClientService.getService(master, self, kube_config=config)
        worker.setServiceParent(master)
        yield master.startService()
        self.assertTrue(config.running)

        def cleanup():
            self._kube.delete = mock_delete

        self.addCleanup(master.stopService)
        self.addCleanup(cleanup)
        return worker

    def test_instantiate(self):
        worker = kubernetes.KubeLatentWorker('worker')
        # class instantiation configures nothing
        self.assertEqual(getattr(worker, '_kube', None), None)

    @defer.inlineCallbacks
    def test_wrong_arg(self):
        with self.assertRaises(TypeError):
            yield self.setupWorker('worker', wrong_param='wrong_param')

    def test_service_arg(self):
        return self.setupWorker('worker')

    @defer.inlineCallbacks
    def test_builds_may_be_incompatible(self):
        yield self.setupWorker('worker')
        # http is lazily created on worker substantiation
        self.assertEqual(self.worker.builds_may_be_incompatible, True)

    @defer.inlineCallbacks
    def test_start_service(self):
        yield self.setupWorker('worker')
        # http is lazily created on worker substantiation
        self.assertNotEqual(self.worker._kube, None)

    @defer.inlineCallbacks
    def test_start_worker(self):
        worker = yield self.setupWorker('worker')
        d = worker.substantiate(None, FakeBuild())
        worker.attached(FakeBot())
        yield d
        self.assertEqual(len(worker._kube.pods), 1)
        pod_name = list(worker._kube.pods.keys())[0]
        self.assertRegex(pod_name, r'default/buildbot-worker-[0-9a-f]+')
        pod = worker._kube.pods[pod_name]
        self.assertEqual(
            sorted(pod['spec'].keys()), ['containers', 'restartPolicy'])
        self.assertEqual(
            sorted(pod['spec']['containers'][0].keys()),
            ['env', 'image', 'name', 'resources'])
        self.assertEqual(pod['spec']['containers'][0]['image'],
                         'rendered:buildbot/buildbot-worker')
        self.assertEqual(pod['spec']['restartPolicy'], 'Never')

    @defer.inlineCallbacks
    def test_start_worker_but_error(self):
        worker = yield self.setupWorker('worker')

        def createPod(namespace, spec):
            raise KubeError({'message': "yeah, but no"})

        self.patch(self._kube, 'createPod', createPod)
        with self.assertRaises(LatentWorkerFailedToSubstantiate):
            yield worker.substantiate(None, FakeBuild())
        self.assertEqual(worker.instance, None)

    @defer.inlineCallbacks
    def test_interpolate_renderables_for_new_build(self):
        build1 = Properties(img_prop="image1")
        build2 = Properties(img_prop="image2")
        worker = yield self.setupWorker('worker', image=Interpolate("%(prop:img_prop)s"))

        yield worker.start_instance(build1)
        yield worker.stop_instance()
        self.assertTrue((yield worker.isCompatibleWithBuild(build2)))

    @defer.inlineCallbacks
    def test_reject_incompatible_build_while_running(self):
        build1 = Properties(img_prop="image1")
        build2 = Properties(img_prop="image2")
        worker = yield self.setupWorker('worker', image=Interpolate("%(prop:img_prop)s"))

        yield worker.start_instance(build1)
        self.assertFalse((yield worker.isCompatibleWithBuild(build2)))
