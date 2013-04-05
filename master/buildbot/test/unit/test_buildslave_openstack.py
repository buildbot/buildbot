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
from buildbot import config, interfaces
from buildbot.buildslave import openstack
import buildbot.test.fake.openstack as novaclient

class TestOpenStackBuildSlave(unittest.TestCase):

    def setUp(self):
        self.patch(openstack, "nce", novaclient)
        self.patch(openstack, "client", novaclient)

    def test_constructor_nonova(self):
        self.patch(openstack, "nce", None)
        self.patch(openstack, "client", None)
        self.assertRaises(config.ConfigErrors,
                openstack.OpenStackLatentBuildSlave, 'bot', 'pass', flavor=1,
                image='image', os_username='user', os_password='pass',
                os_tenant_name='tenant', os_auth_url='auth')

    def test_constructor_minimal(self):
        bs = openstack.OpenStackLatentBuildSlave('bot', 'pass', flavor=1,
                image='image', os_username='user', os_password='pass',
                os_tenant_name='tenant', os_auth_url='auth')
        self.assertEqual(bs.slavename, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.flavor, 1)
        self.assertEqual(bs.image, 'image')
        self.assertEqual(bs.os_username, 'user')
        self.assertEqual(bs.os_password, 'pass')
        self.assertEqual(bs.os_tenant_name, 'tenant')
        self.assertEqual(bs.os_auth_url, 'auth')

    def test_getImage_string(self):
        bs = openstack.OpenStackLatentBuildSlave('bot', 'pass', flavor=1,
                image='image-uuid', os_username='user', os_password='pass',
                os_tenant_name='tenant', os_auth_url='auth')
        self.assertEqual('image-uuid', bs._getImage(None))

    def test_getImage_callable(self):
        def image_callable(images):
            return images[0]

        bs = openstack.OpenStackLatentBuildSlave('bot', 'pass', flavor=1,
                image=image_callable, os_username='user', os_password='pass',
                os_tenant_name='tenant', os_auth_url='auth')
        os_client = novaclient.Client('user', 'pass', 'tenant', 'auth')
        os_client.images.images = ['uuid1', 'uuid2', 'uuid2']
        self.assertEqual('uuid1', bs._getImage(os_client))

    def test_start_instance_already_exists(self):
        bs = openstack.OpenStackLatentBuildSlave('bot', 'pass', flavor=1,
                image='image-uuid', os_username='user', os_password='pass',
                os_tenant_name='tenant', os_auth_url='auth')
        bs.instance = mock.Mock()
        self.assertRaises(ValueError, bs.start_instance, None)

    def test_start_instance_fail_to_find(self):
        bs = openstack.OpenStackLatentBuildSlave('bot', 'pass', flavor=1,
                image='image-uuid', os_username='user', os_password='pass',
                os_tenant_name='tenant', os_auth_url='auth')
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_get', True)
        self.assertRaises(interfaces.LatentBuildSlaveFailedToSubstantiate,
                bs._start_instance)

    def test_start_instance_fail_to_start(self):
        bs = openstack.OpenStackLatentBuildSlave('bot', 'pass', flavor=1,
                image='image-uuid', os_username='user', os_password='pass',
                os_tenant_name='tenant', os_auth_url='auth')
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_start', True)
        self.assertRaises(interfaces.LatentBuildSlaveFailedToSubstantiate,
                bs._start_instance)

    def test_start_instance_success(self):
        bs = openstack.OpenStackLatentBuildSlave('bot', 'pass', flavor=1,
                image='image-uuid', os_username='user', os_password='pass',
                os_tenant_name='tenant', os_auth_url='auth')
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = bs._start_instance()
        self.assertTrue(uuid)
        self.assertEqual(image_uuid, 'image-uuid')
        self.assertTrue(time_waiting)

    def test_start_instance_check_meta(self):
        meta_arg = {'some_key': 'some-value'}
        bs = openstack.OpenStackLatentBuildSlave('bot', 'pass', flavor=1,
                image='image-uuid', os_username='user', os_password='pass',
                os_tenant_name='tenant', os_auth_url='auth', meta=meta_arg)
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = bs._start_instance()
        self.assertIn('meta', bs.instance.boot_kwargs)
        self.assertIdentical(bs.instance.boot_kwargs['meta'], meta_arg)
