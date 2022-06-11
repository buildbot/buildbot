# This file is part of Buildbot. Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import abc
import base64
import os
import time

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.error import ProcessExitedAlready
from twisted.logger import Logger
from twisted.python.failure import Failure

from buildbot import config
from buildbot.util import asyncSleep
from buildbot.util.httpclientservice import HTTPClientService
from buildbot.util.protocol import LineProcessProtocol
from buildbot.util.service import BuildbotService

log = Logger()


# this is a BuildbotService, so that it can be started and destroyed.
# this is needed to implement kubectl proxy lifecycle
class KubeConfigLoaderBase(BuildbotService):
    name = "KubeConfig"

    @abc.abstractmethod
    def getConfig(self):
        """
        @return dictionary with optional params
        {
            'master_url': 'https://kube_master.url',
            'namespace': 'default_namespace',
            'headers' {
                'Authentication': XXX
            }
            # todo (quite hard to implement with treq):
            'cert': 'optional client certificate used to connect to ssl'
            'verify': 'kube master certificate authority to use to connect'
        }
        """

    def getAuthorization(self):
        return None

    def __str__(self):
        """return unique str for SharedService"""
        # hash is implemented from ComparableMixin
        return f"{self.__class__.__name__}({hash(self)})"


class KubeHardcodedConfig(KubeConfigLoaderBase):
    def reconfigService(self,
                        master_url=None,
                        bearerToken=None,
                        basicAuth=None,
                        headers=None,
                        cert=None,
                        verify=None,
                        namespace="default"):
        self.config = {'master_url': master_url, 'namespace': namespace, 'headers': {}}
        if headers is not None:
            self.config['headers'] = headers
        if basicAuth and bearerToken:
            raise Exception("set one of basicAuth and bearerToken, not both")
        self.basicAuth = basicAuth
        self.bearerToken = bearerToken
        if cert is not None:
            self.config['cert'] = cert
        if verify is not None:
            self.config['verify'] = verify

    checkConfig = reconfigService

    @defer.inlineCallbacks
    def getAuthorization(self):
        if self.basicAuth is not None:
            basicAuth = yield self.renderSecrets(self.basicAuth)
            authstring = f"{basicAuth['user']}:{basicAuth['password']}".encode('utf-8')
            encoded = base64.b64encode(authstring)
            return f"Basic {encoded}"

        if self.bearerToken is not None:
            bearerToken = yield self.renderSecrets(self.bearerToken)
            return f"Bearer {bearerToken}"

        return None

    def getConfig(self):
        return self.config


class KubeCtlProxyConfigLoader(KubeConfigLoaderBase):
    """ We use kubectl proxy to connect to kube master.
    Parsing the config and setting up SSL is complex.
    So for now, we use kubectl proxy to load the config and connect to master.
    This will run the kube proxy as a subprocess, and return configuration with
    http://localhost:PORT
    """
    kube_ctl_proxy_cmd = ['kubectl', 'proxy']  # for tests override

    class LocalPP(LineProcessProtocol):
        def __init__(self):
            super().__init__()
            self.got_output_deferred = defer.Deferred()
            self.terminated_deferred = defer.Deferred()
            self.first_line = b""

        def outLineReceived(self, line):
            if not self.got_output_deferred.called:
                self.got_output_deferred.callback(line)

        def errLineReceived(self, line):
            if not self.got_output_deferred.called:
                self.got_output_deferred.errback(Failure(RuntimeError(line)))

        def processEnded(self, status):
            super().processEnded(status)
            self.terminated_deferred.callback(None)

    def checkConfig(self, proxy_port=8001, namespace="default"):
        self.pp = None
        self.process = None

    @defer.inlineCallbacks
    def ensureSubprocessKilled(self):
        if self.pp is not None:
            try:
                self.process.signalProcess("TERM")
            except ProcessExitedAlready:
                pass  # oh well
            yield self.pp.terminated_deferred

    @defer.inlineCallbacks
    def reconfigService(self, proxy_port=8001, namespace="default"):
        self.proxy_port = proxy_port
        self.namespace = namespace
        yield self.ensureSubprocessKilled()
        self.pp = self.LocalPP()
        self.process = reactor.spawnProcess(
            self.pp,
            self.kube_ctl_proxy_cmd[0],
            self.kube_ctl_proxy_cmd + ["-p", str(self.proxy_port)],
            env=None)
        self.kube_proxy_output = yield self.pp.got_output_deferred

    def stopService(self):
        return self.ensureSubprocessKilled()

    def getConfig(self):
        return {
            'master_url': f"http://localhost:{self.proxy_port}",
            'namespace': self.namespace
        }


class KubeInClusterConfigLoader(KubeConfigLoaderBase):
    kube_dir = '/var/run/secrets/kubernetes.io/serviceaccount/'

    kube_namespace_file = os.path.join(kube_dir, 'namespace')
    kube_token_file = os.path.join(kube_dir, 'token')
    kube_cert_file = os.path.join(kube_dir, 'ca.crt')

    def checkConfig(self):
        if not os.path.exists(self.kube_dir):
            config.error(f"Not in kubernetes cluster (kube_dir not found: {self.kube_dir})")

    def reconfigService(self):
        self.config = {}
        self.config['master_url'] = os.environ['KUBERNETES_PORT'].replace(
            'tcp', 'https')
        self.config['verify'] = self.kube_cert_file
        with open(self.kube_token_file, encoding="utf-8") as token_content:
            token = token_content.read().strip()
            self.config['headers'] = {
                'Authorization': f'Bearer {token}'.format(token)
            }
        with open(self.kube_namespace_file, encoding="utf-8") as namespace_content:
            self.config['namespace'] = namespace_content.read().strip()

    def getConfig(self):
        return self.config


class KubeError(RuntimeError):
    def __init__(self, response_json):
        super().__init__(response_json['message'])
        self.json = response_json
        self.reason = response_json.get('reason')


class KubeClientService(HTTPClientService):
    def __init__(self, kube_config=None):
        self.config = kube_config
        super().__init__('')
        self._namespace = None
        kube_config.setServiceParent(self)

    @defer.inlineCallbacks
    def _prepareRequest(self, ep, kwargs):
        config = self.config.getConfig()
        self._base_url = config['master_url']
        url, req_kwargs = super()._prepareRequest(ep, kwargs)

        if 'headers' not in req_kwargs:
            req_kwargs['headers'] = {}
        if 'headers' in config:
            req_kwargs['headers'].update(config['headers'])

        auth = yield self.config.getAuthorization()
        if auth is not None:
            req_kwargs['headers']['Authorization'] = auth

        # warning: this only works with txrequests! not treq
        for arg in ['cert', 'verify']:
            if arg in config:
                req_kwargs[arg] = config[arg]

        return (url, req_kwargs)

    @defer.inlineCallbacks
    def createPod(self, namespace, spec):
        url = f'/api/v1/namespaces/{namespace}/pods'
        res = yield self.post(url, json=spec)
        res_json = yield res.json()
        if res.code not in (200, 201, 202):
            raise KubeError(res_json)
        return res_json

    @defer.inlineCallbacks
    def deletePod(self, namespace, name, graceperiod=0):
        url = f'/api/v1/namespaces/{namespace}/pods/{name}'
        res = yield self.delete(url, params={'graceperiod': graceperiod})
        res_json = yield res.json()
        if res.code != 200:
            raise KubeError(res_json)
        return res_json

    @defer.inlineCallbacks
    def waitForPodDeletion(self, namespace, name, timeout):
        t1 = time.time()
        url = f'/api/v1/namespaces/{namespace}/pods/{name}/status'
        while True:
            if time.time() - t1 > timeout:
                raise TimeoutError(f"Did not see pod {name} terminate after {timeout}s")
            res = yield self.get(url)
            res_json = yield res.json()
            if res.code == 404:
                break  # 404 means the pod has terminated
            if res.code != 200:
                raise KubeError(res_json)
            yield asyncSleep(1)
        return res_json

    @property
    def namespace(self):
        if self._namespace is None:
            self._namespace = self.config.getConfig()['namespace']
        return self._namespace
