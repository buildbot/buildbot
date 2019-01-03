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

import copy
import json
import os
from io import BytesIO

import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.test.util import config
from buildbot.util import kubeclientservice
from buildbot.util import service


class MockFileBase(object):
    file_mock_config = {}

    def setUp(self):
        self.patcher = mock.patch('buildbot.util.kubeclientservice.open',
                                  self.mock_open)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def mock_open(self, filename, mode=None):
        filename_type = os.path.basename(filename)
        file_value = self.file_mock_config[filename_type]
        mock_open = mock.Mock(
            __enter__=mock.Mock(return_value=BytesIO(file_value)),
            __exit__=mock.Mock())
        return mock_open


class KubeClientServiceTestClusterConfig(
        MockFileBase, config.ConfigErrorsMixin, unittest.SynchronousTestCase):

    file_mock_config = {
        'token': 'BASE64_TOKEN'.encode('utf-8'),
        'namespace': 'buildbot_namespace'.encode('utf-8')
    }

    def setUp(self):
        MockFileBase.setUp(self)
        self.patch(kubeclientservice.os, 'environ',
                   {'KUBERNETES_PORT': 'tcp://foo'})

    def tearDown(self):
        return MockFileBase.tearDown(self)

    def patchExist(self, val):
        self.patch(kubeclientservice.os.path, 'exists', lambda x: val)

    def test_not_exists(self):
        self.patchExist(False)
        with self.assertRaisesConfigError('kube_dir not found:'):
            config = kubeclientservice.KubeInClusterConfigLoader()

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


class KubeClientServiceTestKubeCtlProxyConfig(config.ConfigErrorsMixin,
                                              unittest.TestCase):
    def patchProxyCmd(self, cmd):
        self.patch(kubeclientservice.KubeCtlProxyConfigLoader,
                   'kube_ctl_proxy_cmd', ["python", "-c", cmd])

    def tearDown(self):
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
                         b'Starting to serve on 127.0.0.1:8002\n')
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
