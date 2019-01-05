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

import socket

from twisted.internet import defer

from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util import kubeclientservice
from buildbot.util.logger import Logger
from buildbot.worker.docker import DockerBaseWorker

log = Logger()


class KubeLatentWorker(DockerBaseWorker):

    instance = None

    def default_pod_spec(self):
        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": self.getContainerName()
            },
            "spec": {
                "containers": [{
                    "name":
                    self.getContainerName(),
                    "image":
                    self.image,
                    "env": [{
                        "name": k,
                        "value": v
                    } for k, v in self.createEnvironment().items()]
                }],
                "restartPolicy":
                "Never"
            }
        }

    def checkConfig(self,
                    name,
                    image='buildbot/buildbot-worker',
                    namespace=None,
                    masterFQDN=None,
                    kube_extra_spec=None,
                    kube_config=None,
                    **kwargs):

        DockerBaseWorker.checkConfig(self, name, None, **kwargs)
        kubeclientservice.KubeClientService.checkAvailable(
            self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self,
                        name,
                        image='buildbot/buildbot-worker',
                        namespace=None,
                        masterFQDN=None,
                        kube_extra_spec=None,
                        kube_config=None,
                        **kwargs):

        # Set build_wait_timeout to 0 if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.
        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        if masterFQDN is None:
            masterFQDN = self.get_ip
        if callable(masterFQDN):
            masterFQDN = masterFQDN()
        yield DockerBaseWorker.reconfigService(
            self, name, image=image, masterFQDN=masterFQDN, **kwargs)
        self._kube = yield kubeclientservice.KubeClientService.getService(
            self.master, kube_config=kube_config)
        self.namespace = namespace or self._kube.namespace
        self.kube_extra_spec = kube_extra_spec or {}

    @defer.inlineCallbacks
    def start_instance(self, build):
        yield self.stop_instance(reportFailure=False)
        pod_spec = self.merge_spec(self.default_pod_spec(),
                                   self.kube_extra_spec)
        try:
            yield self._kube.createPod(self.namespace, pod_spec)
        except kubeclientservice.KubeError as e:
            raise LatentWorkerFailedToSubstantiate(str(e))
        defer.returnValue(True)

    @defer.inlineCallbacks
    def stop_instance(self, fast=False, reportFailure=True):
        try:
            yield self._kube.deletePod(self.namespace, self.getContainerName())
        except kubeclientservice.KubeError as e:
            if reportFailure and e.reason != 'NotFound':
                raise
        if fast:
            return
        yield self._kube.waitForPodDeletion(
            self.namespace,
            self.getContainerName(),
            timeout=self.missing_timeout)

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
                        '"{0}"\nand\n"{1}"'.format(value, patch_value))
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
