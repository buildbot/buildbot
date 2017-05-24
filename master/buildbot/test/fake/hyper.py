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
# Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function


class Client(object):
    instance = None

    def __init__(self, config):
        self.config = config
        self._containers = {}
        # there should be only one Client instance during tests
        # if this is not the case then tests are leaking between each other
        assert Client.instance is None
        Client.instance = self

    def start(self, container):
        self._containers[container["Id"]]['started'] = True

    def close(self):
        # we should never close if we have live containers
        assert not self._containers, self._containers
        Client.instance = None

    def stop(self, id):
        self._containers[id]['started'] = False

    def wait(self, id):
        return 0

    def containers(self, filters=None, *args, **kwargs):
        if filters is not None:
            def match(name, names):
                for n in names:
                    if name in n:
                        return True
                return False
            return [c for c in self._containers.values() if match(filters['name'], c['Names'])]
        return self._containers.values()

    def create_container(self, image, name=None, *args, **kwargs):
        if 'buggy' in image:
            raise Exception("we could not create this container")
        for c in self._containers.values():
            if c['name'] == name:
                raise Exception("cannot create with same name")
        ret = {'Id': '8a61192da2b3bb2d922875585e29b74ec0dc4e0117fcbf84c962204e97564cd7',
               'Warnings': None}
        self._containers[ret['Id']] = {
            'started': False, 'image': image, 'Id': ret['Id'], "Names": ["/" + name]
        }
        return ret

    def remove_container(self, id, **kwargs):
        del self._containers[id]
