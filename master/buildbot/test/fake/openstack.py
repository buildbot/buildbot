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

import uuid

ACTIVE = 'ACTIVE'
BUILD = 'BUILD'
DELETED = 'DELETED'
ERROR = 'ERROR'
UNKNOWN = 'UNKNOWN'


# Parts used from novaclient
class Client():

    def __init__(self, version, username, password, tenant_name, auth_url):
        self.images = Images()
        self.servers = Servers()


class Images():
    images = []

    def list(self):
        return self.images


class Servers():
    fail_to_get = False
    fail_to_start = False
    gets_until_active = 2
    instances = {}

    def create(self, *boot_args, **boot_kwargs):
        instance_id = uuid.uuid4()
        instance = Instance(instance_id, self, boot_args, boot_kwargs)
        self.instances[instance_id] = instance
        return instance

    def get(self, instance_id):
        if not self.fail_to_get and instance_id in self.instances:
            inst = self.instances[instance_id]
            if not inst.status.startswith('BUILD'):
                return inst
            inst.gets += 1
            if inst.gets >= self.gets_until_active:
                if not self.fail_to_start:
                    inst.status = ACTIVE
                else:
                    inst.status = ERROR
            return inst
        else:
            raise NotFound

    def delete(self, instance_id):
        if instance_id in self.instances:
            del self.instances[instance_id]


# This is returned by Servers.create().
class Instance():

    def __init__(self, id, servers, boot_args, boot_kwargs):
        self.id = id
        self.servers = servers
        self.boot_args = boot_args
        self.boot_kwargs = boot_kwargs
        self.gets = 0
        self.status = 'BUILD(networking)'
        self.name = 'name'

    def delete(self):
        self.servers.delete(self.id)

# Parts used from novaclient.exceptions.


class NotFound():
    pass
