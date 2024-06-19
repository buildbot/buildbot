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

import os
import sys
from io import StringIO
from unittest import mock
from unittest.case import SkipTest

from twisted.internet import defer
from twisted.python import runtime
from twisted.trial import unittest

from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import config
from buildbot.util import kubeclientservice
from buildbot.util import service


class MockFileBase:
    file_mock_config = {}

    def setUp(self):
        self.patcher = mock.patch('buildbot.util.kubeclientservice.open', self.mock_open)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def mock_open(self, filename, mode=None, encoding='UTF-8'):
        filename_type = os.path.basename(filename)
        file_value = self.file_mock_config[filename_type]
        mock_open = mock.Mock(
            __enter__=mock.Mock(return_value=StringIO(file_value)), __exit__=mock.Mock()
        )
        return mock_open


class KubeClientServiceTestClusterConfig(MockFileBase, config.ConfigErrorsMixin, unittest.TestCase):
    file_mock_config = {'token': 'BASE64_TOKEN', 'namespace': 'buildbot_namespace'}

    def setUp(self):
        super().setUp()
        self.patch(kubeclientservice.os, 'environ', {'KUBERNETES_PORT': 'tcp://foo'})

    def patchExist(self, val):
        self.patch(kubeclientservice.os.path, 'exists', lambda x: val)

    def test_not_exists(self):
        self.patchExist(False)
        with self.assertRaisesConfigError('kube_dir not found:'):
            kubeclientservice.KubeInClusterConfigLoader()

    @defer.inlineCallbacks
    def test_basic(self):
        self.patchExist(True)
        config = kubeclientservice.KubeInClusterConfigLoader()
        yield config.startService()
        self.assertEqual(
            config.getConfig(),
            {
                'headers': {'Authorization': 'Bearer BASE64_TOKEN'},
                'master_url': 'https://foo',
                'namespace': 'buildbot_namespace',
                'verify': '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt',
            },
        )


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


class KubeClientServiceTestKubeHardcodedConfig(
    TestReactorMixin, config.ConfigErrorsMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self, "http://localhost:8001"
        )
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    def test_basic(self):
        self.config = kubeclientservice.KubeHardcodedConfig(
            master_url="http://localhost:8001", namespace="default"
        )
        self.assertEqual(
            self.config.getConfig(),
            {'master_url': 'http://localhost:8001', 'namespace': 'default', 'headers': {}},
        )

    def test_cannot_pass_both_bearer_and_basic_auth(self):
        with self.assertRaises(Exception):
            kubeclientservice.KubeHardcodedConfig(
                master_url="http://localhost:8001",
                namespace="default",
                verify="/path/to/pem",
                basicAuth="Bla",
                bearerToken="Bla",
            )


class KubeClientServiceTestKubeCtlProxyConfig(config.ConfigErrorsMixin, unittest.TestCase):
    def patchProxyCmd(self, cmd):
        if runtime.platformType != 'posix':
            self.config = None
            raise SkipTest('only posix platform is supported by this test')
        self.patch(
            kubeclientservice.KubeCtlProxyConfigLoader,
            'kube_ctl_proxy_cmd',
            [sys.executable, "-c", cmd],
        )

    def tearDown(self):
        if self.config is not None and self.config.running:
            return self.config.stopService()
        return None

    @defer.inlineCallbacks
    def test_basic(self):
        self.patchProxyCmd(KUBE_CTL_PROXY_FAKE)
        self.config = kubeclientservice.KubeCtlProxyConfigLoader()
        yield self.config.startService()
        self.assertEqual(
            self.config.getConfig(), {'master_url': 'http://localhost:8001', 'namespace': 'default'}
        )

    @defer.inlineCallbacks
    def test_config_args(self):
        self.patchProxyCmd(KUBE_CTL_PROXY_FAKE)
        self.config = kubeclientservice.KubeCtlProxyConfigLoader(
            proxy_port=8002, namespace="system"
        )
        yield self.config.startService()
        self.assertEqual(self.config.kube_proxy_output, b'Starting to serve on 127.0.0.1:8002')
        self.assertEqual(
            self.config.getConfig(), {'master_url': 'http://localhost:8002', 'namespace': 'system'}
        )
        yield self.config.stopService()

    @defer.inlineCallbacks
    def test_reconfig(self):
        self.patchProxyCmd(KUBE_CTL_PROXY_FAKE)
        self.config = kubeclientservice.KubeCtlProxyConfigLoader(
            proxy_port=8002, namespace="system"
        )
        yield self.config.startService()
        self.assertEqual(self.config.kube_proxy_output, b'Starting to serve on 127.0.0.1:8002')
        self.assertEqual(
            self.config.getConfig(), {'master_url': 'http://localhost:8002', 'namespace': 'system'}
        )
        yield self.config.reconfigService(proxy_port=8003, namespace="system2")
        self.assertEqual(self.config.kube_proxy_output, b'Starting to serve on 127.0.0.1:8003')
        self.assertEqual(
            self.config.getConfig(), {'master_url': 'http://localhost:8003', 'namespace': 'system2'}
        )
        yield self.config.stopService()

    @defer.inlineCallbacks
    def test_config_with_error(self):
        self.patchProxyCmd(KUBE_CTL_PROXY_FAKE_ERROR)
        self.config = kubeclientservice.KubeCtlProxyConfigLoader()
        with self.assertRaises(RuntimeError):
            yield self.config.startService()


class KubeClientServiceTest(unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.parent = service.BuildbotService(name="parent")
        self.client = kubeclientservice.KubeClientService()
        yield self.client.setServiceParent(self.parent)

    @defer.inlineCallbacks
    def tearDown(self):
        if self.parent.running:
            yield self.parent.stopService()

    @defer.inlineCallbacks
    def test_stopped(self):
        worker = mock.Mock(name="worker1")
        config = service.BuildbotService(name="config")

        yield self.client.register(worker, config)
        self.assertEqual(config.running, 0)
        yield self.client.unregister(worker)
        self.assertEqual(config.running, 0)

    @defer.inlineCallbacks
    def test_started(self):
        yield self.parent.startService()

        worker = mock.Mock(name="worker1")
        config = service.BuildbotService(name="config")

        yield self.client.register(worker, config)
        self.assertEqual(config.running, 1)
        yield self.client.unregister(worker)
        self.assertEqual(config.running, 0)

    @defer.inlineCallbacks
    def test_started_but_stop(self):
        yield self.parent.startService()

        worker = mock.Mock(name="worker1")
        config = service.BuildbotService(name="config")

        yield self.client.register(worker, config)
        self.assertEqual(config.running, 1)

        yield self.parent.stopService()
        self.assertEqual(config.running, 0)

    @defer.inlineCallbacks
    def test_stopped_but_start(self):
        worker = mock.Mock(name="worker1")
        config = service.BuildbotService(name="config")

        yield self.client.register(worker, config)
        self.assertEqual(config.running, 0)

        yield self.parent.startService()
        self.assertEqual(config.running, 1)

        yield self.parent.stopService()
        self.assertEqual(config.running, 0)

    @defer.inlineCallbacks
    def test_two_workers(self):
        yield self.parent.startService()

        worker1 = mock.Mock(name="worker1")
        worker2 = mock.Mock(name="worker2")
        config = service.BuildbotService(name="config")

        yield self.client.register(worker1, config)
        self.assertEqual(config.running, 1)
        yield self.client.register(worker2, config)
        self.assertEqual(config.running, 1)
        yield self.client.unregister(worker1)
        self.assertEqual(config.running, 1)
        yield self.client.unregister(worker2)
        self.assertEqual(config.running, 0)
