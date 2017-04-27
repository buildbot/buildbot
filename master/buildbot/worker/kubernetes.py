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

import os
import socket
import tempfile

from twisted.internet import defer

from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util.httpclientservice import HTTPClientService
from buildbot.util.logger import Logger
from buildbot.worker.docker import DockerBaseWorker

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

if PY2:
    FileNotFoundError = IOError


log = Logger()


class KubeClientService(HTTPClientService):

    default_kubeconfig = '~/.kube/config'

    kube_dir = '/var/run/secrets/kubernetes.io/serviceaccount/'

    kube_namespace_file = os.path.join(kube_dir, 'namespace')
    kube_token_file = os.path.join(kube_dir, 'token')
    kube_cert_file = os.path.join(kube_dir, 'ca.crt')

    config_loader_list = ['kube_config_loader', 'incluster_config_loader']

    def __init__(self,
                 kubeconfig=None,
                 config_method=None):
        self.kube_config_file = kubeconfig or self.default_kubeconfig
        self._cert_file = None
        url, req_kwargs, namespace = self.guess_config(config_method)
        self._cert = req_kwargs.pop('cert', None)
        self._verify = req_kwargs.pop('verify', None)
        HTTPClientService.__init__(self, url, **req_kwargs)
        self.namespace = namespace

    def guess_config(self, config_method=None):
        if isinstance(config_method, string_types):
            config_loader_iter = iter((config_method,))
        elif config_method is None:
            config_loader_iter = iter(self.config_loader_list)
        else:
            try:
                config_loader_iter = iter(config_method)
            except TypeError:
                config_loader_iter = iter((config_method,))
        for config in config_loader_iter:
            if callable(config):
                config_loader = config
            else:
                try:
                    config_loader = getattr(self, config)
                except AttributeError:
                    raise ValueError(
                        "Unknown config method '{0}'. "
                        "Only {1} are available.".format(
                            config, self.config_loader_list
                        )
                    )
            if not config_loader:
                continue
            try:
                return config_loader()
            except KubeClientConfigException:
                continue
        else:
            raise KubeClientConfigException(
                'Cannot find a working configurator'
            )

    def stopService(self):
        if self._cert_file:
            os.remove(self._cert_file)
        return HTTPClientService.stopService(self)

    def _prepareRequest(self, ep, kwargs):
        url, req_kwargs = HTTPClientService._prepareRequest(self, ep, kwargs)
        if self._cert is not None and 'cert' not in req_kwargs:
            req_kwargs['cert'] = self._cert
        if self._verify is not None and 'verify' not in req_kwargs:
            req_kwargs['verify'] = self._verify
        return url, req_kwargs

    @property
    def kube_config_loader(self):
        if HAS_YAML:
            return self._kube_config_loader
        else:
            log.showwarning(
                "python-yaml module is not available, "
                "can't load kubeconfig file."
            )
            return None

    def _kube_config_loader(self):
        kube_config = os.path.expanduser(self.kube_config_file)
        try:
            with open(kube_config) as yaml_config:
                config_tree = yaml.load(yaml_config)
        except FileNotFoundError:
            raise KubeClientConfigException('Kubeconfig file not found')
        try:
            current_context_name = config_tree['current-context']
        except KeyError:
            raise ValueError("Cannot find 'current-context'")
        context = self.search_section(
            config_tree['contexts'],
            current_context_name
        )
        cluster_name = context['context']['cluster']

        cluster = self.search_section(config_tree['clusters'], cluster_name)
        request_kwargs = {}
        url = self.load_server_config(cluster['cluster'], request_kwargs)
        user_name = context['context']['user']
        user = self.search_section(config_tree['users'], user_name)
        self.load_user_config(user['user'], request_kwargs)
        namespace = context['context'].get('namespace', 'default')
        return url, request_kwargs, namespace

    def load_server_config(self, cluster, request_kwargs):
        try:
            url = cluster['server']
        except KeyError:
            raise ValueError(
                "cluster config misses mandatory value: 'cluster.server'"
            )
        skip_ssl = cluster.get('insecure-skip-tls-verify', False)
        cert_data = cluster.get('certificate-authority-data', None)
        cert_path = cluster.get('certificate-authority', None)
        if cert_data:
            tmp = tempfile.NamedTemporaryFile(delete=False)
            tmp.write(cert_data.encode('utf-8'))
            self._cert_file = cert_path = tmp.name
            tmp.close()
        if cert_path:
            request_kwargs['verify'] = cert_path
        if skip_ssl:
            request_kwargs['verify'] = False
        return url

    def load_user_config(self, user, request_kwargs):
        client_cert = user.get('client-certificate', None)
        client_key = user.get('client-key', None)
        username = user.get('username', None)
        password = user.get('password', None)
        if client_cert and client_key:
            request_kwargs['cert'] = (client_cert, client_key)
        if username and password:
            request_kwargs['auth'] = (username, password)

    def incluster_config_loader(self):
        url = os.environ['KUBERNETES_PORT'].replace('tcp', 'https')
        req_kwargs = {'verify': self.kube_cert_file, 'headers': {}}
        with open(self.kube_token_file) as token_content:
            token = token_content.read().decode('utf-8').strip()
            req_kwargs['headers']['Authorization'] = 'Bearer {0}'.format(token)
        with open(self.kube_namespace_file) as namespace_content:
            namespace = namespace_content.read().decode('utf-8').strip()
        return url, req_kwargs, namespace

    def search_section(self, tree, name):
        for element in tree:
            if element['name'] == name:
                return element
        else:
            raise ValueError("Cannot find entry '{}'".format(name))


class KubeClientConfigException(Exception):
    """Raised when config can't be loaded"""


class KubeLatentWorker(DockerBaseWorker):

    instance = None

    kubeclientservice_args = ['kubeconfig', 'config_method']

    def default_job_spec(self):
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": self.getContainerName()
            },
            "spec": {
                "template": {
                    "metadata": {
                        "name": self.getContainerName()
                    },
                    "spec": {
                        "containers": [{
                            "name": self.getContainerName(),
                            "image": self.image,
                            "env": [
                                {"name": "BUILDMASTER",
                                 "value": self.masterFQDN},
                                {"name": "BUILDMASTER_PORT",
                                 "value": "9989"},
                                {"name": "WORKERNAME",
                                 "value": self.name},
                                {"name": "WORKERPASS",
                                 "value": self.password}
                            ]
                        }],
                        "restartPolicy": "Never"
                    }
                }
            }
        }

    def checkConfig(self,
                    name,
                    password=None,
                    image='buildbot/buildbot-worker',
                    namespace=None,
                    masterFQDN=None,
                    kube_extra_spec=None,
                    **kwargs):

        # Set build_wait_timeout to 0 if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.
        self._extract_kube_args(kwargs)
        DockerBaseWorker.checkConfig(self, name, password, **kwargs)
        KubeClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self,
                        name,
                        password=None,
                        image='buildbot/buildbot-worker',
                        namespace=None,
                        masterFQDN=None,
                        kube_extra_spec=None,
                        **kwargs):

        # Set build_wait_timeout to 0 if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.
        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        if masterFQDN is None:
            masterFQDN = self.__class__.get_ip
        if callable(masterFQDN):
            masterFQDN = masterFQDN()
        kube_kwargs = self._extract_kube_args(kwargs)
        yield DockerBaseWorker.reconfigService(
            self, name, password, image=image, masterFQDN=masterFQDN, **kwargs)
        self._kube = yield KubeClientService.getService(
            self.master, **kube_kwargs)
        self.kube_extra_spec = kube_extra_spec or {}

    def _extract_kube_args(self, kwargs):
        kube_kwargs = {}
        for args in self.kubeclientservice_args:
            try:
                kube_kwargs[args] = kwargs.pop(args)
            except KeyError:
                pass
        return kube_kwargs

    @defer.inlineCallbacks
    def start_instance(self, build):
        yield self.stop_instance(reportFailure=False)
        job_spec = self.merge_spec(
             self.default_job_spec(),
             self.kube_extra_spec
        )
        url = '/apis/batch/v1/namespaces/{namespace}/jobs'.format(
            namespace=self._kube.namespace
        )
        res = yield self._kube.post(url, json=job_spec)
        if res.code != 201:
            raise LatentWorkerFailedToSubstantiate(
                "Unable to create Kubernetes job %s" % res.code
            )
        res_json = yield res.json()
        self.instance = res_json
        defer.returnValue(True)

    @defer.inlineCallbacks
    def stop_instance(self, fast=False, reportFailure=True):
        if self.instance is None:
            # be gentle. Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            defer.returnValue(True)
        url = "/apis/batch/v1/namespaces/{namespace}/jobs/{job}".format(
            namespace=self._kube.namespace,
            job=self.instance['metadata']['name']
        )
        res = yield self._kube.delete(url)
        self.instance = None
        if res.code != 204 and reportFailure:
            res_json = yield res.json()
            log.warn(
                "Unable to delete kubenertes job: {_id} {code}: {details}",
                _id=self.getContainerName(),
                code=res.code,
                details=res_json
            )

    @classmethod
    def merge_spec(cls, spec_obj, patch):
        copy_spec = spec_obj.copy()
        for key, patch_value in patch.items():
            try:
                value = spec_obj[key]
            except KeyError:
                pass
            else:
                if type(value) != type(patch_value):
                    raise TypeError(
                        'Cannot merge kubernetes spec with different type. '
                        '(For example a list with a dict). '
                        'This happens between\n'
                        '"{0}"\nand\n"{1}"'.format(value, patch_value)
                    )
                if isinstance(value, dict):
                    patch_value = cls.merge_spec(value, patch_value)
                if isinstance(value, list):
                    patch_value = list(value).extend(patch_value)
            copy_spec[key] = patch_value
        return copy_spec

    @staticmethod
    def get_fqdn():
        return socket.getfqdn()

    @staticmethod
    def get_ip():
        fqdn = socket.getfqdn()
        try:
            return socket.gethostbyname(fqdn)
        except socket.gaierror:
            return fqdn
