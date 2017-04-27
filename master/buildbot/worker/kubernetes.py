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

import hashlib
import json
import socket

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import config
from buildbot.interfaces import IProperties
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.util import unicode2bytes
from buildbot.worker.docker import AbstractLatentWorker

try:
    from kubernetes import config as kube_config
    from kubernetes import client
except ImportError as exc:
    kube_config = None
    client = None

if PY2:
    FileNotFoundError = IOError


class KubeLatentWorker(AbstractLatentWorker):
    instance = None

    properties_source = 'kube Latent Worker'

    @staticmethod
    def dependency_error():
        config.error("The python module 'kubernetes>=1' is needed to use a "
                     "KubeLatentWorker")

    def load_config(self, kubeConfig):
        try:
            kube_config.load_kube_config()
        except (FileNotFoundError,
                kube_config.config_exception.ConfigException):
            try:
                kube_config.load_incluster_config()
            except kube_config.config_exception.ConfigException:
                pass
        kubeConfig = kubeConfig or {}
        for config_key, value in kubeConfig.items():
            setattr(client.configuration, config_key, value)
        if not client.configuration.host:
            config.error("No kube-apimaster host provided")

    @staticmethod
    def default_job():
        return Interpolate(
            """{
                 "apiVersion": "batch/v1",
                 "kind": "Job",
                 "metadata": {
                   "name": "%(prop:buildername)s-%(prop:buildnumber)s"
                 },
                 "spec": {
                   "template": {
                     "metadata": {
                       "name": "%(prop:buildername)s-%(prop:buildnumber)s"
                     },
                     "spec": {
                       "containers": [{
                         "name": "%(prop:buildername)s-%(prop:buildnumber)s",
                         "image": "buildbot/buildbot-worker",
                         "env": [
                           {"name": "BUILDMASTER",
                            "value": "%(prop:masterFQDN)s"},
                           {"name": "BUILDMASTER_PORT",
                            "value": "%(prop:masterPort)s"},
                           {"name": "WORKERNAME",
                            "value": "%(prop:workerName)s"},
                           {"name": "WORKERPASS",
                            "value": "%(prop:workerPass)s"}
                         ]
                       }],
                       "restartPolicy": "Never"
                     }
                   }
                 }
               }""")

    def checkConfig(self, name, password, job=None, namespace=None,
                    masterFQDN=None, getMasterMethod=None,
                    kubeConfig=None, **kwargs):

        # Set build_wait_timeout to 0 if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.
        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        if not client:
            self.dependency_error()
        self.load_config(kubeConfig)
        AbstractLatentWorker.checkConfig(self, name, password, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self, name, password, job=None, namespace=None,
                        masterFQDN=None, getMasterMethod=None,
                        kubeConfig=None, **kwargs):

        # Set build_wait_timeout to 0 if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.
        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        if password is None:
            password = self.getRandomPass()
        self.getMasterMethod = getMasterMethod
        if masterFQDN is None:
            masterFQDN = self.get_master_qdn
        if callable(masterFQDN):
            masterFQDN = masterFQDN()
        self.masterFQDN = masterFQDN
        self.load_config(kubeConfig)
        self.kubeConfig = kubeConfig
        self.namespace = namespace or 'default'
        self.job = job or self.default_job()
        masterName = unicode2bytes(self.master.name)
        self.masterhash = hashlib.sha1(masterName).hexdigest()[:6]
        yield AbstractLatentWorker.reconfigService(
            self, name, password, **kwargs)

    @defer.inlineCallbacks
    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')
        masterFQDN = self.masterFQDN
        masterPort = '9989'
        if self.registration is not None:
            masterPort = str(self.registration.getPBPort())
        if ":" in masterFQDN:
            masterFQDN, masterPort = masterFQDN.split(':')
        master_properties = Properties.fromDict({
            'masterHash': (self.masterhash, self.properties_source),
            'masterFQDN': (masterFQDN, self.properties_source),
            'masterPort': (masterPort, self.properties_source),
            'workerName': (self.name, self.properties_source),
            'workerPass': (self.password, self.properties_source)
        })
        props = IProperties(build)
        props.updateFromProperties(master_properties)
        namespace = yield build.render(self.namespace)
        job = yield build.render(self.job)
        res = yield threads.deferToThread(
            self._thd_start_instance,
            namespace,
            job
        )
        defer.returnValue(res)

    def _thd_start_instance(self, namespace, job):
        self.load_config(self.kubeConfig)
        batch_client = client.BatchV1Api()

        instance = batch_client.create_namespaced_job(
            namespace,
            json.loads(job)
        )

        if instance is None:
            log.msg('Failed to create the container')
            raise LatentWorkerFailedToSubstantiate(
                'Failed to start container'
            )
        job_name = instance.metadata.name
        log.msg('Job created, Id: %s...' % job_name)
        self.instance = instance
        return [
            job_name,
            instance.spec.template.spec.containers[0].image
        ]

    def stop_instance(self, fast=False):
        if self.instance is None:
            # be gentle. Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        instance = self.instance
        self.instance = None
        return threads.deferToThread(self._thd_stop_instance, instance, fast)

    def _thd_stop_instance(self, instance, fast):
        assert not False
        self.load_config(self.kubeConfig)
        batch_client = client.BatchV1Api()
        delete_body = client.V1DeleteOptions()
        job_name = instance.metadata.name
        namespace = instance.metadata.namespace
        log.msg('Deleting Job %s...' % job_name)
        batch_client.delete_namespaced_job(job_name, namespace, delete_body)

    def get_master_qdn(self):
        try:
            qdn_getter = self.get_master_mapping[self.getMasterMethod]
        except KeyError:
            qdn_getter = self.default_master_qdn_getter
        return qdn_getter()

    @staticmethod
    def get_fqdn():
        return socket.getfqdn()

    def get_ip(self):
        fqdn = self.get_fqdn()
        try:
            return socket.gethostbyname(fqdn)
        except socket.gaierror:
            return fqdn

    get_master_mapping = {
        'auto_ip': get_ip,
        'fqdn': get_fqdn
    }

    default_master_qdn_getter = get_ip
