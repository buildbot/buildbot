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
# Portions Copyright Buildbot Team Members
# Portions Copyright 2014 Longaccess private company

try:
    import moto
    import boto
except ImportError:
    raise ImportError("EC2LatentSlave tests require the 'moto' module; "
                      "try 'pip install moto'")
from buildbot.buildslave import ec2
from twisted.trial import unittest


class TestEC2LatentBuildSlave(unittest.TestCase):

    def botoSetup(self):
        c = boto.connect_ec2()
        c.create_key_pair('latent_buildbot_slave')
        c.create_security_group('latent_buildbot_slave', 'the security group')
        instance = c.run_instances('foo').instances[0]
        ami = c.create_image(instance.id, "foo", "bar")
        return {'ami': ami}

    @moto.mock_ec2
    def test_constructor_minimal(self):
        kwargs = self.botoSetup()
        bs = ec2.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     **kwargs
                                     )
        self.assertEqual(bs.slavename, 'bot1')
        self.assertEqual(bs.password, 'sekrit')
        self.assertEqual(bs.instance_type, 'm1.large')
        self.assertEqual(bs.ami, kwargs['ami'])

    @moto.mock_ec2
    def test_constructor_tags(self):
        kwargs = self.botoSetup()
        tags = {'foo': 'bar'}
        bs = ec2.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     tags=tags,
                                     **kwargs
                                     )
        self.assertEqual(bs.tags, tags)

    @moto.mock_ec2
    def test_start_instance(self):
        kwargs = self.botoSetup()
        bs = ec2.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     **kwargs
                                     )
        bs._start_instance()
