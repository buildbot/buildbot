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


__version__ = "4.0"


class Client:
    latest = None
    containerCreated = False
    start_exception = None

    def __init__(self, base_url):
        self.base_url = base_url
        self.call_args_create_container = []
        self.call_args_create_host_config = []
        self._images = [
            {'RepoTags': ['busybox:latest', 'worker:latest', 'tester:latest']}]
        self._pullable = ['alpine:latest', 'tester:latest']
        self._pullCount = 0
        self._containers = {}

        if Client.containerCreated:
            self.create_container("some-default-image")

    def images(self):
        return self._images

    def start(self, container):
        if self.start_exception is not None:
            raise self.start_exception  # pylint: disable=raising-bad-type

    def stop(self, id):
        pass

    def wait(self, id):
        return 0

    def build(self, fileobj, tag, pull, target):
        if fileobj.read() == b'BUG':
            pass
        elif pull != bool(pull):
            pass
        elif target != "":
            pass
        else:
            logs = []
            for line in logs:
                yield line
            self._images.append({'RepoTags': [tag + ':latest']})

    def pull(self, image, *args, **kwargs):
        if image in self._pullable:
            self._pullCount += 1
            self._images.append({'RepoTags': [image]})

    def containers(self, filters=None, *args, **kwargs):
        if filters is not None:
            if 'existing' in filters.get('name', ''):
                self.create_container(
                    image='busybox:latest',
                    name="buildbot-existing-87de7e"
                )
                self.create_container(
                    image='busybox:latest',
                    name="buildbot-existing-87de7ef"
                )

            return [
                c for c in self._containers.values()
                if c['name'].startswith(filters['name'])
            ]
        return self._containers.values()

    def create_host_config(self, *args, **kwargs):
        self.call_args_create_host_config.append(kwargs)

    def create_container(self, image, *args, **kwargs):
        self.call_args_create_container.append(kwargs)
        name = kwargs.get('name', None)
        if 'buggy' in image:
            raise RuntimeError('we could not create this container')
        for c in self._containers.values():
            if c['name'] == name:
                raise RuntimeError('cannot create with same name')
        ret = {
            'Id':
            '8a61192da2b3bb2d922875585e29b74ec0dc4e0117fcbf84c962204e97564cd7',
            'Warnings': None
        }
        self._containers[ret['Id']] = {
            'started': False,
            'image': image,
            'Id': ret['Id'],
            'name': name,  # docker does not return this
            'Names': ["/" + name],  # this what docker returns
            "State": "running",
        }
        return ret

    def remove_container(self, id, **kwargs):
        del self._containers[id]

    def logs(self, id, tail=None):
        return f"log for {id}\n1\n2\n3\nend\n".encode("utf-8")

    def close(self):
        # dummy close, no connection to cleanup
        pass


class APIClient(Client):
    pass


class errors:
    class APIError(Exception):
        pass
