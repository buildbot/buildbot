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

import base64
import copy
import os
import sys
import textwrap
from io import StringIO
from unittest.case import SkipTest

import yaml

import mock

from twisted.internet import defer
from twisted.python import runtime
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttp
from buildbot.test.fake import kube as fakekube
from buildbot.test.util import config
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import kubeclientservice


class MockFileBase:
    file_mock_config = {}

    def setUp(self):
        self.patcher = mock.patch('buildbot.util.kubeclientservice.open',
                                  self.mock_open)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def mock_open(self, filename, mode=None, encoding='UTF-8'):
        filename_type = os.path.basename(filename)
        file_value = self.file_mock_config[filename_type]
        mock_open = mock.Mock(
            __enter__=mock.Mock(return_value=StringIO(file_value)),
            __exit__=mock.Mock())
        return mock_open


class KubeClientServiceTestClusterConfig(
        MockFileBase, config.ConfigErrorsMixin, unittest.SynchronousTestCase):

    file_mock_config = {
        'token': 'BASE64_TOKEN',
        'namespace': 'buildbot_namespace'
    }

    def setUp(self):
        super().setUp()
        self.patch(kubeclientservice.os, 'environ',
                   {'KUBERNETES_PORT': 'tcp://foo'})

    def patchExist(self, val):
        self.patch(kubeclientservice.os.path, 'exists', lambda x: val)

    def test_not_exists(self):
        self.patchExist(False)
        with self.assertRaisesConfigError('kube_dir not found:'):
            kubeclientservice.KubeInClusterConfigLoader()

    def test_basic(self):
        self.patchExist(True)
        config = kubeclientservice.KubeInClusterConfigLoader()
        self.successResultOf(config.startService())
        self.assertEqual(
            config.getConfig(), {
                'headers': {
                    'Authorization': 'Bearer BASE64_TOKEN'
                },
                'master_url': 'https://foo',
                'namespace': 'buildbot_namespace',
                'verify':
                '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
            })


KUBE_CTL_PROXY_FAKE = """
from __future__ import print_function
import time
import sys

print("Starting to serve on 127.0.0.1:" + sys.argv[2])
sys.stdout.flush()
time.sleep(1000)
"""

KUBE_CTL_PROXY_FAKE_ERROR = """
from __future__ import print_function
import time
import sys

print("Issue with the config!", file=sys.stderr)
sys.stderr.flush()
sys.exit(1)
"""


class KubeClientServiceTestKubeHardcodedConfig(config.ConfigErrorsMixin,
                                              unittest.TestCase):
    def test_basic(self):
        self.config = config = kubeclientservice.KubeHardcodedConfig(
            master_url="http://localhost:8001",
            namespace="default"
        )
        self.assertEqual(config.getConfig(), {
            'master_url': 'http://localhost:8001',
            'namespace': 'default',
            'headers': {}
        })

    @defer.inlineCallbacks
    def test_verify_is_forwarded_to_keywords(self):
        self.config = config = kubeclientservice.KubeHardcodedConfig(
            master_url="http://localhost:8001",
            namespace="default",
            verify="/path/to/pem"
        )
        service = kubeclientservice.KubeClientService(config)
        url, kwargs = yield service._prepareRequest("/test", {})
        self.assertEqual('/path/to/pem', kwargs['verify'])

    @defer.inlineCallbacks
    def test_verify_headers_are_passed_to_the_query(self):
        self.config = config = kubeclientservice.KubeHardcodedConfig(
            master_url="http://localhost:8001",
            namespace="default",
            verify="/path/to/pem",
            headers={'Test': '10'}
        )
        service = kubeclientservice.KubeClientService(config)
        url, kwargs = yield service._prepareRequest("/test", {})
        self.assertEqual({'Test': '10'}, kwargs['headers'])

    def test_the_configuration_parent_is_set_to_the_service(self):
        # This is needed to allow secret expansion
        self.config = config = kubeclientservice.KubeHardcodedConfig(
            master_url="http://localhost:8001")
        service = kubeclientservice.KubeClientService(config)
        self.assertEqual(service, self.config.parent)

    def test_cannot_pass_both_bearer_and_basic_auth(self):
        with self.assertRaises(Exception):
            kubeclientservice.KubeHardcodedConfig(
                master_url="http://localhost:8001",
                namespace="default",
                verify="/path/to/pem",
                basicAuth="Bla",
                bearerToken="Bla")

    @defer.inlineCallbacks
    def test_verify_bearerToken_is_expanded(self):
        self.config = config = kubeclientservice.KubeHardcodedConfig(
            master_url="http://localhost:8001",
            namespace="default",
            verify="/path/to/pem",
            bearerToken=Interpolate("%(kw:test)s", test=10))
        service = kubeclientservice.KubeClientService(config)
        url, kwargs = yield service._prepareRequest("/test", {})
        self.assertEqual("Bearer 10", kwargs['headers']['Authorization'])

    @defer.inlineCallbacks
    def test_verify_basicAuth_is_expanded(self):
        self.config = config = kubeclientservice.KubeHardcodedConfig(
            master_url="http://localhost:8001",
            namespace="default",
            verify="/path/to/pem",
            basicAuth={'user': 'name', 'password': Interpolate("%(kw:test)s", test=10)})
        service = kubeclientservice.KubeClientService(config)
        url, kwargs = yield service._prepareRequest("/test", {})

        expected = "Basic {0}".format(base64.b64encode("name:10".encode('utf-8')))
        self.assertEqual(expected, kwargs['headers']['Authorization'])


class KubeClientServiceTestKubeCtlProxyConfig(config.ConfigErrorsMixin,
                                              unittest.TestCase):
    def patchProxyCmd(self, cmd):
        if runtime.platformType != 'posix':
            self.config = None
            raise SkipTest('only posix platform is supported by this test')
        self.patch(kubeclientservice.KubeCtlProxyConfigLoader,
                   'kube_ctl_proxy_cmd', [sys.executable, "-c", cmd])

    def tearDown(self):
        if self.config is not None:
            return self.config.stopService()

    @defer.inlineCallbacks
    def test_basic(self):
        self.patchProxyCmd(KUBE_CTL_PROXY_FAKE)
        self.config = config = kubeclientservice.KubeCtlProxyConfigLoader()
        yield config.startService()
        self.assertEqual(config.getConfig(), {
            'master_url': 'http://localhost:8001',
            'namespace': 'default'
        })

    @defer.inlineCallbacks
    def test_config_args(self):
        self.patchProxyCmd(KUBE_CTL_PROXY_FAKE)
        self.config = config = kubeclientservice.KubeCtlProxyConfigLoader(
            proxy_port=8002, namespace="system")
        yield config.startService()
        self.assertEqual(config.kube_proxy_output,
                         b'Starting to serve on 127.0.0.1:8002')
        self.assertEqual(config.getConfig(), {
            'master_url': 'http://localhost:8002',
            'namespace': 'system'
        })
        yield config.stopService()

    @defer.inlineCallbacks
    def test_config_with_error(self):
        self.patchProxyCmd(KUBE_CTL_PROXY_FAKE_ERROR)
        self.config = config = kubeclientservice.KubeCtlProxyConfigLoader()
        with self.assertRaises(RuntimeError):
            yield config.startService()


# integration tests for KubeClientService
class RealKubeClientServiceTest(TestReactorMixin, unittest.TestCase):
    timeout = 200
    POD_SPEC = yaml.safe_load(
        textwrap.dedent("""
    apiVersion: v1
    kind: Pod
    metadata:
        name: pod-example
    spec:
        containers:
        - name: alpine
          image: alpine
          command: ["sleep"]
          args: ["100"]
    """))

    def createKube(self):
        if "TEST_KUBERNETES" not in os.environ:
            raise SkipTest(
                "kubernetes integration tests only run when environment "
                "variable TEST_KUBERNETES is set")

        self.kube = kubeclientservice.KubeClientService(
            kubeclientservice.KubeCtlProxyConfigLoader())

    def expect(self, *args, **kwargs):
        pass

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self)
        self.createKube()
        self.kube.setServiceParent(self.master)
        return self.master.startService()

    def tearDown(self):
        return self.master.stopService()

    kube = None

    @defer.inlineCallbacks
    def test_create_and_delete_pod(self):
        content = {'kind': 'Pod', 'metadata': {'name': 'pod-example'}}
        self.expect(
            method='post',
            ep='/api/v1/namespaces/default/pods',
            params=None,
            data=None,
            json={
                'apiVersion': 'v1',
                'kind': 'Pod',
                'metadata': {
                    'name': 'pod-example'
                },
                'spec': {
                    'containers': [{
                        'name': 'alpine',
                        'image': 'alpine',
                        'command': ['sleep'],
                        'args': ['100']
                    }]
                }
            },
            content_json=content)
        res = yield self.kube.createPod(self.kube.namespace, self.POD_SPEC)
        self.assertEqual(res['kind'], 'Pod')
        self.assertEqual(res['metadata']['name'], 'pod-example')
        self.assertNotIn('deletionTimestamp', res['metadata'])

        content['metadata']['deletionTimestamp'] = 'now'
        self.expect(
            method='delete',
            ep='/api/v1/namespaces/default/pods/pod-example',
            params={'graceperiod': 0},
            data=None,
            json=None,
            code=200,
            content_json=content)

        res = yield self.kube.deletePod(self.kube.namespace, 'pod-example')
        self.assertEqual(res['kind'], 'Pod')
        self.assertIn('deletionTimestamp', res['metadata'])

        # first time present
        self.expect(
            method='get',
            ep='/api/v1/namespaces/default/pods/pod-example/status',
            params=None,
            data=None,
            json=None,
            code=200,
            content_json=content)
        # second time deleted
        content = {'kind': 'Status', 'reason': 'NotFound'}
        self.expect(
            method='get',
            ep='/api/v1/namespaces/default/pods/pod-example/status',
            params=None,
            data=None,
            json=None,
            code=404,
            content_json=content)

        res = yield self.kube.waitForPodDeletion(
            self.kube.namespace, 'pod-example', timeout=200)
        self.assertEqual(res['kind'], 'Status')
        self.assertEqual(res['reason'], 'NotFound')

    @defer.inlineCallbacks
    def test_create_bad_spec(self):
        spec = copy.deepcopy(self.POD_SPEC)
        del spec['metadata']
        content = {
            'kind': 'Status',
            'reason': 'MissingName',
            'message': 'need name'
        }
        self.expect(
            method='post',
            ep='/api/v1/namespaces/default/pods',
            params=None,
            data=None,
            json={
                'apiVersion': 'v1',
                'kind': 'Pod',
                'spec': {
                    'containers': [{
                        'name': 'alpine',
                        'image': 'alpine',
                        'command': ['sleep'],
                        'args': ['100']
                    }]
                }
            },
            code=400,
            content_json=content)
        with self.assertRaises(kubeclientservice.KubeError):
            yield self.kube.createPod(self.kube.namespace, spec)

    @defer.inlineCallbacks
    def test_delete_not_existing(self):
        content = {
            'kind': 'Status',
            'reason': 'NotFound',
            'message': 'no container by that name'
        }
        self.expect(
            method='delete',
            ep='/api/v1/namespaces/default/pods/pod-example',
            params={'graceperiod': 0},
            data=None,
            json=None,
            code=404,
            content_json=content)
        with self.assertRaises(kubeclientservice.KubeError):
            yield self.kube.deletePod(self.kube.namespace, 'pod-example')

    @defer.inlineCallbacks
    def test_wait_for_delete_not_deleting(self):
        yield self.kube.createPod(self.kube.namespace, self.POD_SPEC)
        with self.assertRaises(TimeoutError):
            yield self.kube.waitForPodDeletion(
                self.kube.namespace, 'pod-example', timeout=2)
        res = yield self.kube.deletePod(self.kube.namespace, 'pod-example')
        self.assertEqual(res['kind'], 'Pod')
        self.assertIn('deletionTimestamp', res['metadata'])
        yield self.kube.waitForPodDeletion(
            self.kube.namespace, 'pod-example', timeout=100)


class FakeKubeClientServiceTest(RealKubeClientServiceTest):
    def createKube(self):
        self.kube = fakekube.KubeClientService(
            kubeclientservice.KubeHardcodedConfig(master_url='http://m'))


class PatchedKubeClientServiceTest(RealKubeClientServiceTest):
    def createKube(self):
        self.kube = kubeclientservice.KubeClientService(
            kubeclientservice.KubeHardcodedConfig(master_url='http://m'))
        self.http = fakehttp.HTTPClientService('http://m')
        self.kube.get = self.http.get
        self.kube.post = self.http.post
        self.kube.put = self.http.put
        self.kube.delete = self.http.delete

    def expect(self, *args, **kwargs):
        return self.http.expect(*args, **kwargs)

    def test_wait_for_delete_not_deleting(self):
        # no need to describe the expect flow for that case
        pass
