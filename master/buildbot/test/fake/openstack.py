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

TEST_UUIDS = {
    'image': '28a65eb4-f354-4420-97dc-253b826547f7',
    'volume': '65fbb9f1-c4d5-40a8-a233-ad47c52bb837',
    'snapshot': 'ab89152d-3c26-4d30-9ae5-65b705f874b7',
    'flavor': '853774a1-459f-4f1f-907e-c96f62472531',
}


class FakeNovaClient():
    region_name = ""


# Parts used from novaclient
class Client():

    def __init__(self, version, session):
        self.glance = ItemManager()
        self.glance._add_items([Image(TEST_UUIDS['image'], 'CirrOS 0.3.4', 13287936)])
        self.volumes = ItemManager()
        self.volumes._add_items([Volume(TEST_UUIDS['volume'], 'CirrOS 0.3.4', 4)])
        self.volume_snapshots = ItemManager()
        self.volume_snapshots._add_items([Snapshot(TEST_UUIDS['snapshot'], 'CirrOS 0.3.4', 2)])
        self.flavors = ItemManager()
        self.flavors._add_items([Flavor(TEST_UUIDS['flavor'], 'm1.small', 0)])
        self.servers = Servers()
        self.session = session
        self.client = FakeNovaClient()


class ItemManager():

    def __init__(self):
        self._items = {}

    def _add_items(self, new_items):
        for item in new_items:
            self._items[item.id] = item

    def list(self):
        return self._items.values()

    def get(self, uuid):
        if uuid in self._items:
            return self._items[uuid]
        else:
            raise NotFound


# This exists because Image needs an attribute that isn't supported by
# namedtuple. And once the base code is there might as well have Volume and
# Snapshot use it too.
class Item():

    def __init__(self, id, name, size):
        self.id = id
        self.name = name
        self.size = size


class Image(Item):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setattr(self, 'OS-EXT-IMG-SIZE:size', self.size)


class Flavor(Item):
    pass


class Volume(Item):
    pass


class Snapshot(Item):
    pass


class Servers():
    fail_to_get = False
    fail_to_start = False
    gets_until_active = 3
    gets_until_disappears = 1
    instances = {}

    def create(self, *boot_args, **boot_kwargs):
        instance_id = uuid.uuid4()
        instance = Instance(instance_id, self, boot_args, boot_kwargs)
        self.instances[instance_id] = instance
        return instance

    def get(self, instance_id):
        if instance_id not in self.instances:
            raise NotFound
        inst = self.instances[instance_id]
        if not self.fail_to_get or inst.gets < self.gets_until_disappears:
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

    def findall(self, **kwargs):
        name = kwargs.get('name', None)
        if name:
            return list(filter(lambda item: item.name == name, self.instances.values()))
        return []

    def find(self, **kwargs):
        result = self.findall(**kwargs)
        if len(result) > 0:
            raise NoUniqueMatch
        if len(result) == 0:
            raise NotFound
        return result[0]


# This is returned by Servers.create().
class Instance():

    def __init__(self, id, servers, boot_args, boot_kwargs):
        self.id = id
        self.servers = servers
        self.boot_args = boot_args
        self.boot_kwargs = boot_kwargs
        self.gets = 0
        self.status = 'BUILD(networking)'
        self.metadata = boot_kwargs.get('meta', {})
        try:
            self.name = boot_args[0]
        except IndexError:
            self.name = 'name'

    def delete(self):
        self.servers.delete(self.id)

# Parts used from novaclient.exceptions.


class NotFound(Exception):
    pass


class NoUniqueMatch(Exception):
    pass

# Parts used from keystoneauth1.


def get_plugin_loader(plugin_type):
    if plugin_type == 'password':
        return PasswordLoader()
    if plugin_type == 'token':
        return TokenLoader()
    raise ValueError("plugin_type '{}' is not supported".format(plugin_type))


class PasswordLoader():

    def load_from_options(self, **kwargs):
        return PasswordAuth(**kwargs)


class TokenLoader():
    def load_from_options(self, **kwargs):
        return TokenAuth(**kwargs)


class PasswordAuth():

    def __init__(self, auth_url, password, project_name, username, user_domain_name=None,
                 project_domain_name=None):
        self.auth_url = auth_url
        self.password = password
        self.project_name = project_name
        self.username = username
        self.user_domain_name = user_domain_name
        self.project_domain_name = project_domain_name


class TokenAuth():
    def __init__(self, auth_url, token):
        self.auth_url = auth_url
        self.token = token
        self.project_name = 'tenant'
        self.username = 'testuser'
        self.user_domain_name = 'token'
        self.project_domain_name = 'token'


class Session():

    def __init__(self, auth):
        self.auth = auth
