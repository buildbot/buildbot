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

import os
from unittest.case import SkipTest

from twisted.internet import defer

from buildbot.config import BuilderConfig
from buildbot.plugins import schedulers
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase
from buildbot.util import kubeclientservice
from buildbot.worker import kubernetes

# This integration test creates a master and kubernetes worker environment,
# It requires a kubernetes cluster up and running. It tries to get the config
# like loading "~/.kube/config" files or environment variable.
# You can use minikube to create a kubernetes environment for development:

# # See https://github.com/kubernetes/minikube for full documentation
# minikube start # [--vm-driver=kvm]
#
# export masterFQDN=$(ip route get $(minikube ip)| awk '{ print $5 }')
# export KUBE_NAMESPACE=`kubectl config get-contexts \`kubectl config current-context\` |tail -n1 |awk '{print $5}'`

# useful commands:
#  - 'minikube dashboard' to display WebUI of the kubernetes cluster
#  - 'minikube ip' to display the IP of the kube-apimaster
#  - 'minikube ssh' to get a shell into the minikube VM

# following environment variable can be used to stress concurrent worker startup
NUM_CONCURRENT = int(os.environ.get("KUBE_TEST_NUM_CONCURRENT_BUILD", 1))


class KubernetesMaster(RunMasterBase):
    timeout = 200

    def setUp(self):
        if "TEST_KUBERNETES" not in os.environ:
            raise SkipTest(
                "kubernetes integration tests only run when environment "
                "variable TEST_KUBERNETES is set")
        if 'masterFQDN' not in os.environ:
            raise SkipTest(
                "you need to export masterFQDN. You have example in the test file. "
                "Make sure that you're spawned worker can callback this IP")

    @defer.inlineCallbacks
    def test_trigger(self):
        yield self.setupConfig(
            masterConfig(num_concurrent=NUM_CONCURRENT), startWorker=False)
        yield self.doForceBuild()

        builds = yield self.master.data.get(("builds", ))
        # if there are some retry, there will be more builds
        self.assertEqual(len(builds), 1 + NUM_CONCURRENT)
        for b in builds:
            self.assertEqual(b['results'], SUCCESS)


class KubernetesMasterTReq(KubernetesMaster):
    def setup(self):
        super().setUp()
        self.patch(kubernetes.KubeClientService, 'PREFER_TREQ', True)


# master configuration
def masterConfig(num_concurrent, extra_steps=None):
    if extra_steps is None:
        extra_steps = []
    c = {}

    c['schedulers'] = [
        schedulers.ForceScheduler(name="force", builderNames=["testy"])
    ]
    triggereables = []
    for i in range(num_concurrent):
        c['schedulers'].append(
            schedulers.Triggerable(
                name="trigsched" + str(i), builderNames=["build"]))
        triggereables.append("trigsched" + str(i))

    f = BuildFactory()
    f.addStep(steps.ShellCommand(command='echo hello'))
    f.addStep(
        steps.Trigger(
            schedulerNames=triggereables,
            waitForFinish=True,
            updateSourceStamp=True))
    f.addStep(steps.ShellCommand(command='echo world'))
    f2 = BuildFactory()
    f2.addStep(steps.ShellCommand(command='echo ola'))
    for step in extra_steps:
        f2.addStep(step)
    c['builders'] = [
        BuilderConfig(name="testy", workernames=["kubernetes0"], factory=f),
        BuilderConfig(
            name="build",
            workernames=["kubernetes" + str(i) for i in range(num_concurrent)],
            factory=f2)
    ]
    masterFQDN = os.environ.get('masterFQDN')
    c['workers'] = [
        kubernetes.KubeLatentWorker(
            'kubernetes' + str(i),
            'buildbot/buildbot-worker',
            kube_config=kubeclientservice.KubeCtlProxyConfigLoader(
                namespace=os.getenv("KUBE_NAMESPACE", "default")),
            masterFQDN=masterFQDN) for i in range(num_concurrent)
    ]
    # un comment for debugging what happens if things looks locked.
    # c['www'] = {'port': 8080}
    c['protocols'] = {"pb": {"port": "tcp:9989"}}

    return c
