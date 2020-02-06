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


from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot import interfaces
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.properties import Property
from buildbot.test.fake import docker
from buildbot.test.fake import fakemaster
from buildbot.test.util.misc import TestReactorMixin
from buildbot.worker import docker as dockerworker


class TestDockerLatentWorker(unittest.TestCase, TestReactorMixin):

    @defer.inlineCallbacks
    def setupWorker(self, *args, **kwargs):
        self.patch(dockerworker, 'docker', docker)
        worker = dockerworker.DockerLatentWorker(*args, **kwargs)
        master = fakemaster.make_master(self, wantData=True)
        fakemaster.master = master
        worker.setServiceParent(master)
        yield master.startService()
        self.addCleanup(master.stopService)
        return worker

    def setUp(self):
        self.setUpTestReactor()

        self.build = Properties(
            image='busybox:latest', builder='docker_worker', distro='wheezy')
        self.patch(dockerworker, 'client', docker)

    @defer.inlineCallbacks
    def test_constructor_nodocker(self):
        self.patch(dockerworker, 'client', None)
        with self.assertRaises(config.ConfigErrors):
            yield self.setupWorker('bot', 'pass', 'unix://tmp.sock', 'debian:wheezy', [])

    @defer.inlineCallbacks
    def test_constructor_noimage_nodockerfile(self):
        with self.assertRaises(config.ConfigErrors):
            yield self.setupWorker('bot', 'pass', 'http://localhost:2375')

    @defer.inlineCallbacks
    def test_constructor_noimage_dockerfile(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'http://localhost:2375', dockerfile="FROM ubuntu")
        self.assertEqual(bs.dockerfile, "FROM ubuntu")
        self.assertEqual(bs.image, None)

    @defer.inlineCallbacks
    def test_constructor_image_nodockerfile(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'http://localhost:2375', image="myworker")
        self.assertEqual(bs.dockerfile, None)
        self.assertEqual(bs.image, 'myworker')

    @defer.inlineCallbacks
    def test_constructor_minimal(self):
        # Minimal set of parameters
        bs = yield self.setupWorker('bot', 'pass', 'tcp://1234:2375', 'worker')
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.client_args, {'base_url': 'tcp://1234:2375'})
        self.assertEqual(bs.image, 'worker')
        self.assertEqual(bs.command, [])

    @defer.inlineCallbacks
    def test_contruction_minimal_docker_py(self):
        docker.version = "1.10.6"
        bs = yield self.setupWorker('bot', 'pass', 'tcp://1234:2375', 'worker')
        id, name = yield bs.start_instance(self.build)
        client = docker.APIClient.latest
        self.assertEqual(client.called_class_name, "Client")
        client = docker.Client.latest
        self.assertNotEqual(client.called_class_name, "APIClient")

    @defer.inlineCallbacks
    def test_contruction_minimal_docker(self):
        docker.version = "2.0.0"
        bs = yield self.setupWorker('bot', 'pass', 'tcp://1234:2375', 'worker')
        id, name = yield bs.start_instance(self.build)
        client = docker.Client.latest
        self.assertEqual(client.called_class_name, "APIClient")
        client = docker.APIClient.latest
        self.assertNotEqual(client.called_class_name, "Client")

    @defer.inlineCallbacks
    def test_constructor_nopassword(self):
        # when no password, it is created automatically
        bs = yield self.setupWorker('bot', None, 'tcp://1234:2375', 'worker')
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(len(bs.password), 20)

    @defer.inlineCallbacks
    def test_constructor_all_docker_parameters(self):
        # Volumes have their own tests
        bs = yield self.setupWorker('bot', 'pass', 'unix:///var/run/docker.sock', 'worker_img',
                                    ['/bin/sh'],
                                    dockerfile="FROM ubuntu", version='1.9', tls=True,
                                    hostconfig={'network_mode': 'fake', 'dns': ['1.1.1.1', '1.2.3.4']},
                                    custom_context=False, buildargs=None,
                                    encoding='gzip')
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
        self.assertFalse(bs.custom_context)
        self.assertEqual(bs.buildargs, None)
        self.assertEqual(bs.encoding, 'gzip')

    @defer.inlineCallbacks
    def test_start_instance_volume_renderable(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'],
            volumes=[Interpolate('/data:/worker/%(kw:builder)s/build',
                                 builder=Property('builder'))])
        id, name = yield bs.start_instance(self.build)
        client = docker.Client.latest
        self.assertEqual(len(client.call_args_create_container), 1)
        self.assertEqual(client.call_args_create_container[0]['volumes'],
                         ['/worker/docker_worker/build'])

    @defer.inlineCallbacks
    def test_volume_no_suffix(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'], volumes=['/src/webapp:/opt/webapp'])
        yield bs.start_instance(self.build)
        client = docker.Client.latest
        self.assertEqual(len(client.call_args_create_container), 1)
        self.assertEqual(len(client.call_args_create_host_config), 1)
        self.assertEqual(client.call_args_create_container[0]['volumes'],
                         ['/opt/webapp'])
        self.assertEqual(client.call_args_create_host_config[0]['binds'],
                         ["/src/webapp:/opt/webapp"])

    @defer.inlineCallbacks
    def test_volume_ro_rw(self):
        bs = yield self.setupWorker('bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'],
                                    volumes=['/src/webapp:/opt/webapp:ro',
                                             '~:/backup:rw'])
        yield bs.start_instance(self.build)
        client = docker.Client.latest
        self.assertEqual(len(client.call_args_create_container), 1)
        self.assertEqual(len(client.call_args_create_host_config), 1)
        self.assertEqual(client.call_args_create_container[0]['volumes'],
                         ['/opt/webapp', '/backup'])
        self.assertEqual(client.call_args_create_host_config[0]['binds'],
                         ['/src/webapp:/opt/webapp:ro', '~:/backup:rw'])

    @defer.inlineCallbacks
    def test_volume_bad_format(self):
        with self.assertRaises(config.ConfigErrors):
            yield self.setupWorker('bot', 'pass', 'http://localhost:2375',
                                   image="worker",
                                   volumes=['abcd=efgh'])

    @defer.inlineCallbacks
    def test_volume_bad_format_renderable(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'http://localhost:2375', image="worker",
            volumes=[Interpolate('/data==/worker/%(kw:builder)s/build',
                                 builder=Property('builder'))])
        with self.assertRaises(config.ConfigErrors):
            yield bs.start_instance(self.build)

    @defer.inlineCallbacks
    def test_start_instance_image_no_version(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'busybox', ['bin/bash'])
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'busybox')

    @defer.inlineCallbacks
    def test_start_instance_image_right_version(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'busybox:latest', ['bin/bash'])
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'busybox:latest')

    @defer.inlineCallbacks
    def test_start_instance_image_wrong_version(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'busybox:123', ['bin/bash'])
        with self.assertRaises(interfaces.LatentWorkerCannotSubstantiate):
            yield bs.start_instance(self.build)

    @defer.inlineCallbacks
    def test_start_instance_image_renderable(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', Property('image'), ['bin/bash'])
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'busybox:latest')

    @defer.inlineCallbacks
    def test_start_instance_noimage_nodockerfile(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'customworker', ['bin/bash'])
        with self.assertRaises(interfaces.LatentWorkerCannotSubstantiate):
            yield bs.start_instance(self.build)

    @defer.inlineCallbacks
    def test_start_instance_image_and_dockefile(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'customworker', dockerfile='BUG')
        with self.assertRaises(interfaces.LatentWorkerCannotSubstantiate):
            yield bs.start_instance(self.build)

    @defer.inlineCallbacks
    def test_start_instance_noimage_gooddockerfile(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'customworker', dockerfile='FROM debian:wheezy')
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'customworker')

    @defer.inlineCallbacks
    def test_start_instance_noimage_pull(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'alpine:latest', autopull=True)
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'alpine:latest')

    @defer.inlineCallbacks
    def test_start_instance_image_pull(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'tester:latest', autopull=True)
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'tester:latest')
        client = docker.Client.latest
        self.assertEqual(client._pullCount, 0)

    @defer.inlineCallbacks
    def test_start_instance_image_alwayspull(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'tester:latest', autopull=True, alwaysPull=True)
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'tester:latest')
        client = docker.Client.latest
        self.assertEqual(client._pullCount, 1)

    @defer.inlineCallbacks
    def test_start_instance_image_noauto_alwayspull(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'tester:latest', autopull=False, alwaysPull=True)
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'tester:latest')
        client = docker.Client.latest
        self.assertEqual(client._pullCount, 0)

    @defer.inlineCallbacks
    def test_start_instance_noimage_renderabledockerfile(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'customworker',
            dockerfile=Interpolate('FROM debian:%(kw:distro)s',
                                   distro=Property('distro')))
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'customworker')

    @defer.inlineCallbacks
    def test_start_instance_custom_context_and_buildargs(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'tester:latest',
            dockerfile=Interpolate('FROM debian:latest'), custom_context=True,
            buildargs={'sample_arg1': 'test_val1'})
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'tester:latest')

    @defer.inlineCallbacks
    def test_start_instance_custom_context_no_buildargs(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'tester:latest',
            dockerfile=Interpolate('FROM debian:latest'),
            custom_context=True)
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'tester:latest')

    @defer.inlineCallbacks
    def test_start_instance_buildargs_no_custom_context(self):
        bs = yield self.setupWorker(
            'bot', 'pass', 'tcp://1234:2375', 'tester:latest',
            dockerfile=Interpolate('FROM debian:latest'),
            buildargs={'sample_arg1': 'test_val1'})
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'tester:latest')

    @defer.inlineCallbacks
    def test_start_worker_but_already_created_with_same_name(self):
        bs = yield self.setupWorker(
            'existing', 'pass', 'tcp://1234:2375', 'busybox:latest', ['bin/bash'])
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'busybox:latest')


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
