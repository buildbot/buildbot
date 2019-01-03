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

from twisted.internet import defer

from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util.kubeclientservice import KubeClientService
from buildbot.util.logger import Logger
from buildbot.worker.docker import DockerBaseWorker


log = Logger()


class KubeLatentWorker(DockerBaseWorker):

    instance = None

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
                    image='buildbot/buildbot-worker',
                    namespace=None,
                    masterFQDN=None,
                    kube_extra_spec=None,
                    kube_config=None,
                    **kwargs):

        DockerBaseWorker.checkConfig(self, name, None, **kwargs)
        KubeClientService.checkAvailable(self.__class__.__name__)

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
        self._kube = yield KubeClientService.getService(
            self.master, kube_config=kube_config)
        self.kube_extra_spec = kube_extra_spec or {}

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
