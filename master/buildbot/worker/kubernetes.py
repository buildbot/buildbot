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

from twisted.internet import defer

from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util import kubeclientservice
from buildbot.util.latent import CompatibleLatentWorkerMixin
from buildbot.util.logger import Logger
from buildbot.worker.docker import DockerBaseWorker

log = Logger()


class KubeLatentWorker(DockerBaseWorker, CompatibleLatentWorkerMixin):

    instance = None
    builds_may_be_incompatible = True

    @defer.inlineCallbacks
    def getPodSpec(self, build):
        image = yield build.render(self.image)
        env = yield self.createEnvironment(build)
        defer.returnValue({
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": self.getContainerName()
            },
            "spec": {
                "containers": [{
                    "name":
                    self.getContainerName(),
                    "image": image,
                    "env": [{
                        "name": k,
                        "value": v
                    } for k, v in env.items()],
                    "resources": (yield self.getBuildContainerResources(build))
                }] + (yield self.getServicesContainers(build)),
                "restartPolicy":
                "Never"
            }
        })

    def getBuildContainerResources(self, build):
        # customization point to generate Build container resources
        return {}

    def getServicesContainers(self, build):
        # customization point to create services containers around the build container
        # those containers will run within the same localhost as the build container (aka within the same pod)
        return []

    def renderWorkerProps(self, build_props):
        return self.getPodSpec(build_props)

    def checkConfig(self,
                    name,
                    image='buildbot/buildbot-worker',
                    namespace=None,
                    masterFQDN=None,
                    kube_config=None,
                    **kwargs):

        super().checkConfig(name, None, **kwargs)
        kubeclientservice.KubeClientService.checkAvailable(
            self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self,
                        name,
                        image='buildbot/buildbot-worker',
                        namespace=None,
                        masterFQDN=None,
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
        yield super().reconfigService(name, image=image, masterFQDN=masterFQDN, **kwargs)
        self._kube = yield kubeclientservice.KubeClientService.getService(
            self.master, kube_config=kube_config)
        self.namespace = namespace or self._kube.namespace

    @defer.inlineCallbacks
    def start_instance(self, build):
        yield self.stop_instance(reportFailure=False)
        pod_spec = yield self.renderWorkerPropsOnStart(build)
        try:
            yield self._kube.createPod(self.namespace, pod_spec)
        except kubeclientservice.KubeError as e:
            raise LatentWorkerFailedToSubstantiate(str(e))
        defer.returnValue(True)

    @defer.inlineCallbacks
    def stop_instance(self, fast=False, reportFailure=True):
        self.current_pod_spec = None
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
