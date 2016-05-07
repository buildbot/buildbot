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
from buildbot.worker import docker as dockerworker


class TestDockerLatentWorker(unittest.TestCase):

    class ConcreteWorker(dockerworker.DockerLatentWorker):
        pass

    def setUp(self):
        self.build = Properties(
            image="busybox:latest", builder="docker_worker")
        self.patch(dockerworker, 'client', docker)

    def test_constructor_nodocker(self):
        self.patch(dockerworker, 'client', None)
        self.assertRaises(config.ConfigErrors, self.ConcreteWorker,
                          'bot', 'pass', 'unix://tmp.sock', 'debian:wheezy', [])

    def test_constructor_noimage_nodockerfile(self):
        self.assertRaises(
            config.ConfigErrors, self.ConcreteWorker, 'bot', 'pass', 'http://localhost:2375')

    def test_constructor_noimage_dockerfile(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'http://localhost:2375', dockerfile="FROM ubuntu")
        self.assertEqual(bs.dockerfile, "FROM ubuntu")
        self.assertEqual(bs.image, None)

    def test_constructor_image_nodockerfile(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'http://localhost:2375', image="myworker")
        self.assertEqual(bs.dockerfile, None)
        self.assertEqual(bs.image, 'myworker')

    def test_constructor_networking_config(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'http://localhost:2375', 'worker', networking_config='host')
        self.assertEqual(bs.networking_config, 'host')

    def test_constructor_minimal(self):
        # Minimal set of parameters
        bs = self.ConcreteWorker('bot', 'pass', 'tcp://1234:2375', 'worker')
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.client_args, {'base_url': 'tcp://1234:2375'})
        self.assertEqual(bs.image, 'worker')
        self.assertEqual(bs.command, [])

    def test_constructor_all_docker_parameters(self):
        # Volumes have their own tests
        bs = self.ConcreteWorker('bot', 'pass', 'unix:///var/run/docker.sock', 'worker_img', ['/bin/sh'],
                                 dockerfile="FROM ubuntu", version='1.9', tls=True,
                                 hostconfig={'network_mode': 'fake', 'dns': ['1.1.1.1', '1.2.3.4']})
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.image, 'worker_img')
        self.assertEqual(bs.command, ['/bin/sh'])
        self.assertEqual(bs.dockerfile, "FROM ubuntu")
        self.assertEqual(bs.volumes, [])
        self.assertEqual(bs.binds, {})
        self.assertEqual(bs.client_args, {
                         'base_url': 'unix:///var/run/docker.sock', 'version': '1.9', 'tls': True})
        self.assertEqual(
            bs.hostconfig, {'network_mode': 'fake', 'dns': ['1.1.1.1', '1.2.3.4']})

    @defer.inlineCallbacks
    def test_start_instance_volume_renderable(self):
        bs = self.ConcreteWorker('bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'],
                                 volumes=[Interpolate('/data:/buildslave/%(kw:builder)s/build', builder=Property('builder'))])
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(bs.volumes, ['/data:/buildslave/docker_worker/build'])

    @defer.inlineCallbacks
    def test_volume_no_suffix(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'], volumes=['/src/webapp:/opt/webapp'])
        yield bs.start_instance(self.build)
        self.assertEqual(bs.volumes, ['/src/webapp:/opt/webapp'])
        self.assertEqual(
            bs.binds, {'/src/webapp': {'bind': '/opt/webapp', 'ro': False}})

    @defer.inlineCallbacks
    def test_volume_ro_rw(self):
        bs = self.ConcreteWorker('bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'],
                                 volumes=['/src/webapp:/opt/webapp:ro',
                                          '~:/backup:rw'])
        yield bs.start_instance(self.build)
        self.assertEqual(
            bs.volumes, ['/src/webapp:/opt/webapp:ro', '~:/backup:rw'])
        self.assertEqual(bs.binds, {'/src/webapp': {'bind': '/opt/webapp', 'ro': True},
                                    '~': {'bind': '/backup', 'ro': False}})

    def test_volume_bad_format(self):
        self.assertRaises(config.ConfigErrors, self.ConcreteWorker, 'bot', 'pass', 'http://localhost:2375', image="worker",
                          volumes=['abcd=efgh'])

    @defer.inlineCallbacks
    def test_volume_bad_format_renderable(self):
        bs = self.ConcreteWorker('bot', 'pass', 'http://localhost:2375', image="worker",
                                 volumes=[Interpolate('/data==/buildslave/%(kw:builder)s/build', builder=Property('builder'))])
        yield self.assertRaises(AttributeError, bs.start_instance(self.build))

    @defer.inlineCallbacks
    def test_start_instance_image_no_version(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'tcp://1234:2375', 'busybox', ['bin/bash'])
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'busybox')

    @defer.inlineCallbacks
    def test_start_instance_image_right_version(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'tcp://1234:2375', 'busybox:latest', ['bin/bash'])
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'busybox:latest')

    @defer.inlineCallbacks
    def test_start_instance_image_wrong_version(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'tcp://1234:2375', 'busybox:123', ['bin/bash'])
        yield self.assertFailure(bs.start_instance(self.build),
                                 interfaces.LatentWorkerFailedToSubstantiate)

    @defer.inlineCallbacks
    def test_start_instance_image_renderable(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'tcp://1234:2375', Property('image'), ['bin/bash'])
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'busybox:latest')

    @defer.inlineCallbacks
    def test_start_instance_noimage_nodockerfile(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'tcp://1234:2375', 'worker', ['bin/bash'])
        try:
            id, name = yield bs.start_instance(self.build)
        except interfaces.LatentWorkerFailedToSubstantiate:
            pass

    @defer.inlineCallbacks
    def test_start_instance_noimage_dockefilefails(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'tcp://1234:2375', 'worker', dockerfile='BUG')
        try:
            id, name = yield bs.start_instance(self.build)
        except interfaces.LatentWorkerFailedToSubstantiate:
            pass

    @defer.inlineCallbacks
    def test_start_instance_noimage_gooddockerfile(self):
        bs = self.ConcreteWorker(
            'bot', 'pass', 'tcp://1234:2375', 'worker', dockerfile='FROM debian:wheezy')
        id, name = yield bs.start_instance(self.build)
        self.assertEqual(name, 'worker')


class testDockerPyStreamLogs(unittest.TestCase):

    def compare(self, result, log):
        self.assertEquals(result,
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
        self.compare(["ERROR: The command [/bin/sh -c apt-get update && apt-get install -y    python-dev    python-pip] returned a non-zero code: 127"],
                     '{"errorDetail": {"message": "The command [/bin/sh -c apt-get update && apt-get install -y    python-dev    python-pip] returned a non-zero code: 127"}, "error": "The command [/bin/sh -c apt-get update && apt-get install -y    python-dev    python-pip] returned a non-zero code: 127"}\r\n')
