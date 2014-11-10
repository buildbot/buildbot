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

from twisted.trial import unittest

from buildbot import config
from buildbot import interfaces
from buildbot.buildslave import docker as dockerbuildslave
from buildbot.test.fake import docker

class TestDockerLatentBuildSlave(unittest.TestCase):

    class ConcreteBuildSlave(dockerbuildslave.DockerLatentBuildSlave):
        pass

    def setUp(self):
        self.patch(dockerbuildslave, 'client', docker)

    def test_constructor_nodocker(self):
        self.patch(dockerbuildslave, 'client', None)
        self.assertRaises(config.ConfigErrors, self.ConcreteBuildSlave, 'bot', 'pass', 'unix://tmp.sock', 'debian:wheezy', [])

    def test_constructor_noimage(self):
        self.assertRaises(config.ConfigErrors, self.ConcreteBuildSlave, 'bot', 'pass', 'http://localhost:2375')

    def test_constructor_minimal(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'tcp://1234:2375', 'slave', ['bin/bash'])
        self.assertEqual(bs.slavename, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.docker_host, 'tcp://1234:2375')
        self.assertEqual(bs.image, 'slave')
        self.assertEqual(bs.command, ['bin/bash'])

    def test_start_instance_image_no_version(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'tcp://1234:2375', 'busybox', ['bin/bash'])
        id, name = bs._start_instance()
        self.assertEqual(name, 'busybox')

    def test_start_instance_image_right_version(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'tcp://1234:2375', 'busybox:latest', ['bin/bash'])
        id, name = bs._start_instance()
        self.assertEqual(name, 'busybox:latest')

    def test_start_instance_image_wrong_version(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'tcp://1234:2375', 'busybox:previous', ['bin/bash'])
        self.assertRaises(interfaces.LatentBuildSlaveFailedToSubstantiate, bs._start_instance)

    def test_start_instance_noimage_nodockerfile(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'tcp://1234:2375', 'slave', ['bin/bash'])
        self.assertRaises(interfaces.LatentBuildSlaveFailedToSubstantiate, bs._start_instance)

    def test_start_instance_noimage_dockefilefails(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'tcp://1234:2375', 'slave', dockerfile='BUG')
        self.assertRaises(interfaces.LatentBuildSlaveFailedToSubstantiate, bs._start_instance)

    def test_start_instance_noimage_gooddockerfile(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'tcp://1234:2375', 'slave', dockerfile='FROM debian:wheezy')
        id, name = bs._start_instance()
        self.assertEqual(name, 'slave')
