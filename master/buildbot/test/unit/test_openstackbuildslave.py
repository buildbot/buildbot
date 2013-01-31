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
# Portions Copyright 2013 Cray Inc.

import mock
from twisted.trial import unittest
from twisted.internet import defer, reactor, utils
from twisted.python import failure
from buildbot import config, interfaces, openstackbuildslave
from buildbot.test.fake import openstack
from buildbot.test.util import compat

class TestOpenStackBuildSlave(unittest.TestCase):

    class ConcreteBuildSlave(openstackbuildslave.OpenStackLatentBuildSlave):
        pass

    def setUp(self):
        self.patch(openstackbuildslave, "nce", openstack)
        self.patch(openstackbuildslave, "client", openstack)

    def test_constructor_nonova(self):
        self.patch(openstackbuildslave, "nce", None)
        self.patch(openstackbuildslave, "client", None)
        self.assertRaises(config.ConfigErrors, self.ConcreteBuildSlave,
            'bot', 'pass', 'flavor', 'image', 'user', 'pass', 'tenant', 'auth')

    def test_constructor_minimal(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'flavor', 'image', 'user',
                'pass', 'tenant', 'auth')
        yield bs._find_existing_deferred
        self.assertEqual(bs.slavename, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.flavor, 'flavor')
        self.assertEqual(bs.image, 'image')
        self.assertEqual(bs.os_username, 'user')
        self.assertEqual(bs.os_password, 'pass')
        self.assertEqual(bs.os_tenant_name, 'tenant')
        self.assertEqual(bs.os_auth_url, 'auth')

    def test_get_image_string(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'flavor', 'image-uuid',
                'user', 'pass', 'tenant', 'auth')
        self.assertEqual('image-uuid', bs._get_image(None))

    def test_get_image_callable(self):
        def image_callable(images):
            return images[0]

        bs = self.ConcreteBuildSlave('bot', 'pass', 'flavor', image_callable,
                'user', 'pass', 'tenant', 'auth')
        os_client = openstack.Client('user', 'pass', 'tenant', 'auth')
        os_client.images.images = ['uuid1', 'uuid2', 'uuid2']
        self.assertEqual('uuid1', bs._get_image(os_client))

    def test_start_instance_already_exists(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'flavor', 'image-uuid',
                'user', 'pass', 'tenant', 'auth')
        bs.instance = mock.Mock()
        self.assertRaises(ValueError, bs.start_instance, None)

    def test_start_instance_fail_to_find(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'flavor', 'image-uuid',
                'user', 'pass', 'tenant', 'auth')
        bs._poll_resolution = 0
        self.patch(openstack.Servers, 'fail_to_get', True)
        self.assertRaises(interfaces.LatentBuildSlaveFailedToSubstantiate,
                bs._start_instance)

    def test_start_instance_fail_to_start(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'flavor', 'image-uuid',
                'user', 'pass', 'tenant', 'auth')
        bs._poll_resolution = 0
        self.patch(openstack.Servers, 'fail_to_start', True)
        self.assertRaises(interfaces.LatentBuildSlaveFailedToSubstantiate,
                bs._start_instance)

    def test_start_instance_success(self):
        bs = self.ConcreteBuildSlave('bot', 'pass', 'flavor', 'image-uuid',
                'user', 'pass', 'tenant', 'auth')
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = bs._start_instance()
        self.assertTrue(uuid)
        self.assertEqual(image_uuid, 'image-uuid')
        self.assertTrue(time_waiting)

    def test_start_instance_check_meta(self):
        meta_arg = {'some_key': 'some-value'}
        bs = self.ConcreteBuildSlave('bot', 'pass', 'flavor', 'image-uuid',
                'user', 'pass', 'tenant', 'auth', meta=meta_arg)
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = bs._start_instance()
        self.assertIn('meta', bs.instance.boot_kwargs)
        self.assertIdentical(bs.instance.boot_kwargs['meta'], meta_arg)
