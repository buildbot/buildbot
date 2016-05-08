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
from twisted.internet import defer
from twisted.trial import unittest

import buildbot.test.fake.openstack as novaclient
from buildbot import config
from buildbot import interfaces
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker import openstack
from buildbot.worker_transition import DeprecatedWorkerNameWarning


class TestOpenStackWorker(unittest.TestCase):
    os_auth = dict(
        os_username='user',
        os_password='pass',
        os_tenant_name='tenant',
        os_auth_url='auth')
    bs_image_args = dict(
        flavor=1,
        image='image-uuid',
        **os_auth)

    def setUp(self):
        self.patch(openstack, "nce", novaclient)
        self.patch(openstack, "client", novaclient)

    def test_constructor_nonova(self):
        self.patch(openstack, "nce", None)
        self.patch(openstack, "client", None)
        self.assertRaises(config.ConfigErrors,
                          openstack.OpenStackLatentWorker, 'bot', 'pass',
                          **self.bs_image_args)

    def test_constructor_minimal(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.flavor, 1)
        self.assertEqual(bs.image, 'image-uuid')
        self.assertEqual(bs.block_devices, None)
        self.assertEqual(bs.os_username, 'user')
        self.assertEqual(bs.os_password, 'pass')
        self.assertEqual(bs.os_tenant_name, 'tenant')
        self.assertEqual(bs.os_auth_url, 'auth')

    def test_constructor_block_devices_default(self):
        block_devices = [{'uuid': 'uuid', 'volume_size': 10}]
        bs = openstack.OpenStackLatentWorker('bot', 'pass', flavor=1,
                                             block_devices=block_devices,
                                             **self.os_auth)
        self.assertEqual(bs.image, None)
        self.assertEqual(len(bs.block_devices), 1)
        self.assertEqual(bs.block_devices, [{'boot_index': 0,
                                             'delete_on_termination': True,
                                             'destination_type': 'volume', 'device_name': 'vda',
                                             'source_type': 'image', 'volume_size': 10, 'uuid': 'uuid'}])

    def test_constructor_no_image(self):
        """
        Must have one of image or block_devices specified.
        """
        self.assertRaises(ValueError,
                          openstack.OpenStackLatentWorker, 'bot', 'pass',
                          flavor=1, **self.os_auth)

    def test_getImage_string(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        self.assertEqual('image-uuid', bs._getImage(None, bs.image))

    def test_getImage_callable(self):
        def image_callable(images):
            return images[0]

        bs = openstack.OpenStackLatentWorker('bot', 'pass', flavor=1,
                                             image=image_callable, **self.os_auth)
        os_client = novaclient.Client('1.1', 'user', 'pass', 'tenant', 'auth')
        os_client.images.images = ['uuid1', 'uuid2', 'uuid2']
        self.assertEqual('uuid1', bs._getImage(os_client, image_callable))

    def test_start_instance_already_exists(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs.instance = mock.Mock()
        self.assertRaises(ValueError, bs.start_instance, None)

    def test_start_instance_fail_to_find(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_get', True)
        self.assertRaises(interfaces.LatentWorkerFailedToSubstantiate,
                          bs._start_instance)

    def test_start_instance_fail_to_start(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_start', True)
        self.assertRaises(interfaces.LatentWorkerFailedToSubstantiate,
                          bs._start_instance)

    def test_start_instance_success(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = bs._start_instance()
        self.assertTrue(uuid)
        self.assertEqual(image_uuid, 'image-uuid')
        self.assertTrue(time_waiting)

    def test_start_instance_check_meta(self):
        meta_arg = {'some_key': 'some-value'}
        bs = openstack.OpenStackLatentWorker('bot', 'pass', meta=meta_arg,
                                             **self.bs_image_args)
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = bs._start_instance()
        self.assertIn('meta', bs.instance.boot_kwargs)
        self.assertIdentical(bs.instance.boot_kwargs['meta'], meta_arg)

    @defer.inlineCallbacks
    def test_stop_instance_not_set(self):
        """
        Test stopping the instance but with no instance to stop.
        """
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs.instance = None
        stopped = yield bs.stop_instance()
        self.assertEqual(stopped, None)

    def test_stop_instance_missing(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        instance = mock.Mock()
        instance.id = 'uuid'
        bs.instance = instance
        # TODO: Check log for instance not found.
        bs.stop_instance()

    def test_stop_instance_fast(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        # Make instance immediately active.
        self.patch(novaclient.Servers, 'gets_until_active', 0)
        s = novaclient.Servers()
        bs.instance = inst = s.create()
        self.assertIn(inst.id, s.instances)
        bs.stop_instance(fast=True)
        self.assertNotIn(inst.id, s.instances)

    def test_stop_instance_notfast(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        # Make instance immediately active.
        self.patch(novaclient.Servers, 'gets_until_active', 0)
        s = novaclient.Servers()
        bs.instance = inst = s.create()
        self.assertIn(inst.id, s.instances)
        bs.stop_instance(fast=False)
        self.assertNotIn(inst.id, s.instances)

    def test_stop_instance_unknown(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        # Make instance immediately active.
        self.patch(novaclient.Servers, 'gets_until_active', 0)
        s = novaclient.Servers()
        bs.instance = inst = s.create()
        # Set status to DELETED. Instance should not be deleted when shutting
        # down as it already is.
        inst.status = novaclient.DELETED
        self.assertIn(inst.id, s.instances)
        bs.stop_instance()
        self.assertIn(inst.id, s.instances)


class TestWorkerTransition(unittest.TestCase):

    def test_OpenStackLatentBuildSlave_deprecated(self):
        from buildbot.worker.openstack import OpenStackLatentWorker

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="OpenStackLatentBuildSlave was deprecated"):
            from buildbot.buildslave.openstack import OpenStackLatentBuildSlave

        self.assertIdentical(OpenStackLatentBuildSlave, OpenStackLatentWorker)
