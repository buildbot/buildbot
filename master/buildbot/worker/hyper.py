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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time

from twisted.internet import reactor as global_reactor
from twisted.internet import defer
from twisted.internet import threads
from twisted.python import threadpool

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util import service
from buildbot.util.logger import Logger
from buildbot.worker.docker import DockerBaseWorker

try:
    import docker  # noqa pylint: disable=unused-import
    from docker.errors import NotFound
    from hyper_sh import Client as Hyper
except ImportError:
    Hyper = None

log = Logger()


class HyperLatentManager(service.SharedService):
    """A shared service class that manages all the connections to the hyper cloud

    There is one instance of this manager per host, accesskey, secretkey tuple.
    This manager manages its own thread pull, as Hyper_sh is blocking.

    You can change the maximum number of concurrent access to hyper using

    import buildbot.worker.hyper
    buildbot.worker.hyper.HyperLatentManager.MAX_THREADS = 1
    This feature is undocumented for now, as we are not sure if this is ideal API.
    """
    MAX_THREADS = 5

    def __init__(self, hyper_host, hyper_accesskey, hyper_secretkey):
        service.SharedService.__init__(self)
        # Prepare the parameters for the Docker Client object.
        self._client_args = {'clouds': {
            hyper_host: {
                "accesskey": hyper_accesskey,
                "secretkey": hyper_secretkey
            }
        }}

    def startService(self):
        self._threadPool = threadpool.ThreadPool(
            minthreads=1, maxthreads=self.MAX_THREADS, name='hyper')
        self._threadPool.start()
        self._client = Hyper(self._client_args)

    @property
    def client(self):
        return self._client

    def stopService(self):
        self.client.close()
        return self._threadPool.stop()

    def deferToThread(self, reactor, meth, *args, **kwargs):
        return threads.deferToThreadPool(reactor, self._threadPool, meth, *args, **kwargs)


class HyperLatentWorker(DockerBaseWorker):
    """hyper.sh is a docker CaaS company"""
    instance = None
    ALLOWED_SIZES = ['s1', 's2', 's3', 's4',
                     'm1', 'm2', 'm3', 'l1', 'l2', 'l3']
    image = None
    reactor = global_reactor

    def checkConfig(self, name, password, hyper_host,
                    hyper_accesskey, hyper_secretkey, image, hyper_size="s3", masterFQDN=None, **kwargs):

        DockerBaseWorker.checkConfig(self, name, password, image=image, masterFQDN=masterFQDN, **kwargs)

        if not Hyper:
            config.error("The python modules 'docker-py>=1.4' and 'hyper_sh' are needed to use a"
                         " HyperLatentWorker")

        if hyper_size not in self.ALLOWED_SIZES:
            config.error("Size is not valid {!r} vs {!r}".format(
                hyper_size, self.ALLOWED_SIZES))

    @property
    def client(self):
        if self.manager is None:
            return None
        return self.manager.client

    @defer.inlineCallbacks
    def reconfigService(self, name, password, hyper_host,
                        hyper_accesskey, hyper_secretkey, image, hyper_size="s3", masterFQDN=None, **kwargs):
        yield DockerBaseWorker.reconfigService(self, name, password, image=image,
                                               masterFQDN=masterFQDN, **kwargs)

        self.manager = yield HyperLatentManager.getService(self.master, hyper_host, hyper_accesskey,
                                                           hyper_secretkey)
        self.size = hyper_size

    def deferToThread(self, meth, *args, **kwargs):
        return self.manager.deferToThread(self.reactor, meth, *args, **kwargs)

    @defer.inlineCallbacks
    def start_instance(self, build):
        image = yield build.render(self.image)
        yield self.deferToThread(self._thd_start_instance, image)
        defer.returnValue(True)

    def _thd_cleanup_instance(self):
        container_name = self.getContainerName()
        instances = self.client.containers(
            all=1,
            filters=dict(name=container_name))
        for instance in instances:
            # hyper filtering will match 'hyper12" if you search for 'hyper1' !
            if "".join(instance['Names']).strip("/") != container_name:
                continue
            try:
                self.client.remove_container(instance['Id'], v=True, force=True)
            except NotFound:
                pass  # that's a race condition
            except docker.errors.APIError as e:
                if "Conflict operation on container" not in str(e):
                    raise
                # else: also race condition.

    def _thd_start_instance(self, image):
        t1 = time.time()
        self._thd_cleanup_instance()
        t2 = time.time()
        instance = self.client.create_container(
            image,
            environment=self.createEnvironment(),
            labels={
                'sh_hyper_instancetype': self.size
            },
            name=self.getContainerName()
        )
        t3 = time.time()

        if instance.get('Id') is None:
            raise LatentWorkerFailedToSubstantiate(
                'Failed to start container'
            )
        instance['image'] = image
        self.instance = instance
        self.client.start(instance)
        t4 = time.time()
        log.debug('{name}:{containerid}: Container started in {total_time:.2f}', name=self.name,
                  containerid=self.shortid,
                  clean_time=t2 - t1, create_time=t3 - t2, start_time=t4 - t3, total_time=t4 - t1)
        return [instance['Id'], image]

    def stop_instance(self, fast=False):
        if self.instance is None:
            # be gentle. Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        return self.deferToThread(self._thd_stop_instance, fast)

    def _thd_stop_instance(self, fast):
        if self.instance is None:
            return
        log.debug('{name}:{containerid}: Stopping container', name=self.name,
                  containerid=self.shortid)
        t1 = time.time()
        try:
            self.client.stop(self.instance['Id'])
        except NotFound:
            # That's ok. container was already deleted, probably by an admin
            # lets fail nicely
            log.warn('{name}:{containerid}: container was already deleted!', name=self.name,
                     containerid=self.shortid)
            self.instance = None
            return
        t2 = time.time()
        if not fast:
            self.client.wait(self.instance['Id'])
        t3 = time.time()
        self.client.remove_container(self.instance['Id'], v=True, force=True)
        t4 = time.time()
        log.debug('{name}:{containerid}: Stopped container in {total_time:.2f}', name=self.name,
                  containerid=self.shortid,
                  stop_time=t2 - t1, wait_time=t3 - t2, remove_time=t4 - t3, total_time=t4 - t1)
        self.instance = None
