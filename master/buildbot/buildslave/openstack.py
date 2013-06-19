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

from twisted.internet import defer, threads
from twisted.python import log

from buildbot.buildslave.base import AbstractLatentBuildSlave
from buildbot import config, interfaces

try:
    import novaclient.exceptions as nce
    from novaclient.v1_1 import client
    _hush_pyflakes = [nce, client]
except ImportError:
    nce = None
    client = None


ACTIVE = 'ACTIVE'
BUILD = 'BUILD'
DELETED = 'DELETED'
UNKNOWN = 'UNKNOWN'

class OpenStackLatentBuildSlave(AbstractLatentBuildSlave):

    instance = None
    _poll_resolution = 5 # hook point for tests

    def __init__(self, name, password,
                 flavor,
                 image,
                 os_username,
                 os_password,
                 os_tenant_name,
                 os_auth_url,
                 meta=None,
                 max_builds=None, notify_on_missing=[], missing_timeout=60*20,
                 build_wait_timeout=60*10, properties={}, locks=None):

        if not client or not nce:
            config.error("The python module 'novaclient' is needed  "
                         "to use a OpenStackLatentBuildSlave")

        AbstractLatentBuildSlave.__init__(
            self, name, password, max_builds, notify_on_missing,
            missing_timeout, build_wait_timeout, properties, locks)
        self.flavor = flavor
        self.image = image
        self.os_username = os_username
        self.os_password = os_password
        self.os_tenant_name = os_tenant_name
        self.os_auth_url = os_auth_url
        self.meta = meta

    def _getImage(self, os_client):
        # If self.image is a callable, then pass it the list of images. The
        # function should return the image's UUID to use.
        if callable(self.image):
            image_uuid = self.image(os_client.images.list())
        else:
            image_uuid = self.image
        return image_uuid

    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')
        return threads.deferToThread(self._start_instance)

    def _start_instance(self):
        # Authenticate to OpenStack.
        os_client = client.Client(self.os_username, self.os_password,
                                  self.os_tenant_name, self.os_auth_url)
        image_uuid = self._getImage(os_client)
        flavor_id = self.flavor
        boot_args = [self.slavename, image_uuid, flavor_id]
        boot_kwargs = {}
        if self.meta is not None:
            boot_kwargs['meta'] = self.meta
        self.instance = os_client.servers.create(*boot_args, **boot_kwargs)
        log.msg('%s %s starting instance %s (image %s)' %
                (self.__class__.__name__, self.slavename, self.instance.id,
                 image_uuid))
        duration = 0
        interval = self._poll_resolution
        inst = self.instance
        while inst.status == BUILD:
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg('%s %s has waited %d minutes for instance %s' %
                        (self.__class__.__name__, self.slavename, duration//60,
                         self.instance.id))
            try:
                inst = os_client.servers.get(self.instance.id)
            except nce.NotFound:
                log.msg('%s %s instance %s (%s) went missing' %
                        (self.__class__.__name__, self.slavename,
                         self.instance.id, self.instance.name))
                raise interfaces.LatentBuildSlaveFailedToSubstantiate(
                    self.instance.id, self.instance.status)
        if inst.status == ACTIVE:
            minutes = duration//60
            seconds = duration%60
            log.msg('%s %s instance %s (%s) started '
                    'in about %d minutes %d seconds' %
                    (self.__class__.__name__, self.slavename,
                     self.instance.id, self.instance.name, minutes, seconds))
            return [self.instance.id, image_uuid,
                    '%02d:%02d:%02d' % (minutes//60, minutes%60, seconds)]
        else:
            log.msg('%s %s failed to start instance %s (%s)' %
                    (self.__class__.__name__, self.slavename,
                     self.instance.id, inst.status))
            raise interfaces.LatentBuildSlaveFailedToSubstantiate(
                self.instance.id, self.instance.status)

    def stop_instance(self, fast=False):
        if self.instance is None:
            # be gentle.  Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        instance = self.instance
        self.instance = None
        return threads.deferToThread(self._stop_instance, instance, fast)

    def _stop_instance(self, instance, fast):
        # Authenticate to OpenStack. This is needed since it seems the update
        # method doesn't do a whole lot of updating right now.
        os_client = client.Client(self.os_username, self.os_password,
                                  self.os_tenant_name, self.os_auth_url)
        # When the update method does work, replace the lines like below with
        # instance.update().
        try:
            inst = os_client.servers.get(instance.id)
        except nce.NotFound:
            # If can't find the instance, then it's already gone.
            log.msg('%s %s instance %s (%s) already terminated' %
                    (self.__class__.__name__, self.slavename, instance.id,
                     instance.name))
            return
        if inst.status not in (DELETED, UNKNOWN):
            inst.delete()
            log.msg('%s %s terminating instance %s (%s)' %
                    (self.__class__.__name__, self.slavename, instance.id,
                     instance.name))
        duration = 0
        interval = self._poll_resolution
        if fast:
            goal = (DELETED, UNKNOWN)
        else:
            goal = (DELETED,)
        while inst.status not in goal:
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg(
                    '%s %s has waited %d minutes for instance %s to end' %
                    (self.__class__.__name__, self.slavename, duration//60,
                     instance.id))
            try:
                inst = os_client.servers.get(instance.id)
            except nce.NotFound:
                break
        log.msg('%s %s instance %s %s '
                'after about %d minutes %d seconds' %
                (self.__class__.__name__, self.slavename,
                 instance.id, goal, duration//60, duration%60))
