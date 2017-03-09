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

from __future__ import absolute_import
from __future__ import print_function

import mock

from twisted.internet import defer
from twisted.trial import unittest

import buildbot.test.fake.openstack as novaclient
from buildbot import config
from buildbot import interfaces
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
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
        self.patch(openstack, "client", novaclient)
        self.patch(openstack, "loading", novaclient)
        self.patch(openstack, "session", novaclient)
        self.build = Properties(image=novaclient.TEST_UUIDS['image'])

    def test_constructor_nonova(self):
        self.patch(openstack, "client", None)
        self.assertRaises(config.ConfigErrors,
                          openstack.OpenStackLatentWorker, 'bot', 'pass',
                          **self.bs_image_args)

    def test_constructor_nokeystoneauth(self):
        self.patch(openstack, "loading", None)
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
        self.assertIsInstance(bs.novaclient, novaclient.Client)

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

    @defer.inlineCallbacks
    def test_constructor_block_devices_get_sizes(self):
        block_devices = [
            {'source_type': 'image', 'uuid': novaclient.TEST_UUIDS['image']},
            {'source_type': 'image', 'uuid': novaclient.TEST_UUIDS['image'], 'volume_size': 4},
            {'source_type': 'volume', 'uuid': novaclient.TEST_UUIDS['volume']},
            {'source_type': 'snapshot', 'uuid': novaclient.TEST_UUIDS['snapshot']},
        ]

        def check_volume_sizes(_images, block_devices):
            self.assertEqual(len(block_devices), 4)
            self.assertEqual(block_devices[0]['volume_size'], 1)
            self.assertIsInstance(block_devices[0]['volume_size'], int,
                                  "Volume size is an integer.")
            self.assertEqual(block_devices[1]['volume_size'], 4)
            self.assertEqual(block_devices[2]['volume_size'], 4)
            self.assertEqual(block_devices[3]['volume_size'], 2)

        lw = openstack.OpenStackLatentWorker('bot', 'pass', flavor=1,
                                             block_devices=block_devices,
                                             **self.os_auth)
        self.assertEqual(lw.image, None)
        self.assertEqual(lw.block_devices, [{'boot_index': 0,
                                             'delete_on_termination': True,
                                             'destination_type': 'volume', 'device_name': 'vda',
                                             'source_type': 'image', 'volume_size': None,
                                             'uuid': novaclient.TEST_UUIDS['image']},
                                            {'boot_index': 0,
                                             'delete_on_termination': True,
                                             'destination_type': 'volume', 'device_name': 'vda',
                                             'source_type': 'image', 'volume_size': 4,
                                             'uuid': novaclient.TEST_UUIDS['image']},
                                            {'boot_index': 0,
                                             'delete_on_termination': True,
                                             'destination_type': 'volume', 'device_name': 'vda',
                                             'source_type': 'volume', 'volume_size': None,
                                             'uuid': novaclient.TEST_UUIDS['volume']},
                                            {'boot_index': 0,
                                             'delete_on_termination': True,
                                             'destination_type': 'volume', 'device_name': 'vda',
                                             'source_type': 'snapshot', 'volume_size': None,
                                             'uuid': novaclient.TEST_UUIDS['snapshot']}])
        self.patch(lw, "_start_instance", check_volume_sizes)
        yield lw.start_instance(self.build)

    @defer.inlineCallbacks
    def test_constructor_block_devices_missing(self):
        block_devices = [
            {'source_type': 'image', 'uuid': '9fb2e6e8-110d-4388-8c23-0fcbd1e2fcc1'},
        ]

        lw = openstack.OpenStackLatentWorker('bot', 'pass', flavor=1,
                                             block_devices=block_devices,
                                             **self.os_auth)
        yield self.assertFailure(lw.start_instance(self.build),
                                 novaclient.NotFound)

    def test_constructor_no_image(self):
        """
        Must have one of image or block_devices specified.
        """
        self.assertRaises(ValueError,
                          openstack.OpenStackLatentWorker, 'bot', 'pass',
                          flavor=1, **self.os_auth)

    @defer.inlineCallbacks
    def test_getImage_string(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        image_uuid = yield bs._getImage(self.build)
        self.assertEqual('image-uuid', image_uuid)

    @defer.inlineCallbacks
    def test_getImage_callable(self):
        def image_callable(images):
            filtered = [i for i in images if i.id == 'uuid1']
            return filtered[0].id

        bs = openstack.OpenStackLatentWorker('bot', 'pass', flavor=1,
                                             image=image_callable, **self.os_auth)
        os_client = bs.novaclient
        os_client.images._add_items([
            novaclient.Image('uuid1', 'name1', 1),
            novaclient.Image('uuid2', 'name2', 1),
            novaclient.Image('uuid3', 'name3', 1),
            ])
        image_uuid = yield bs._getImage(self.build)
        self.assertEqual('uuid1', image_uuid)

    @defer.inlineCallbacks
    def test_getImage_renderable(self):
        bs = openstack.OpenStackLatentWorker('bot', 'pass', flavor=1,
                                             image=Interpolate('%(prop:image)s'),
                                             **self.os_auth)
        image_uuid = yield bs._getImage(self.build)
        self.assertEqual(novaclient.TEST_UUIDS['image'], image_uuid)

    def test_start_instance_already_exists(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs.instance = mock.Mock()
        self.assertFailure(bs.start_instance(self.build), ValueError)

    @defer.inlineCallbacks
    def test_start_instance_first_fetch_fail(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_get', True)
        self.patch(novaclient.Servers, 'gets_until_disappears', 0)
        yield self.assertFailure(bs.start_instance(self.build),
                                 interfaces.LatentWorkerFailedToSubstantiate)

    @defer.inlineCallbacks
    def test_start_instance_fail_to_find(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_get', True)
        yield self.assertFailure(bs.start_instance(self.build),
                                 interfaces.LatentWorkerFailedToSubstantiate)

    @defer.inlineCallbacks
    def test_start_instance_fail_to_start(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_start', True)
        yield self.assertFailure(bs.start_instance(self.build),
                                 interfaces.LatentWorkerFailedToSubstantiate)

    @defer.inlineCallbacks
    def test_start_instance_success(self):
        bs = openstack.OpenStackLatentWorker(
            'bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = yield bs.start_instance(self.build)
        self.assertTrue(uuid)
        self.assertEqual(image_uuid, 'image-uuid')
        self.assertTrue(time_waiting)

    @defer.inlineCallbacks
    def test_start_instance_check_meta(self):
        meta_arg = {'some_key': 'some-value'}
        bs = openstack.OpenStackLatentWorker('bot', 'pass', meta=meta_arg,
                                             **self.bs_image_args)
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = yield bs.start_instance(self.build)
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
