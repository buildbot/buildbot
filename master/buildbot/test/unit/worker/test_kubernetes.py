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

import base64
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake.fakebuild import FakeBuildForRendering as FakeBuild
from buildbot.test.fake.fakeprotocol import FakeTrivialConnection as FakeBot
from buildbot.test.reactor import TestReactorMixin
from buildbot.util.kubeclientservice import KubeHardcodedConfig
from buildbot.worker import kubernetes


class FakeResult:
    code = 204


def mock_delete(*args):
    return defer.succeed(FakeResult())


KUBE_CTL_PROXY_FAKE = """
import time
import sys

print("Starting to serve on 127.0.0.1:" + sys.argv[2])
sys.stdout.flush()
time.sleep(1000)
"""


KUBE_CTL_PROXY_FAKE_ERROR = """
import time
import sys

print("Issue with the config!", file=sys.stderr)
sys.stderr.flush()
sys.exit(1)
"""


class TestKubernetesWorker(TestReactorMixin, unittest.TestCase):
    worker = None

    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def setupWorker(self, *args, config=None, **kwargs):
        self.patch(kubernetes.KubeLatentWorker, "_generate_random_password", lambda _: "random_pw")

        if config is None:
            config = KubeHardcodedConfig(master_url="https://kube.example.com")

        worker = kubernetes.KubeLatentWorker(
            *args, masterFQDN="buildbot-master", kube_config=config, **kwargs
        )
        self.master = yield fakemaster.make_master(self, wantData=True)
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self, "https://kube.example.com"
        )

        yield worker.setServiceParent(self.master)
        yield self.master.startService()
        self.assertTrue(config.running)
        self.addCleanup(self.master.stopService)
        return worker

    def get_expected_metadata(self):
        return {"name": "buildbot-worker-87de7e"}

    def get_expected_spec(self, image):
        return {
            "affinity": {},
            "containers": [
                {
                    "name": "buildbot-worker-87de7e",
                    "image": image,
                    "env": [
                        {"name": "BUILDMASTER", "value": "buildbot-master"},
                        {"name": "BUILDMASTER_PROTOCOL", "value": "pb"},
                        {"name": "WORKERNAME", "value": "worker"},
                        {"name": "WORKERPASS", "value": "random_pw"},
                        {"name": "BUILDMASTER_PORT", "value": "1234"},
                    ],
                    "resources": {},
                    "volumeMounts": [],
                }
            ],
            "nodeSelector": {},
            "restartPolicy": "Never",
            "volumes": [],
        }

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
        worker = yield self.setupWorker('worker')
        # http is lazily created on worker substantiation
        self.assertEqual(worker.builds_may_be_incompatible, True)

    @defer.inlineCallbacks
    def test_start_service(self):
        worker = yield self.setupWorker('worker')
        # http is lazily created on worker substantiation
        self.assertNotEqual(worker._kube, None)

    def expect_pod_delete_nonexisting(self):
        self._http.expect(
            "delete",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e",
            params={"graceperiod": 0},
            code=404,
            content_json={"message": "Pod not found", "reason": "NotFound"},
        )

    def expect_pod_delete_existing(self, image):
        self._http.expect(
            "delete",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e",
            params={"graceperiod": 0},
            code=200,
            content_json={
                "kind": "Pod",
                "metadata": self.get_expected_metadata(),
                "spec": self.get_expected_spec(image),
            },
        )

    def expect_pod_status_not_found(self):
        self._http.expect(
            "get",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e/status",
            code=404,
            content_json={"kind": "Status", "reason": "NotFound"},
        )

    def expect_pod_status_exists(self, image):
        self._http.expect(
            "get",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e/status",
            code=200,
            content_json={
                "kind": "Pod",
                "metadata": self.get_expected_metadata(),
                "spec": self.get_expected_spec(image),
            },
        )

    def expect_pod_startup(self, image):
        self._http.expect(
            "post",
            "/api/v1/namespaces/default/pods",
            json={
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": self.get_expected_metadata(),
                "spec": self.get_expected_spec(image),
            },
            code=200,
            content_json={
                "kind": "Pod",
                "metadata": self.get_expected_metadata(),
                "spec": self.get_expected_spec(image),
            },
        )

    def expect_pod_startup_error(self, image):
        self._http.expect(
            "post",
            "/api/v1/namespaces/default/pods",
            json={
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": self.get_expected_metadata(),
                "spec": self.get_expected_spec(image),
            },
            code=400,
            content_json={"kind": "Status", "reason": "MissingName", "message": "need name"},
        )

    @defer.inlineCallbacks
    def test_start_worker(self):
        worker = yield self.setupWorker('worker')
        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()
        self.expect_pod_startup("rendered:buildbot/buildbot-worker")
        self.expect_pod_delete_existing("rendered:buildbot/buildbot-worker")
        self.expect_pod_status_not_found()

        d = worker.substantiate(None, FakeBuild())
        worker.attached(FakeBot())
        yield d

    @defer.inlineCallbacks
    def test_start_worker_but_error(self):
        worker = yield self.setupWorker('worker')
        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()
        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()

        def create_pod(namespace, spec):
            raise kubernetes.KubeJsonError(400, {'message': "yeah, but no"})

        with mock.patch.object(worker, '_create_pod', create_pod):
            with self.assertRaises(LatentWorkerFailedToSubstantiate):
                yield worker.substantiate(None, FakeBuild())
        self.assertEqual(worker.instance, None)

    @defer.inlineCallbacks
    def test_start_worker_but_error_spec(self):
        worker = yield self.setupWorker('worker')

        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()
        self.expect_pod_startup_error("rendered:buildbot/buildbot-worker")
        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()

        with self.assertRaises(LatentWorkerFailedToSubstantiate):
            yield worker.substantiate(None, FakeBuild())
        self.assertEqual(worker.instance, None)

    @defer.inlineCallbacks
    def test_interpolate_renderables_for_new_build(self):
        build1 = Properties(img_prop="image1")
        build2 = Properties(img_prop="image2")
        worker = yield self.setupWorker('worker', image=Interpolate("%(prop:img_prop)s"))

        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()
        self.expect_pod_startup("image1")
        self.expect_pod_delete_existing("image1")
        self.expect_pod_status_not_found()

        yield worker.start_instance(build1)
        yield worker.stop_instance()
        self.assertTrue((yield worker.isCompatibleWithBuild(build2)))

    @defer.inlineCallbacks
    def test_reject_incompatible_build_while_running(self):
        build1 = Properties(img_prop="image1")
        build2 = Properties(img_prop="image2")
        worker = yield self.setupWorker('worker', image=Interpolate("%(prop:img_prop)s"))

        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()
        self.expect_pod_startup("image1")
        self.expect_pod_delete_existing("image1")
        self.expect_pod_status_not_found()

        yield worker.start_instance(build1)
        self.assertFalse((yield worker.isCompatibleWithBuild(build2)))
        yield worker.stop_instance()

    @defer.inlineCallbacks
    def test_start_worker_delete_non_json_response(self):
        worker = yield self.setupWorker('worker')
        self._http.expect(
            "delete",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e",
            params={"graceperiod": 0},
            code=404,
            content="not json",
        )

        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()

        with self.assertRaises(LatentWorkerFailedToSubstantiate) as e:
            yield worker.substantiate(None, FakeBuild())
        self.assertIn("Failed to decode: not json", e.exception.args[0])

    @defer.inlineCallbacks
    def test_start_worker_delete_timeout(self):
        worker = yield self.setupWorker('worker', missing_timeout=4)

        self.expect_pod_delete_existing("rendered:buildbot/buildbot-worker")
        self.expect_pod_status_exists("rendered:buildbot/buildbot-worker")
        self.expect_pod_status_exists("rendered:buildbot/buildbot-worker")
        self.expect_pod_status_exists("rendered:buildbot/buildbot-worker")
        self.expect_pod_status_exists("rendered:buildbot/buildbot-worker")
        self.expect_pod_status_exists("rendered:buildbot/buildbot-worker")

        d = worker.stop_instance()
        self.reactor.pump([0.5] * 20)
        with self.assertRaises(TimeoutError):
            yield d

    @defer.inlineCallbacks
    def test_start_worker_create_non_json_response(self):
        worker = yield self.setupWorker('worker')

        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()

        expected_metadata = {"name": "buildbot-worker-87de7e"}
        expected_spec = {
            "affinity": {},
            "containers": [
                {
                    "name": "buildbot-worker-87de7e",
                    "image": "rendered:buildbot/buildbot-worker",
                    "env": [
                        {"name": "BUILDMASTER", "value": "buildbot-master"},
                        {"name": "BUILDMASTER_PROTOCOL", "value": "pb"},
                        {"name": "WORKERNAME", "value": "worker"},
                        {"name": "WORKERPASS", "value": "random_pw"},
                        {"name": "BUILDMASTER_PORT", "value": "1234"},
                    ],
                    "resources": {},
                    "volumeMounts": [],
                }
            ],
            "nodeSelector": {},
            "restartPolicy": "Never",
            "volumes": [],
        }

        self._http.expect(
            "post",
            "/api/v1/namespaces/default/pods",
            json={
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": expected_metadata,
                "spec": expected_spec,
            },
            code=200,
            content="not json",
        )
        self.expect_pod_delete_nonexisting()
        self.expect_pod_status_not_found()

        with self.assertRaises(LatentWorkerFailedToSubstantiate) as e:
            yield worker.substantiate(None, FakeBuild())
        self.assertIn("Failed to decode: not json", e.exception.args[0])

    @defer.inlineCallbacks
    def test_hardcoded_config_verify_is_forwarded(self):
        config = KubeHardcodedConfig(
            master_url="https://kube.example.com", namespace="default", verify="/path/to/pem"
        )
        worker = yield self.setupWorker('worker', config=config)

        self._http.expect(
            "delete",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e",
            params={"graceperiod": 0},
            verify="/path/to/pem",
            code=200,
            content_json={},
        )
        self._http.expect(
            "get",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e/status",
            verify="/path/to/pem",
            code=404,
            content_json={"kind": "Status", "reason": "NotFound"},
        )

        yield worker.stop_instance()

    @defer.inlineCallbacks
    def test_hardcoded_config_verify_headers_is_forwarded(self):
        config = KubeHardcodedConfig(
            master_url="https://kube.example.com",
            namespace="default",
            verify="/path/to/pem",
            headers={"Test": "10"},
        )
        worker = yield self.setupWorker('worker', config=config)

        self._http.expect(
            "delete",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e",
            params={"graceperiod": 0},
            headers={'Test': '10'},
            verify="/path/to/pem",
            code=200,
            content_json={},
        )
        self._http.expect(
            "get",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e/status",
            headers={'Test': '10'},
            verify="/path/to/pem",
            code=404,
            content_json={"kind": "Status", "reason": "NotFound"},
        )

        yield worker.stop_instance()

    @defer.inlineCallbacks
    def test_hardcoded_config_verify_bearer_token_is_rendered(self):
        config = KubeHardcodedConfig(
            master_url="https://kube.example.com",
            namespace="default",
            verify="/path/to/pem",
            bearerToken=Interpolate("%(kw:test)s", test=10),
        )
        worker = yield self.setupWorker('worker', config=config)

        self._http.expect(
            "delete",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e",
            params={"graceperiod": 0},
            headers={"Authorization": "Bearer 10"},
            verify="/path/to/pem",
            code=200,
            content_json={},
        )
        self._http.expect(
            "get",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e/status",
            headers={"Authorization": "Bearer 10"},
            verify="/path/to/pem",
            code=404,
            content_json={"kind": "Status", "reason": "NotFound"},
        )

        yield worker.stop_instance()

    @defer.inlineCallbacks
    def test_hardcoded_config_verify_basicAuth_is_expanded(self):
        config = KubeHardcodedConfig(
            master_url="https://kube.example.com",
            namespace="default",
            verify="/path/to/pem",
            basicAuth={'user': 'name', 'password': Interpolate("%(kw:test)s", test=10)},
        )
        worker = yield self.setupWorker('worker', config=config)

        self._http.expect(
            "delete",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e",
            params={"graceperiod": 0},
            headers={"Authorization": "Basic " + str(base64.b64encode(b"name:10"))},
            verify="/path/to/pem",
            code=200,
            content_json={},
        )
        self._http.expect(
            "get",
            "/api/v1/namespaces/default/pods/buildbot-worker-87de7e/status",
            headers={"Authorization": "Basic " + str(base64.b64encode(b"name:10"))},
            verify="/path/to/pem",
            code=404,
            content_json={"kind": "Status", "reason": "NotFound"},
        )

        yield worker.stop_instance()
