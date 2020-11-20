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


import math
import time

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util.latent import CompatibleLatentWorkerMixin
from buildbot.worker import AbstractLatentWorker

try:
    from keystoneauth1 import loading
    from keystoneauth1 import session
    from novaclient import client
    from novaclient.exceptions import NotFound
    _hush_pyflakes = [client]
except ImportError:
    NotFound = Exception
    client = None
    loading = None
    session = None


ACTIVE = 'ACTIVE'
BUILD = 'BUILD'
DELETED = 'DELETED'
UNKNOWN = 'UNKNOWN'


class OpenStackLatentWorker(CompatibleLatentWorkerMixin,
                            AbstractLatentWorker):

    instance = None
    _poll_resolution = 5  # hook point for tests

    def checkConfig(self, name, password,
                    flavor,
                    os_username=None,
                    os_password=None,
                    os_tenant_name=None,
                    os_auth_url=None,
                    os_user_domain=None,
                    os_project_domain=None,
                    os_auth_args=None,
                    block_devices=None,
                    region=None,
                    image=None,
                    meta=None,
                    # Have a nova_args parameter to allow passing things directly
                    # to novaclient.
                    nova_args=None,
                    client_version='2',
                    **kwargs):
        if not client:
            config.error("The python module 'novaclient' is needed  "
                         "to use a OpenStackLatentWorker. "
                         "Please install 'python-novaclient' package.")
        if not loading or not session:
            config.error("The python module 'keystoneauth1' is needed "
                         "to use a OpenStackLatentWorker. "
                         "Please install the 'keystoneauth1' package.")

        if block_devices is None and image is None:
            raise ValueError('One of block_devices or image must be given')

        if os_auth_args is None:
            if os_auth_url is None:
                config.error("Missing os_auth_url OpenStackLatentWorker "
                             "and os_auth_args not provided.")
            if os_username is None or os_password is None:
                config.error("Missing os_username / os_password for OpenStackLatentWorker "
                             "and os_auth_args not provided.")
        else:
            # ensure that at least auth_url is provided
            if os_auth_args.get('auth_url') is None:
                config.error("Missing 'auth_url' from os_auth_args for OpenStackLatentWorker")

        super().checkConfig(name, password, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self, name, password,
                        flavor,
                        os_username=None,
                        os_password=None,
                        os_tenant_name=None,
                        os_auth_url=None,
                        os_user_domain=None,
                        os_project_domain=None,
                        os_auth_args=None,
                        block_devices=None,
                        region=None,
                        image=None,
                        meta=None,
                        # Have a nova_args parameter to allow passing things directly
                        # to novaclient.
                        nova_args=None,
                        client_version='2',
                        **kwargs):
        yield super().reconfigService(name, password, **kwargs)

        if os_auth_args is None:
            os_auth_args = {
                    'auth_url': os_auth_url,
                    'username': os_username,
                    'password': os_password
            }
            if os_tenant_name is not None:
                os_auth_args['project_name'] = os_tenant_name
            if os_user_domain is not None:
                os_auth_args['user_domain_name'] = os_user_domain
            if os_project_domain is not None:
                os_auth_args['project_domain_name'] = os_project_domain

        self.flavor = flavor
        self.client_version = client_version
        if client:
            os_auth_args = yield self.renderSecrets(os_auth_args)
            self.novaclient = self._constructClient(client_version, os_auth_args)
            if region is not None:
                self.novaclient.client.region_name = region

        if block_devices is not None:
            self.block_devices = [
                self._parseBlockDevice(bd) for bd in block_devices]
        else:
            self.block_devices = None
        self.image = image
        self.meta = meta
        self.nova_args = nova_args if nova_args is not None else {}

    def _constructClient(self, client_version, auth_args):
        """Return a novaclient from the given args."""

        auth_plugin = auth_args.pop('auth_type', 'password')
        loader = loading.get_plugin_loader(auth_plugin)

        auth = loader.load_from_options(**auth_args)

        sess = session.Session(auth=auth)
        return client.Client(client_version, session=sess)

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
        return rendered_block_device

    def _determineVolumeSize(self, source_type, source_uuid):
        """
        Determine the minimum size the volume needs to be for the source.
        Returns the size in GiB.
        """
        nova = self.novaclient
        if source_type == 'image':
            # The size returned for an image is in bytes. Round up to the next
            # integer GiB.
            image = nova.glance.get(source_uuid)
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
            unknown_source = ("The source type '{}' for UUID '{}' is unknown".format(source_type,
                                                                                     source_uuid))
            raise ValueError(unknown_source)
        return None

    @defer.inlineCallbacks
    def _getImage(self, build):
        image_uuid = yield build.render(self.image)
        # check if we got name instead of uuid
        for image in self.novaclient.glance.list():
            if image.name == image_uuid:
                image_uuid = image.id
        return image_uuid

    @defer.inlineCallbacks
    def _getFlavor(self, build):
        flavor_uuid = yield build.render(self.flavor)
        # check if we got name instead of uuid
        for flavor in self.novaclient.flavors.list():
            if flavor.name == flavor_uuid:
                flavor_uuid = flavor.id
        return flavor_uuid

    @defer.inlineCallbacks
    def renderWorkerProps(self, build):
        image = yield self._getImage(build)
        flavor = yield self._getFlavor(build)
        nova_args = yield build.render(self.nova_args)
        meta = yield build.render(self.meta)

        if self.block_devices is not None:
            block_devices = []
            for bd in self.block_devices:
                rendered_block_device = yield self._renderBlockDevice(bd, build)
                block_devices.append(rendered_block_device)
        else:
            block_devices = None
        return (image, flavor, block_devices, nova_args, meta)

    @defer.inlineCallbacks
    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')

        image, flavor, block_devices, nova_args, meta = yield self.renderWorkerPropsOnStart(build)
        res = yield threads.deferToThread(self._start_instance, image, flavor,
                                          block_devices, nova_args, meta)
        return res

    def _start_instance(self, image_uuid, flavor_uuid, block_devices, nova_args, meta):
        boot_args = [self.workername, image_uuid, flavor_uuid]
        boot_kwargs = dict(
            meta=meta,
            block_device_mapping_v2=block_devices,
            **nova_args)
        instance = self.novaclient.servers.create(*boot_args, **boot_kwargs)
        # There is an issue when using sessions that the status is not
        # available on the first try. Trying again will work fine. Fetch the
        # instance to avoid that.
        try:
            instance = self.novaclient.servers.get(instance.id)
        except NotFound as e:
            log.msg('{class_name} {name} instance {instance.id} '
                    '({instance.name}) never found',
                    class_name=self.__class__.__name__, name=self.workername,
                    instance=instance)
            raise LatentWorkerFailedToSubstantiate(instance.id, BUILD) from e
        self.instance = instance
        log.msg('{} {} starting instance {} (image {})'.format(self.__class__.__name__,
                                                               self.workername, instance.id,
                                                               image_uuid))
        duration = 0
        interval = self._poll_resolution
        while instance.status.startswith(BUILD):
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg(('{} {} has waited {} minutes for instance {}'
                         ).format(self.__class__.__name__, self.workername, duration // 60,
                                  instance.id))
            try:
                instance = self.novaclient.servers.get(instance.id)
            except NotFound as e:
                log.msg('{} {} instance {} ({}) went missing'.format(self.__class__.__name__,
                                                                     self.workername,
                                                                     instance.id, instance.name))
                raise LatentWorkerFailedToSubstantiate(instance.id, instance.status) from e
        if instance.status == ACTIVE:
            minutes = duration // 60
            seconds = duration % 60
            log.msg('{} {} instance {} ({}) started in about {} minutes {} seconds'.format(
                    self.__class__.__name__, self.workername, instance.id, instance.name, minutes,
                    seconds))
            return [instance.id, image_uuid,
                    '%02d:%02d:%02d' % (minutes // 60, minutes % 60, seconds)]
        else:
            self.failed_to_start(instance.id, instance.status)

    def stop_instance(self, fast=False):
        if self.instance is None:
            # be gentle.  Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        instance = self.instance
        self.instance = None
        self.resetWorkerPropsOnStop()
        self._stop_instance(instance, fast)
        return None

    def _stop_instance(self, instance, fast):
        try:
            instance = self.novaclient.servers.get(instance.id)
        except NotFound:
            # If can't find the instance, then it's already gone.
            log.msg('{} {} instance {} ({}) already terminated'.format(self.__class__.__name__,
                                                                       self.workername, instance.id,
                                                                       instance.name))
            return
        if instance.status not in (DELETED, UNKNOWN):
            instance.delete()
            log.msg('{} {} terminating instance {} ({})'.format(self.__class__.__name__,
                                                                self.workername, instance.id,
                                                                instance.name))
