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

from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.util import httpclientservice
from buildbot.util import service
from buildbot.worker import kubernetes


class KubeClientServiceTestBase(unittest.SynchronousTestCase):

    def setUp(self):
        if httpclientservice.txrequests is None or httpclientservice.treq is None:
            raise unittest.SkipTest('this test requires txrequests and treq')
        self.patch(httpclientservice, 'txrequests', mock.Mock())
        self.patch(httpclientservice, 'treq', mock.Mock())
        self.parent = service.MasterService()
        self.parent.reactor = reactor
        self.successResultOf(self.parent.startService())


class KubeClientServiceTestRequest(KubeClientServiceTestBase):

    def setUp(self):
        KubeClientServiceTestBase.setUp(self)
        self.patch(
            kubernetes.KubeClientService,
            'guess_config',
            self.guess_config_mock
        )
        self._kube = self.successResultOf(
            kubernetes.KubeClientService.getService(self.parent)
        )

    def guess_config_mock(class_self, config_method):
        return 'http://foo', {}, 'default_namespace'

    def test_get(self):
        self._kube.get('/bar')
        self._kube._session.request.assert_called_once_with(
            'get', 'http://foo/bar', headers={}, background_callback=mock.ANY
        )

    def test_post(self):
        self._kube.post('/bar')
        self._kube._session.request.assert_called_once_with(
            'post', 'http://foo/bar', headers={}, background_callback=mock.ANY
        )


class MockFileBase(object):

    def setUp(self):
        KubeClientServiceTestBase.setUp(self)
        self.patcher = mock.patch(
            'buildbot.worker.kubernetes.open',
            self.mock_open
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def mock_open(self, filename, mode=None):
        filename_type = os.path.basename(filename)
        file_value = self.file_mock_config[filename_type]
        mock_open = mock.Mock(
            __enter__=mock.Mock(return_value=BytesIO(file_value)),
            __exit__=mock.Mock()
        )
        return mock_open


class KubeClientServiceTestKubeConfig(
        KubeClientServiceTestBase,
        MockFileBase
):

    kube_config_dict = {
        'apiVersion': 'v1',
        'current-context': 'buildbot-test-context',
        'clusters': [{
            'name': 'cluster_name',
            'cluster': {
                'server': 'http://foo'
            }
        }],
        'users': [{
            'name': 'user_name',
            'user': {
                'login': 'login',
                'password': 'password'
            }
        }],
        'contexts': [{
            'name': 'buildbot-test-context',
            'context': {
                'cluster': 'cluster_name',
                'user': 'user_name',
                'namespace': 'buildbot'
            }
        }]
    }

    file_mock_config = {
        # json is subset of yaml,
        # it will be loaded by `yaml.loads` without problem
        # this avoid the yaml dependency in the test
        'config': json.dumps(kube_config_dict).encode('utf-8')
    }

    def setUp(self):
        if not kubernetes.HAS_YAML:
            raise unittest.SkipTest('this test requires yaml')
        KubeClientServiceTestBase.setUp(self)
        MockFileBase.setUp(self)

    def tearDown(self):
        if hasattr(self, '_kube'):
            self._kube.stopService()
        return MockFileBase.tearDown(self)

    def test_simple_http(self):
        self._kube = self.successResultOf(
            kubernetes.KubeClientService.getService(self.parent)
        )
        self._kube.get('/bar')
        self._kube._session.request.assert_called_once_with(
            'get', 'http://foo/bar', headers={}, background_callback=mock.ANY
        )

    def test_certificate_path(self):
        kube_config_dict = copy.deepcopy(self.kube_config_dict)
        kube_config_dict['clusters'][0]['cluster'].update({
            'certificate-authority': 'filename'
        })
        self.file_mock_config = {
            'config': json.dumps(kube_config_dict).encode('utf-8')
        }
        self._kube = self.successResultOf(
            kubernetes.KubeClientService.getService(self.parent)
        )
        self._kube.get('/bar')
        self._kube._session.request.assert_called_once_with(
            'get', 'http://foo/bar', headers={}, verify='filename',
            background_callback=mock.ANY
        )

    def test_certificate_data(self):
        kube_config_dict = copy.deepcopy(self.kube_config_dict)
        kube_config_dict['clusters'][0]['cluster'].update({
            'certificate-authority-data': 'CERTIFICATE_DATA'
        })
        self.file_mock_config = {
            'config': json.dumps(kube_config_dict).encode('utf-8')
        }
        self._kube = self.successResultOf(
            kubernetes.KubeClientService.getService(self.parent)
        )
        self._kube.get('/bar')
        cert_file = self._kube._session.request.call_args[1]['verify']
        self._kube._session.request.assert_called_once_with(
            'get', 'http://foo/bar', headers={}, verify=cert_file,
            background_callback=mock.ANY
        )
        with open(cert_file) as cert_content:
            self.assertEqual(cert_content.read(), 'CERTIFICATE_DATA')
        self._kube.stopService()
        self.assertEqual(os.path.exists(cert_file), False)
        del self._kube

    def test_dont_valid_cert(self):
        kube_config_dict = copy.deepcopy(self.kube_config_dict)
        kube_config_dict['clusters'][0]['cluster'].update({
            'insecure-skip-tls-verify': True
        })
        self.file_mock_config = {
            'config': json.dumps(kube_config_dict).encode('utf-8')
        }
        self._kube = self.successResultOf(
            kubernetes.KubeClientService.getService(self.parent)
        )
        self._kube.get('/bar')
        self._kube._session.request.assert_called_once_with(
            'get', 'http://foo/bar', headers={}, verify=False,
            background_callback=mock.ANY
        )


class KubeClientServiceTestClusterConfig(
        KubeClientServiceTestBase,
        MockFileBase
):

    file_mock_config = {
        'token': 'BASE64_TOKEN'.encode('utf-8'),
        'namespace': 'buildbot_namespace'.encode('utf-8')
    }

    def setUp(self):
        KubeClientServiceTestBase.setUp(self)
        MockFileBase.setUp(self)
        self.patch(
            kubernetes.os,
            'environ',
            {'KUBERNETES_PORT': 'tcp://foo'}
        )
        self._kube = self.successResultOf(
            kubernetes.KubeClientService.getService(
                self.parent,
                config_method='incluster_config_loader'
            )
        )

    def tearDown(self):
        return MockFileBase.tearDown(self)

    def test_get(self):
        self._kube.get('/bar')
        self._kube._session.request.assert_called_once_with(
            'get',
            'https://foo/bar',
            headers={'Authorization': 'Bearer BASE64_TOKEN'},
            verify='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt',
            background_callback=mock.ANY
        )
