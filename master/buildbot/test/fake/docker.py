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


class Client(object):

    def __init__(self, base_url):
        self._images = [{'RepoTags': ['busybox:latest', 'worker:latest']}]

    def images(self):
        return self._images

    def start(self, container):
        pass

    def stop(self, id):
        pass

    def wait(self, id):
        return 0

    def build(self, fileobj, tag):
        if fileobj.read() == 'BUG':
            logs = []
            for line in logs:
                yield line
        else:
            logs = []
            for line in logs:
                yield line
            self._images.append({'RepoTags': [tag + ':latest']})

    def create_host_config(self, *args, **kwargs):
        pass

    def create_container(self, image, *args, **kwargs):
        return {'Id': '8a61192da2b3bb2d922875585e29b74ec0dc4e0117fcbf84c962204e97564cd7',
                'Warnings': None}
