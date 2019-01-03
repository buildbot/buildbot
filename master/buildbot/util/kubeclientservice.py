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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from future.utils import PY2
from future.utils import string_types

import abc
import os
import tempfile

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
from twisted.python.failure import Failure
from twisted.internet.error import ProcessExitedAlready

from buildbot import config
from buildbot.util.httpclientservice import HTTPClientService
from buildbot.util.logger import Logger
from buildbot.util.service import BuildbotService

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

if PY2:
    FileNotFoundError = IOError


log = Logger()

# this is a BuildbotService, so that it can be started and destroyed.
# this is needed to implement kubectl proxy lifecycle
class KubeConfigBaseLoader(BuildbotService):
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


    def __str__(self):
        """return unique str for SharedService"""
        # hash is implemented from ComparableMixin
        return "{}({})".format(self.__class__.__name__, hash(self))

class KubeHardcodedConfig(KubeConfigBaseLoader):
    def reconfigService(
        self,
        master_url=None,
        headers=None,
        cert=None,
        verify=None,
        namespace="default"
        ):
        self.config = {
            'master_url': master_url,
            'namespace': namespace
            }
        if headers is not None:
            self.config['headers'] = headers
        if cert is not None:
            self.config['cert'] = cert
        if verify is not None:
            self.config['verify'] = verify
    checkConfig = reconfigService
    def getConfig(self):
        return self.config

class KubeCtlProxyConfigLoader(KubeConfigBaseLoader):
    """ We use kubectl proxy to connect to kube master.
    Parsing the config and setting up SSL is complex.
    So for now, we use kubectl proxy to load the config and connect to master.
    This will run the kube proxy as a subprocess, and return configuration with
    http://localhost:PORT
    """
    kube_ctl_proxy_cmd = ['kubectl', 'proxy']  # for tests override
    class LocalPP(ProcessProtocol):

        def __init__(self, config_loader):
            self.config_loader = config_loader
            self.got_output_deferred = defer.Deferred()
            self.terminated_deferred = defer.Deferred()

        def outReceived(self, data):
            if not self.got_output_deferred.called:
                self.got_output_deferred.callback(data)

        def errReceived(self, data):
            if not self.got_output_deferred.called:
                self.got_output_deferred.errback(Failure(RuntimeError(data)))

        def processEnded(self, status_object):
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
        self.pp = self.LocalPP(self)
        self.process = reactor.spawnProcess(
            self.pp,
            self.kube_ctl_proxy_cmd[0],
            self.kube_ctl_proxy_cmd + ["-p", str(self.proxy_port)],
            env=None)
        self.kube_proxy_output = yield self.pp.got_output_deferred

    def stopService(self):
        return self.ensureSubprocessKilled()

    def getConfig(self):
        return {'master_url': "http://localhost:{}".format(self.proxy_port),
                'namespace': self.namespace}

class KubeInClusterConfigLoader(KubeConfigBaseLoader):
    kube_dir = '/var/run/secrets/kubernetes.io/serviceaccount/'

    kube_namespace_file = os.path.join(kube_dir, 'namespace')
    kube_token_file = os.path.join(kube_dir, 'token')
    kube_cert_file = os.path.join(kube_dir, 'ca.crt')
    def checkConfig(self):
        if not os.path.exists(self.kube_dir):
            return config.error(
                "Not in kubernetes cluster (kube_dir not found: {})".format(
                    self.kube_dir))

    def reconfigService(self):
        self.config = {}
        self.config['master_url'] = os.environ['KUBERNETES_PORT'].replace('tcp', 'https')
        self.config['verify'] = self.kube_cert_file
        with open(self.kube_token_file) as token_content:
            token = token_content.read().decode('utf-8').strip()
            self.config['headers'] = {'Authorization': 'Bearer {0}'.format(token)}
        with open(self.kube_namespace_file) as namespace_content:
            self.config['namespace'] = namespace_content.read().decode('utf-8').strip()

    def getConfig(self):
        return self.config

class KubeClientService(HTTPClientService):

    def __init__(self,
                 kube_config=None):
        self.config = kube_config
        HTTPClientService.__init__(self, '')
        self._namespace = None
        self.addService(kube_config)

    def _prepareRequest(self, ep, kwargs):
        config = self.config.getConfig()
        self._base_url = config['master_url']
        url, req_kwargs = HTTPClientService._prepareRequest(self, ep, kwargs)

        # warning: this only works with txrequests! not treq
        for arg in ['cert', 'verify']:
            if arg in config:
                req_kwargs[arg] = self.config[arg]

        return url, req_kwargs

    @property
    def namespace(self):
        if self._namespace is None:
            self._namespace = self.config.getConfig()['namespace']
        return self._namespace
