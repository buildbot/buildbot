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
from buildbot import interfaces
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.properties import Property
from buildbot.test.fake import docker
from buildbot.test.fake import fakemaster
from buildbot.test.fake.reactor import NonThreadPool
from buildbot.test.fake.reactor import TestReactor
from buildbot.util.eventual import _setReactor
from buildbot.worker import docker as dockerworker


class TestDockerLatentWorker(unittest.SynchronousTestCase):

    def setupWorker(self, *args, **kwargs):
        self.patch(dockerworker, 'docker', docker)
        worker = dockerworker.DockerLatentWorker(*args, **kwargs)
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
        self.build = Properties(
            image='busybox:latest', builder='docker_worker', distro='wheezy')
        self.patch(dockerworker, 'client', docker)

    def test_constructor_nodocker(self):
        self.patch(dockerworker, 'client', None)
        self.assertRaises(config.ConfigErrors, self.setupWorker,
                          'bot', 'pass', 'unix://tmp.sock', 'debian:wheezy', [])

    def test_constructor_noimage_nodockerfile(self):
        self.assertRaises(
            config.ConfigErrors, self.setupWorker, 'bot', 'pass', 'http://localhost:2375')

    def test_constructor_noimage_dockerfile(self):
        bs = self.setupWorker(
            'bot', 'pass', 'http://localhost:2375', dockerfile="FROM ubuntu")
        self.assertEqual(bs.dockerfile, "FROM ubuntu")
        self.assertEqual(bs.image, None)

    def test_constructor_image_nodockerfile(self):
        bs = self.setupWorker(
            'bot', 'pass', 'http://localhost:2375', image="myworker")
        self.assertEqual(bs.dockerfile, None)
        self.assertEqual(bs.image, 'myworker')

    def test_constructor_minimal(self):
        # Minimal set of parameters
        bs = self.setupWorker('bot', 'pass', 'tcp://1234:2375', 'worker')
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.client_args, {'base_url': 'tcp://1234:2375'})
        self.assertEqual(bs.image, 'worker')
        self.assertEqual(bs.command, [])

    def test_contruction_minimal_docker_py(self):
        docker.version = "1.10.6"
        bs = self.setupWorker('bot', 'pass', 'tcp://1234:2375', 'worker')
        id, name = self.successResultOf(bs.start_instance(self.build))
        client = docker.APIClient.latest
        self.assertEqual(client.called_class_name, "Client")
        client = docker.Client.latest
        self.assertNotEqual(client.called_class_name, "APIClient")

    def test_contruction_minimal_docker(self):
        docker.version = "2.0.0"
        bs = self.setupWorker('bot', 'pass', 'tcp://1234:2375', 'worker')
        id, name = self.successResultOf(bs.start_instance(self.build))
        client = docker.Client.latest
        self.assertEqual(client.called_class_name, "APIClient")
        client = docker.APIClient.latest
        self.assertNotEqual(client.called_class_name, "Client")

    def test_constructor_nopassword(self):
        # when no password, it is created automatically
        bs = self.setupWorker('bot', None, 'tcp://1234:2375', 'worker')
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(len(bs.password), 20)

    def test_constructor_all_docker_parameters(self):
        # Volumes have their own tests
        bs = self.setupWorker('bot', 'pass', 'unix:///var/run/docker.sock', 'worker_img', ['/bin/sh'],
                              dockerfile="FROM ubuntu", version='1.9', tls=True,
                              hostconfig={'network_mode': 'fake', 'dns': ['1.1.1.1', '1.2.3.4']})
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.image, 'worker_img')
        self.assertEqual(bs.command, ['/bin/sh'])
        self.assertEqual(bs.dockerfile, "FROM ubuntu")
        self.assertEqual(bs.volumes, [])
        self.assertEqual(bs.client_args, {
                         'base_url': 'unix:///var/run/docker.sock', 'version': '1.9', 'tls': True})
        self.assertEqual(
            bs.hostconfig, {'network_mode': 'fake', 'dns': ['1.1.1.1', '1.2.3.4']})

    def test_start_instance_volume_renderable(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'],
            volumes=[Interpolate('/data:/worker/%(kw:builder)s/build',
                                 builder=Property('builder'))])
        id, name = self.successResultOf(bs.start_instance(self.build))
        client = docker.Client.latest
        self.assertEqual(len(client.call_args_create_container), 1)
        self.assertEqual(client.call_args_create_container[0]['volumes'],
                         ['/worker/docker_worker/build'])

    def test_volume_no_suffix(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'], volumes=['/src/webapp:/opt/webapp'])
        self.successResultOf(bs.start_instance(self.build))
        client = docker.Client.latest
        self.assertEqual(len(client.call_args_create_container), 1)
        self.assertEqual(len(client.call_args_create_host_config), 1)
        self.assertEqual(client.call_args_create_container[0]['volumes'],
                         ['/opt/webapp'])
        self.assertEqual(client.call_args_create_host_config[0]['binds'],
                         {'/src/webapp': {'bind': '/opt/webapp', 'ro': False}})

    def test_volume_ro_rw(self):
        bs = self.setupWorker('bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'],
                              volumes=['/src/webapp:/opt/webapp:ro',
                                       '~:/backup:rw'])
        self.successResultOf(bs.start_instance(self.build))
        client = docker.Client.latest
        self.assertEqual(len(client.call_args_create_container), 1)
        self.assertEqual(len(client.call_args_create_host_config), 1)
        self.assertEqual(client.call_args_create_container[0]['volumes'],
                         ['/opt/webapp', '/backup'])
        self.assertEqual(client.call_args_create_host_config[0]['binds'],
                         {'/src/webapp': {'bind': '/opt/webapp', 'ro': True},
                          '~': {'bind': '/backup', 'ro': False}})

    def test_volume_bad_format(self):
        self.assertRaises(config.ConfigErrors, self.setupWorker, 'bot', 'pass', 'http://localhost:2375',
                          image="worker",
                          volumes=['abcd=efgh'])

    def test_volume_bad_format_renderable(self):
        bs = self.setupWorker(
            'bot', 'pass', 'http://localhost:2375', image="worker",
            volumes=[Interpolate('/data==/worker/%(kw:builder)s/build',
                                 builder=Property('builder'))])
        f = self.failureResultOf(bs.start_instance(self.build))
        f.check(config.ConfigErrors)

    def test_start_instance_image_no_version(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'busybox', ['bin/bash'])
        id, name = self.successResultOf(bs.start_instance(self.build))
        self.assertEqual(name, 'busybox')

    def test_start_instance_image_right_version(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'busybox:latest', ['bin/bash'])
        id, name = self.successResultOf(bs.start_instance(self.build))
        self.assertEqual(name, 'busybox:latest')

    def test_start_instance_image_wrong_version(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'busybox:123', ['bin/bash'])
        f = self.failureResultOf(bs.start_instance(self.build))
        f.check(interfaces.LatentWorkerFailedToSubstantiate)

    def test_start_instance_image_renderable(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', Property('image'), ['bin/bash'])
        id, name = self.successResultOf(bs.start_instance(self.build))
        self.assertEqual(name, 'busybox:latest')

    def test_start_instance_noimage_nodockerfile(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'customworker', ['bin/bash'])
        f = self.failureResultOf(bs.start_instance(self.build))
        f.check(interfaces.LatentWorkerFailedToSubstantiate)

    def test_start_instance_image_and_dockefile(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'customworker', dockerfile='BUG')
        f = self.failureResultOf(bs.start_instance(self.build))
        f.check(interfaces.LatentWorkerFailedToSubstantiate)

    def test_start_instance_noimage_gooddockerfile(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'customworker', dockerfile='FROM debian:wheezy')
        id, name = self.successResultOf(bs.start_instance(self.build))
        self.assertEqual(name, 'customworker')

    def test_start_instance_noimage_renderabledockerfile(self):
        bs = self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'customworker',
            dockerfile=Interpolate('FROM debian:%(kw:distro)s',
                                   distro=Property('distro')))
        id, name = self.successResultOf(bs.start_instance(self.build))
        self.assertEqual(name, 'customworker')


class testDockerPyStreamLogs(unittest.TestCase):

    def compare(self, result, log):
        self.assertEqual(result,
                         list(dockerworker._handle_stream_line(log)))

    def testEmpty(self):
        self.compare([], '{"stream":"\\n"}\r\n')

    def testOneLine(self):
        self.compare(
            [" ---> Using cache"], '{"stream":" ---\\u003e Using cache\\n"}\r\n')

    def testMultipleLines(self):
        self.compare(["Fetched 8298 kB in 3s (2096 kB/s)", "Reading package lists..."],
                     '{"stream":"Fetched 8298 kB in 3s (2096 kB/s)\\nReading package lists..."}\r\n')

    def testError(self):
        self.compare(["ERROR: The command [/bin/sh -c apt-get update && apt-get install -y"
                      "    python-dev    python-pip] returned a non-zero code: 127"],
                     '{"errorDetail": {"message": "The command [/bin/sh -c apt-get update && '
                     'apt-get install -y    python-dev    python-pip] returned a non-zero code: 127"},'
                     ' "error": "The command [/bin/sh -c apt-get update && apt-get install -y'
                     '    python-dev    python-pip] returned a non-zero code: 127"}\r\n')
