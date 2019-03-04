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
import time

from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.util.kubeclientservice import KubeError


class KubeClientService(fakehttpclientservice.HTTPClientService):

    def __init__(self, kube_config=None, *args, **kwargs):
        c = kube_config.getConfig()
        super().__init__(c['master_url'], *args, **kwargs)
        self.namespace = c['namespace']
        self.addService(kube_config)
        self.pods = {}

    def createPod(self, namespace, spec):
        if 'metadata' not in spec:
            raise KubeError({
                'message': 'Pod "" is invalid: metadata.name: Required value: name or generateName is required'})
        name = spec['metadata']['name']
        pod = {
            'kind': 'Pod',
            'metadata': copy.copy(spec['metadata']),
            'spec': copy.deepcopy(spec['spec'])
        }
        self.pods[namespace + '/' + name] = pod
        return pod

    def deletePod(self, namespace, name, graceperiod=0):
        if namespace + '/' + name not in self.pods:
            raise KubeError({
                'message': 'Pod not found',
                'reason': 'NotFound'})

        spec = self.pods[namespace + '/' + name]

        del self.pods[namespace + '/' + name]
        spec['metadata']['deletionTimestamp'] = time.ctime(time.time())
        return spec

    def waitForPodDeletion(self, namespace, name, timeout):
        if namespace + '/' + name in self.pods:
            raise TimeoutError("Did not see pod {name} terminate after {timeout}s".format(
                name=name, timeout=timeout
            ))
        return {
            'kind': 'Status',
            'reason': 'NotFound'
        }
