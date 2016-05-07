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

# Needed so that this module name don't clash with docker-py on older python.
from __future__ import absolute_import

import socket
from io import BytesIO

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util import json
from buildbot.worker import AbstractLatentWorker

try:
    import docker
    from docker import client
    _hush_pyflakes = [docker, client]
except ImportError:
    client = None


def _handle_stream_line(line):
    """\
    Input is the json representation of: {'stream': "Content\ncontent"}
    Output is a generator yield "Content", and then "content"
    """
    # XXX This necessary processing is probably a bug from docker-py,
    # hence, might break if the bug is fixed, i.e. we should get decoded JSON
    # directly from the API.
    line = json.loads(line)
    if 'error' in line:
        content = "ERROR: " + line['error']
    else:
        content = line.get('stream', '')
    for streamline in content.split('\n'):
        if streamline:
            yield streamline


class DockerLatentWorker(AbstractLatentWorker):
    instance = None

    def __init__(self, name, password, docker_host, image=None, command=None,
                 volumes=None, dockerfile=None, version=None, tls=None, followStartupLogs=False,
                 masterFQDN=None, hostconfig=None, networking_config='bridge', **kwargs):

        if not client:
            config.error("The python module 'docker-py>=1.4' is needed to use a"
                         " DockerLatentWorker")
        if not image and not dockerfile:
            config.error("DockerLatentWorker: You need to specify at least"
                         " an image name, or a dockerfile")

        self.volumes = volumes or []
        self.binds = {}
        self.networking_config = networking_config
        self.followStartupLogs = followStartupLogs

        # Following block is only for checking config errors,
        # actual parsing happens in self.parse_volumes()
        # Renderables can be direct volumes definition or list member
        if isinstance(volumes, list):
            for volume_string in (volumes or []):
                if not isinstance(volume_string, str):
                    continue
                try:
                    volume, bind = volume_string.split(":", 1)
                except ValueError:
                    config.error("Invalid volume definition for docker "
                                 "%s. Skipping..." % volume_string)
                    continue

        # Set build_wait_timeout to 0 if not explicitely set: Starting a
        # container is almost immediate, we can affort doing so for each build.
        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        AbstractLatentWorker.__init__(self, name, password, **kwargs)

        self.image = image
        self.command = command or []
        self.dockerfile = dockerfile
        if masterFQDN is None:
            masterFQDN = socket.getfqdn()
        self.masterFQDN = masterFQDN
        self.hostconfig = hostconfig or {}
        # Prepare the parameters for the Docker Client object.
        self.client_args = {'base_url': docker_host}
        if version is not None:
            self.client_args['version'] = version
        if tls is not None:
            self.client_args['tls'] = tls

    def parse_volumes(self, volumes):
        self.volumes = []
        for volume_string in (volumes or []):
            try:
                volume, bind = volume_string.split(":", 1)
            except ValueError:
                config.error("Invalid volume definition for docker "
                             "%s. Skipping..." % volume_string)
                continue
            self.volumes.append(volume_string)

            ro = False
            if bind.endswith(':ro') or bind.endswith(':rw'):
                ro = bind[-2:] == 'ro'
                bind = bind[:-3]
            self.binds[volume] = {'bind': bind, 'ro': ro}

    def createEnvironment(self):
        result = {
            "BUILDMASTER": self.masterFQDN,
            "WORKERNAME": self.name,
            "WORKERPASS": self.password
        }
        if self.registration is not None:
            result["BUILDMASTER_PORT"] = str(self.registration.getPBPort())
        return result

    @defer.inlineCallbacks
    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')
        image = yield build.render(self.image)
        volumes = yield build.render(self.volumes)
        res = yield threads.deferToThread(self._thd_start_instance, image, volumes)
        defer.returnValue(res)

    def _image_exists(self, client, name):
        # Make sure the image exists
        for image in client.images():
            for tag in image['RepoTags']:
                if ':' in name and tag == name:
                    return True
                if tag.startswith(name + ':'):
                    return True
        return False

    def _thd_start_instance(self, image, volumes):
        docker_client = client.Client(**self.client_args)

        found = False
        if image is not None:
            found = self._image_exists(docker_client, image)
        else:
            image = '%s_%s_image' % (self.workername, id(self))
        if (not found) and (self.dockerfile is not None):
            log.msg("Image '%s' not found, building it from scratch" %
                    image)
            for line in docker_client.build(fileobj=BytesIO(self.dockerfile.encode('utf-8')),
                                            tag=image):
                for streamline in _handle_stream_line(line):
                    log.msg(streamline)

        if (not self._image_exists(docker_client, image)):
            log.msg("Image '%s' not found" % image)
            raise LatentWorkerFailedToSubstantiate(
                'Image "%s" not found on docker host.' % image
            )

        self.parse_volumes(volumes)
        self.hostconfig['binds'] = self.binds
        host_conf = docker_client.create_host_config(**self.hostconfig)

        instance = docker_client.create_container(
            image,
            self.command,
            name='%s_%s' % (self.workername, id(self)),
            volumes=self.volumes,
            environment=self.createEnvironment(),
            host_config=host_conf,
            networking_config=self.networking_config
        )

        if instance.get('Id') is None:
            log.msg('Failed to create the container')
            raise LatentWorkerFailedToSubstantiate(
                'Failed to start container'
            )
        shortid = instance['Id'][:6]
        log.msg('Container created, Id: %s...' % (shortid,))
        instance['image'] = image
        self.instance = instance
        docker_client.start(instance)
        log.msg('Container started')
        if self.followStartupLogs:
            logs = docker_client.attach(
                container=instance, stdout=True, stderr=True, stream=True)
            for line in logs:
                log.msg("docker VM %s: %s" % (shortid, line.strip()))
                if self.conn:
                    break
            del logs
        return [instance['Id'], image]

    def stop_instance(self, fast=False):
        if self.instance is None:
            # be gentle. Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        instance = self.instance
        self.instance = None
        return threads.deferToThread(self._thd_stop_instance, instance, fast)

    def _thd_stop_instance(self, instance, fast):
        docker_client = client.Client(**self.client_args)
        log.msg('Stopping container %s...' % instance['Id'][:6])
        docker_client.stop(instance['Id'])
        if not fast:
            docker_client.wait(instance['Id'])
        docker_client.remove_container(instance['Id'], v=True, force=True)
        if self.image is None:
            try:
                docker_client.remove_image(image=instance['image'])
            except docker.errors.APIError as e:
                log.msg('Error while removing the image: %s', e)
