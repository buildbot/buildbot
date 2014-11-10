# This file is part of Buildbot. Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from io import BytesIO

from twisted.internet import defer, threads
from twisted.python import log

from buildbot.buildslave import AbstractLatentBuildSlave
from buildbot import config, interfaces

try:
    from docker import client
    _hush_pyflakes = [client]
except ImportError:
    client = None


class DockerLatentBuildSlave(AbstractLatentBuildSlave):
    instance = None

    def __init__(self, name, password, docker_host, image=None, command=None,
                 max_builds=None, notify_on_missing=None,
                 missing_timeout=(60 * 20), build_wait_timeout=(60 * 10),
                 properties={}, locks=None, volumes=None, dockerfile=None):

        if not client:
            config.error("The python module 'docker-py' is needed "
                         "to use a DockerLatentBuildSlave")
        if not image:
            config.error("DockerLatentBuildSlave: You need to specify an"
                         " image name")

        AbstractLatentBuildSlave.__init__(self, name, password, max_builds,
                                          notify_on_missing or [],
                                          missing_timeout, build_wait_timeout,
                                          properties, locks)

        self.docker_host = docker_host
        self.image = image
        self.command = command or []

        self.volumes = volumes or []
        self.dockerfile = dockerfile

    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')
        return threads.deferToThread(self._start_instance)

    def _image_exists(self, client):
        # Make sure the container exists
        for image in client.images():
            for tag in image['RepoTags']:
                if ':' in self.image and tag == self.image:
                    return True
                if tag.startswith(self.image + ':'):
                    return True
        return False

    def _start_instance(self):
        docker_client = client.Client(base_url=self.docker_host)

        found = self._image_exists(docker_client)
        if (not found) and (self.dockerfile is not None):
            log.msg("Image '%s' not found, building it from scratch" %
                    self.image)
            for line in docker_client.build(fileobj=BytesIO(self.dockerfile.encode('utf-8')),
                                            tag=self.image):
                log.msg(line)

        if not self._image_exists(docker_client):
            log.msg("Image '%s' not found" % self.image)
            raise interfaces.LatentBuildSlaveFailedToSubstantiate(
                'Image "%s" not found on docker host.' % self.image
            )

        volumes = {}
        binds = {}
        for volume_string in self.volumes:
            try:
                volume = volume_string.split(":")[1]
            except IndexError:
                log.err("Invalid volume definition for docker "
                        "{0}. Skipping...".format(volume_string))
                continue
            volumes[volume] = {}

            volume, bind = volume_string.split(':', 1)
            binds[volume] = bind

        instance = docker_client.create_container(
            self.image,
            self.command,
            volumes=volumes,
        )

        if instance.get('Id') is None:
            log.msg('Failed to create the container')
            raise interfaces.LatentBuildSlaveFailedToSubstantiate(
                'Failed to start container'
            )

        log.msg('Container created, Id: %s...' % instance['Id'][:6])
        self.instance = instance
        docker_client.start(instance['Id'], binds=binds)
        return [instance['Id'], self.image]

    def stop_instance(self, fast=False):
        if self.instance is None:
            # be gentle. Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        instance = self.instance
        self.instance = None
        self._stop_instance(instance, fast)

    def _stop_instance(self, instance, fast):
        docker_client = client.Client(self.docker_host)
        log.msg('Stopping container %s...' % instance['Id'][:6])
        docker_client.stop(instance['Id'])
        docker_client.wait(instance['Id'])

    def buildFinished(self, sb):
        self.insubstantiate()
