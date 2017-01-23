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
from __future__ import division
from __future__ import print_function

import math
import time

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.worker import AbstractLatentWorker

try:
    import novaclient.exceptions as nce
    from novaclient import client
    from novaclient.exceptions import NotFound
    _hush_pyflakes = [nce, client]
except ImportError:
    NotFound = Exception
    nce = None
    client = None


ACTIVE = 'ACTIVE'
BUILD = 'BUILD'
DELETED = 'DELETED'
UNKNOWN = 'UNKNOWN'


class OpenStackLatentWorker(AbstractLatentWorker):

    instance = None
    _poll_resolution = 5  # hook point for tests

    def __init__(self, name, password,
                 flavor,
                 os_username,
                 os_password,
                 os_tenant_name,
                 os_auth_url,
                 block_devices=None,
                 image=None,
                 meta=None,
                 # Have a nova_args parameter to allow passing things directly
                 # to novaclient.
                 nova_args=None,
                 client_version='1.1',
                 **kwargs):

        if not client or not nce:
            config.error("The python module 'novaclient' is needed  "
                         "to use a OpenStackLatentWorker. "
                         "Please install 'python-novaclient' package.")

        if not block_devices and not image:
            raise ValueError('One of block_devices or image must be given')

        AbstractLatentWorker.__init__(self, name, password, **kwargs)

        self.flavor = flavor
        self.client_version = client_version
        self.novaclient = client.Client(client_version, os_username,
                                        os_password, os_tenant_name,
                                        os_auth_url)

        if block_devices is not None:
            self.block_devices = [
                self._parseBlockDevice(bd) for bd in block_devices]
        else:
            self.block_devices = None
        self.image = image
        self.meta = meta
        self.nova_args = nova_args if nova_args is not None else {}

    def _parseBlockDevice(self, block_device):
        """
        Parse a higher-level view of the block device mapping into something
        novaclient wants. This should be similar to how Horizon presents it.
        Required keys:
            device_name: The name of the device; e.g. vda or xda.
            source_type: image, snapshot, volume, or blank/None.
            destination_type: Destination of block device: volume or local.
            delete_on_termination: True/False.
            uuid: The image, snapshot, or volume id.
            boot_index: Integer used for boot order.
            volume_size: Size of the device in GiB.
        """
        client_block_device = {}
        client_block_device['device_name'] = block_device.get(
            'device_name', 'vda')
        client_block_device['source_type'] = block_device.get(
            'source_type', 'image')
        client_block_device['destination_type'] = block_device.get(
            'destination_type', 'volume')
        client_block_device['delete_on_termination'] = bool(
            block_device.get('delete_on_termination', True))
        client_block_device['uuid'] = block_device['uuid']
        client_block_device['boot_index'] = int(
            block_device.get('boot_index', 0))
        # Allow None here. It will be rendered later.
        client_block_device['volume_size'] = block_device.get('volume_size')
        return client_block_device

    @defer.inlineCallbacks
    def _renderBlockDevice(self, block_device, build):
        """Render all of the block device's values."""
        rendered_block_device = yield build.render(block_device)
        if rendered_block_device['volume_size'] is None:
            source_type = rendered_block_device['source_type']
            source_uuid = rendered_block_device['uuid']
            volume_size = self._determineVolumeSize(source_type, source_uuid)
            rendered_block_device['volume_size'] = volume_size
        defer.returnValue(rendered_block_device)

    def _determineVolumeSize(self, source_type, source_uuid):
        """
        Determine the minimum size the volume needs to be for the source.
        Returns the size in GiB.
        """
        nova = self.novaclient
        if source_type == 'image':
            # The size returned for an image is in bytes. Round up to the next
            # integer GiB.
            image = nova.images.get(source_uuid)
            if hasattr(image, 'OS-EXT-IMG-SIZE:size'):
                size = getattr(image, 'OS-EXT-IMG-SIZE:size')
                size_gb = int(math.ceil(size / 1024.0**3))
                return size_gb
        elif source_type == 'volume':
            # Volumes are easy because they are already in GiB.
            volume = nova.volumes.get(source_uuid)
            return volume.size
        elif source_type == 'snapshot':
            snap = nova.volume_snapshots.get(source_uuid)
            return snap.size
        else:
            unknown_source = ("The source type '%s' for UUID '%s' is"
                              " unknown" % (source_type, source_uuid))
            raise ValueError(unknown_source)

    @defer.inlineCallbacks
    def _getImage(self, build):
        # If image is a callable, then pass it the list of images. The
        # function should return the image's UUID to use.
        image = self.image
        if callable(image):
            image_uuid = image(self.novaclient.images.list())
        else:
            image_uuid = yield build.render(image)
        defer.returnValue(image_uuid)

    @defer.inlineCallbacks
    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')
        image = yield self._getImage(build)
        if self.block_devices is not None:
            block_devices = []
            for bd in self.block_devices:
                rendered_block_device = yield self._renderBlockDevice(bd, build)
                block_devices.append(rendered_block_device)
        else:
            block_devices = None
        res = yield threads.deferToThread(self._start_instance, image,
                                          block_devices)
        defer.returnValue(res)

    def _start_instance(self, image_uuid, block_devices):
        boot_args = [self.workername, image_uuid, self.flavor]
        boot_kwargs = dict(
            meta=self.meta,
            block_device_mapping_v2=block_devices,
            **self.nova_args)
        instance = self.novaclient.servers.create(*boot_args, **boot_kwargs)
        self.instance = instance
        log.msg('%s %s starting instance %s (image %s)' %
                (self.__class__.__name__, self.workername, instance.id,
                 image_uuid))
        duration = 0
        interval = self._poll_resolution
        inst = instance
        while inst.status.startswith(BUILD):
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg('%s %s has waited %d minutes for instance %s' %
                        (self.__class__.__name__, self.workername, duration // 60,
                         instance.id))
            try:
                inst = self.novaclient.servers.get(instance.id)
            except NotFound:
                log.msg('%s %s instance %s (%s) went missing' %
                        (self.__class__.__name__, self.workername,
                         instance.id, instance.name))
                raise LatentWorkerFailedToSubstantiate(
                    instance.id, instance.status)
        if inst.status == ACTIVE:
            minutes = duration // 60
            seconds = duration % 60
            log.msg('%s %s instance %s (%s) started '
                    'in about %d minutes %d seconds' %
                    (self.__class__.__name__, self.workername,
                     instance.id, instance.name, minutes, seconds))
            return [instance.id, image_uuid,
                    '%02d:%02d:%02d' % (minutes // 60, minutes % 60, seconds)]
        else:
            self.failed_to_start(instance.id, inst.status)

    def stop_instance(self, fast=False):
        if self.instance is None:
            # be gentle.  Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        instance = self.instance
        self.instance = None
        self._stop_instance(instance, fast)

    def _stop_instance(self, instance, fast):
        # When the update method does work, replace the lines like below with
        # instance.update().
        try:
            inst = self.novaclient.servers.get(instance.id)
        except NotFound:
            # If can't find the instance, then it's already gone.
            log.msg('%s %s instance %s (%s) already terminated' %
                    (self.__class__.__name__, self.workername, instance.id,
                     instance.name))
            return
        if inst.status not in (DELETED, UNKNOWN):
            inst.delete()
            log.msg('%s %s terminating instance %s (%s)' %
                    (self.__class__.__name__, self.workername, instance.id,
                     instance.name))
