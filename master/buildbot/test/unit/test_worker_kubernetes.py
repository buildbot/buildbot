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

from twisted.internet import threads
from twisted.python import threadpool
from twisted.trial import unittest


from buildbot import config
from buildbot.process.properties import Properties
from buildbot.test.fake import kubernetes as kubeclient
from buildbot.test.fake import fakemaster
from buildbot.test.fake.reactor import NonThreadPool
from buildbot.test.fake.reactor import TestReactor
from buildbot.util.eventual import _setReactor

from buildbot.worker import kubernetes


class TestConfigKubernetesWorker(unittest.TestCase):

    def setupWorker(self, *args, **kwargs):
        worker = kubernetes.KubeLatentWorker(*args, **kwargs)
        master = fakemaster.make_master(testcase=self, wantData=True)
        worker.setServiceParent(master)
        self.successResultOf(master.startService())
        self.addCleanup(master.stopService)
        return worker

    def setUp(self):
        self.kube_config = kube_config = kubeclient.Config()
        self.patch(kubernetes, "kube_config", kube_config)
        self.patch(kubernetes, "client", kube_config._get_fake_client())

    def test_error_config_dependency(self):
        self.patch(kubernetes, "kube_config", None)
        self.patch(kubernetes, "client", None)
        self.assertRaises(config.ConfigErrors,
            self.setupWorker, 'worker_name', 'pass')

    def test_error_config_file_not_found(self):
        def raise_IOError():
            raise IOError()
        self.kube_config._kube_config_file = raise_IOError
        self.assertRaisesRegex(config.ConfigErrors, "No kube-apimaster host provided",
            self.setupWorker, 'worker_name', 'pass')

    def test_error_config_file_invalid_file(self):
        def raise_ConfigException():
            raise self.kube_config.config_exception.ConfigException
        self.kube_config._kube_config_file = raise_ConfigException
        self.assertRaisesRegex(config.ConfigErrors, "No kube-apimaster host provided",
            self.setupWorker, 'worker_name', 'pass')

    def test_error_incluster_novar(self):
        def raise_ConfigException():
            raise self.kube_config.config_exception.ConfigException
        self.kube_config._envvar_cluster = raise_ConfigException
        self.assertRaisesRegex(config.ConfigErrors, "No kube-apimaster host provided",
            self.setupWorker, 'worker_name', 'pass')

    def test_kube_config_file(self):
        self.kube_config._kube_config_file = {'host': 'fake_host'}
        self.setupWorker('worker_name', 'pass')

    def test_kube_incluster(self):
        self.kube_config._envvar_cluster = {'host': 'fake_host'}
        self.setupWorker('worker_name', 'pass')

    def test_kube_config_in_param(self):
        self.setupWorker('worker_name', 'pass', kubeConfig={'host': 'fake_host'})


class TestRunKubernetesWorker(unittest.SynchronousTestCase):

    def setupWorker(self, *args, **kwargs):
        worker = kubernetes.KubeLatentWorker(*args, **kwargs)
        master = fakemaster.make_master(testcase=self, wantData=True)
        worker.setServiceParent(master)
        self.successResultOf(master.startService())
        self.addCleanup(master.stopService)
        return worker

    def setUp(self):
        def deferToThread(f, *args, **kwargs):
            return threads.deferToThreadPool(self.reactor, self.reactor.getThreadPool(),
                f, *args, **kwargs)
        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.patch(threads, 'deferToThread', deferToThread)
        self.reactor = TestReactor()

        _setReactor(self.reactor)

        self.kube_config = kube_config = kubeclient.Config()
        self.patch(kubernetes, "kube_config", kube_config)
        self.patch(kubernetes, "client", kube_config._get_fake_client())
        self.build = Properties(builder='kubernetes_worker')

    def test_start(self):
        bs = self.setupWorker('worker_name', 'pass',
            kubeConfig={'host': 'fake_host'})
        id, name = self.successResultOf(bs.start_instance(self.build))
