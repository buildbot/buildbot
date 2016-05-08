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
import time

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.worker.base import AbstractLatentWorker

try:
    import novaclient.exceptions as nce
    from novaclient import client
    _hush_pyflakes = [nce, client]
except ImportError:
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
                 # to novaclient v1.1.
                 nova_args=None,
                 client_version='1.1',
                 **kwargs):

        if not client or not nce:
            config.error("The python module 'novaclient' is needed  "
                         "to use a OpenStackLatentWorker")

        if not block_devices and not image:
            raise ValueError('One of block_devices or image must be given')

        AbstractLatentWorker.__init__(self, name, password, **kwargs)

        self.flavor = flavor
        self.os_username = os_username
        self.os_password = os_password
        self.os_tenant_name = os_tenant_name
        self.os_auth_url = os_auth_url
        self.client_version = client_version

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
        client_block_device['volume_size'] = block_device['volume_size']
        return client_block_device

    @staticmethod
    def _getImage(os_client, image):
        # If image is a callable, then pass it the list of images. The
        # function should return the image's UUID to use.
        if callable(image):
            image_uuid = image(os_client.images.list())
        else:
            image_uuid = image
        return image_uuid

    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')
        return threads.deferToThread(self._start_instance)

    def _start_instance(self):
        # Authenticate to OpenStack.
        os_client = client.Client(self.client_version, self.os_username, self.os_password,
                                  self.os_tenant_name, self.os_auth_url)
        image_uuid = self._getImage(os_client, self.image)
        boot_args = [self.workername, image_uuid, self.flavor]
        boot_kwargs = dict(
            meta=self.meta,
            block_device_mapping_v2=self.block_devices,
            **self.nova_args)
        instance = os_client.servers.create(*boot_args, **boot_kwargs)
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
                inst = os_client.servers.get(instance.id)
            except nce.NotFound:
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
        # Authenticate to OpenStack. This is needed since it seems the update
        # method doesn't do a whole lot of updating right now.
        os_client = client.Client(self.client_version, self.os_username, self.os_password,
                                  self.os_tenant_name, self.os_auth_url)
        # When the update method does work, replace the lines like below with
        # instance.update().
        try:
            inst = os_client.servers.get(instance.id)
        except nce.NotFound:
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
