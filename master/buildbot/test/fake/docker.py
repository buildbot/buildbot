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

version = "1.10.6"


class Client(object):
    latest = None

    def __init__(self, base_url):
        Client.latest = self
        self.call_args_create_container = []
        self.call_args_create_host_config = []
        self.called_class_name = None
        self._images = [{'RepoTags': ['busybox:latest', 'worker:latest']}]
        self._containers = {}

    def images(self):
        return self._images

    def start(self, container):
        pass

    def stop(self, id):
        pass

    def wait(self, id):
        return 0

    def build(self, fileobj, tag):
        if fileobj.read() == b'BUG':
            pass
        else:
            logs = []
            for line in logs:
                yield line
            self._images.append({'RepoTags': [tag + ':latest']})

    def containers(self, filters=None, *args, **kwargs):
        if filters is not None:
            return [
                c for c in self._containers.values()
                if c['name'] == filters['name']
            ]
        return self._containers.values()

    def create_host_config(self, *args, **kwargs):
        self.call_args_create_host_config.append(kwargs)

    def create_container(self, image, *args, **kwargs):
        self.call_args_create_container.append(kwargs)
        self.called_class_name = self.__class__.__name__
        name = kwargs.get('name', None)
        if 'buggy' in image:
            raise Exception('we could not create this container')
        for c in self._containers.values():
            if c['name'] == name:
                raise Exception('cannot create with same name')
        ret = {
            'Id':
            '8a61192da2b3bb2d922875585e29b74ec0dc4e0117fcbf84c962204e97564cd7',
            'Warnings': None
        }
        self._containers[ret['Id']] = {
            'started': False,
            'image': image,
            'Id': ret['Id'],
            'name': name
        }
        return ret

    def remove_container(self, id, **kwargs):
        del self._containers[id]


class APIClient(Client):
    pass
