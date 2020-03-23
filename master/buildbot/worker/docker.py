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


import hashlib
import json
import socket
from io import BytesIO

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import config
from buildbot.interfaces import LatentWorkerCannotSubstantiate
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util import unicode2bytes
from buildbot.util.latent import CompatibleLatentWorkerMixin
from buildbot.worker import AbstractLatentWorker

try:
    import docker
    from docker import client
    from docker.errors import NotFound
    _hush_pyflakes = [docker, client]
    docker_py_version = float(docker.__version__.rsplit(".", 1)[0])
except ImportError:
    docker = None
    client = None
    docker_py_version = 0.0


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


class DockerBaseWorker(AbstractLatentWorker):

    def checkConfig(self, name, password=None, image=None,
                    masterFQDN=None, **kwargs):

        # Set build_wait_timeout to 0 if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.
        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        if image is not None and not isinstance(image, str):
            if not hasattr(image, 'getRenderingFor'):
                config.error("image must be a string")

        super().checkConfig(name, password, **kwargs)

    def reconfigService(self, name, password=None, image=None,
                        masterFQDN=None, **kwargs):
        # Set build_wait_timeout to 0 if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.
        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        if password is None:
            password = self.getRandomPass()
        if masterFQDN is None:
            masterFQDN = socket.getfqdn()
        self.masterFQDN = masterFQDN
        self.image = image
        masterName = unicode2bytes(self.master.name)
        self.masterhash = hashlib.sha1(masterName).hexdigest()[:6]
        return super().reconfigService(name, password, **kwargs)

    def getContainerName(self):
        return ('buildbot-{worker}-{hash}'.format(worker=self.workername,
                                                  hash=self.masterhash)).replace("_", "-")

    @property
    def shortid(self):
        if self.instance is None:
            return None
        return self.instance['Id'][:6]

    def createEnvironment(self, build=None):
        result = {
            "BUILDMASTER": self.masterFQDN,
            "WORKERNAME": self.name,
            "WORKERPASS": self.password
        }
        if self.registration is not None:
            result["BUILDMASTER_PORT"] = str(self.registration.getPBPort())
        if ":" in self.masterFQDN:
            result["BUILDMASTER"], result["BUILDMASTER_PORT"] = self.masterFQDN.split(":")
        return result

    @staticmethod
    def get_fqdn():
        return socket.getfqdn()

    @staticmethod
    def get_ip():
        fqdn = socket.getfqdn()
        try:
            return socket.gethostbyname(fqdn)
        except socket.gaierror:
            return fqdn


class DockerLatentWorker(DockerBaseWorker,
                         CompatibleLatentWorkerMixin):
    instance = None

    def checkConfig(self, name, password, docker_host, image=None,
                    command=None, volumes=None, dockerfile=None, version=None,
                    tls=None, followStartupLogs=False, masterFQDN=None,
                    hostconfig=None, autopull=False, alwaysPull=False,
                    custom_context=False, encoding='gzip', buildargs=None,
                    **kwargs):

        super().checkConfig(name, password, image, masterFQDN, **kwargs)

        if not client:
            config.error("The python module 'docker>=2.0' is needed to use a"
                         " DockerLatentWorker")
        if not image and not dockerfile:
            config.error("DockerLatentWorker: You need to specify at least"
                         " an image name, or a dockerfile")

        # Following block is only for checking config errors,
        # actual parsing happens in self.parse_volumes()
        # Renderables can be direct volumes definition or list member
        if isinstance(volumes, list):
            for volume_string in (volumes or []):
                if not isinstance(volume_string, str):
                    continue
                try:
                    bind, volume = volume_string.split(":", 1)
                except ValueError:
                    config.error(("Invalid volume definition for docker "
                                  "{}. Skipping...").format(volume_string))
                    continue

    @defer.inlineCallbacks
    def reconfigService(self, name, password, docker_host, image=None,
                        command=None, volumes=None, dockerfile=None,
                        version=None, tls=None, followStartupLogs=False,
                        masterFQDN=None, hostconfig=None, autopull=False,
                        alwaysPull=False, custom_context=False,
                        encoding='gzip', buildargs=None, **kwargs):

        yield super().reconfigService(name, password, image, masterFQDN, **kwargs)
        self.volumes = volumes or []
        self.followStartupLogs = followStartupLogs

        self.command = command or []
        self.dockerfile = dockerfile
        self.hostconfig = hostconfig or {}
        self.autopull = autopull
        self.alwaysPull = alwaysPull
        self.custom_context = custom_context
        self.encoding = encoding
        self.buildargs = buildargs
        # Prepare the parameters for the Docker Client object.
        self.client_args = {'base_url': docker_host}
        if version is not None:
            self.client_args['version'] = version
        if tls is not None:
            self.client_args['tls'] = tls

    def _thd_parse_volumes(self, volumes):
        volume_list = []
        for volume_string in (volumes or []):
            try:
                _, volume = volume_string.split(":", 1)
            except ValueError:
                config.error(("Invalid volume definition for docker "
                              "{}. Skipping...").format(volume_string))
                continue

            if volume.endswith(':ro') or volume.endswith(':rw'):
                volume = volume[:-3]

            volume_list.append(volume)
        return volume_list, volumes

    def _getDockerClient(self):
        if docker.version[0] == '1':
            docker_client = client.Client(**self.client_args)
        else:
            docker_client = client.APIClient(**self.client_args)
        return docker_client

    def renderWorkerProps(self, build):
        return build.render((self.image, self.dockerfile,
                             self.volumes, self.custom_context,
                             self.encoding, self.buildargs))

    @defer.inlineCallbacks
    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')
        image, dockerfile, volumes, custom_context, encoding, buildargs = \
            yield self.renderWorkerPropsOnStart(build)

        res = yield threads.deferToThread(self._thd_start_instance, image,
                                          dockerfile, volumes, custom_context,
                                          encoding, buildargs)
        defer.returnValue(res)

    def _image_exists(self, client, name):
        # Make sure the image exists
        for image in client.images():
            for tag in image['RepoTags'] or []:
                if ':' in name and tag == name:
                    return True
                if tag.startswith(name + ':'):
                    return True
        return False

    def _thd_start_instance(self, image, dockerfile, volumes,
                            custom_context, encoding, buildargs):
        docker_client = self._getDockerClient()
        container_name = self.getContainerName()
        # cleanup the old instances
        instances = docker_client.containers(
            all=1,
            filters=dict(name=container_name))
        container_name = "/{0}".format(container_name)
        for instance in instances:
            if container_name not in instance['Names']:
                continue
            try:
                docker_client.remove_container(instance['Id'], v=True, force=True)
            except NotFound:
                pass  # that's a race condition

        found = False
        if image is not None:
            found = self._image_exists(docker_client, image)
        else:
            image = '{}_{}_image'.format(self.workername, id(self))
        if (not found) and (dockerfile is not None):
            log.msg("Image '{}' not found, building it from scratch".format(image))
            if (custom_context):
                with open(dockerfile, 'rb') as fin:
                    lines = docker_client.build(fileobj=fin,
                                                custom_context=custom_context,
                                                encoding=encoding, tag=image,
                                                buildargs=buildargs)
            else:
                lines = docker_client.build(
                    fileobj=BytesIO(dockerfile.encode('utf-8')),
                    tag=image,
                )

            for line in lines:
                for streamline in _handle_stream_line(line):
                    log.msg(streamline)

        imageExists = self._image_exists(docker_client, image)
        if ((not imageExists) or self.alwaysPull) and self.autopull:
            if (not imageExists):
                log.msg("Image '{}' not found, pulling from registry".format(image))
            docker_client.pull(image)

        if (not self._image_exists(docker_client, image)):
            msg = 'Image "{}" not found on docker host.'.format(image)
            log.msg(msg)
            raise LatentWorkerCannotSubstantiate(msg)

        volumes, binds = self._thd_parse_volumes(volumes)
        host_conf = self.hostconfig.copy()
        host_conf['binds'] = binds
        if docker_py_version >= 2.2:
            host_conf['init'] = True
        host_conf = docker_client.create_host_config(**host_conf)

        instance = docker_client.create_container(
            image,
            self.command,
            name=self.getContainerName(),
            volumes=volumes,
            environment=self.createEnvironment(),
            host_config=host_conf
        )

        if instance.get('Id') is None:
            log.msg('Failed to create the container')
            raise LatentWorkerFailedToSubstantiate(
                'Failed to start container'
            )
        shortid = instance['Id'][:6]
        log.msg('Container created, Id: {}...'.format(shortid))
        instance['image'] = image
        self.instance = instance
        docker_client.start(instance)
        log.msg('Container started')
        if self.followStartupLogs:
            logs = docker_client.attach(
                container=instance, stdout=True, stderr=True, stream=True)
            for line in logs:
                log.msg("docker VM {}: {}".format(shortid, line.strip()))
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
        docker_client = self._getDockerClient()
        log.msg('Stopping container {}...'.format(instance['Id'][:6]))
        docker_client.stop(instance['Id'])
        if not fast:
            docker_client.wait(instance['Id'])
        docker_client.remove_container(instance['Id'], v=True, force=True)
        if self.image is None:
            try:
                docker_client.remove_image(image=instance['image'])
            except docker.errors.APIError as e:
                log.msg('Error while removing the image: %s', e)
