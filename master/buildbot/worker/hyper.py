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

import socket

from twisted.internet import reactor as global_reactor
from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log
from twisted.python import threadpool

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.worker import AbstractLatentWorker

try:
    import docker
    from hypercompose.api import Hyper
    _hush_pyflakes = [docker, Hyper]
except ImportError:
    Hyper = None


class HyperLatentWorker(AbstractLatentWorker):
    """hyper.sh is a docker CaaS company"""
    instance = None
    ALLOWED_SIZES = ['s1', 's2', 's3', 's4', 'm1', 'm2', 'm3', 'l1', 'l2', 'l3']
    threadPool = None
    client = None
    reactor = global_reactor
    client_args = None

    def checkConfig(self, name, password, hyper_host,
                    hyper_accesskey, hyper_secretkey, image, hyper_size="s3", masterFQDN=None, **kwargs):

        # Set build_wait_timeout to 0s if not explicitely set: Starting a
        # container is almost immediate, we can affort doing so for each build.

        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0

        AbstractLatentWorker.checkConfig(self, name, password, **kwargs)

        if not Hyper:
            config.error("The python modules 'docker-py>=1.4' and 'hypercompose' are needed to use a"
                         " HyperLatentWorker")

        if hyper_size not in self.ALLOWED_SIZES:
            config.error("Size is not valid %s vs %r".format(hyper_size, self.ALLOWED_SIZES))

    def reconfigService(self, name, password, hyper_host,
                        hyper_accesskey, hyper_secretkey, image, hyper_size="xs", masterFQDN=None, **kwargs):

        AbstractLatentWorker.reconfigService(self, name, password, **kwargs)
        self.size = hyper_size
        self.image = image

        # Prepare the parameters for the Docker Client object.
        self.client_args = {'clouds': {
            hyper_host: {
                "accesskey": hyper_accesskey,
                "secretkey": hyper_secretkey
            }
        }}
        if not masterFQDN:  # also match empty string (for UI)
            masterFQDN = socket.getfqdn()
        self.masterFQDN = masterFQDN

    @defer.inlineCallbacks
    def stopService(self):
        # stopService will call stop_instance if the worker was up.
        yield AbstractLatentWorker.stopService(self)
        # we cleanup our thread and session (or reactor.stop will hang)
        if self.client is not None:
            self.client.close()
            self.client = None
        if self.threadPool is not None:
            yield self.threadPool.stop()
            self.threadPool = None

    def createEnvironment(self):
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

    @defer.inlineCallbacks
    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')

        if self.threadPool is None:
            # requests_aws4 is documented to not be thread safe, so we must serialize access
            self.threadPool = threadpool.ThreadPool(minthreads=1, maxthreads=1, name='hyper')
            self.threadPool.start()

        if self.client is None:
            self.client = Hyper(self.client_args)

        image = yield build.render(self.image)
        res = yield threads.deferToThreadPool(self.reactor, self.threadPool, self._thd_start_instance, image)
        defer.returnValue(res)

    def _thd_start_instance(self, image):
        instance = self.client.create_container(
            image,
            name=('%s%s' % (self.workername, id(self))).replace("_", "-"),
            environment=self.createEnvironment(),
        )

        if instance.get('Id') is None:
            raise LatentWorkerFailedToSubstantiate(
                'Failed to start container'
            )
        shortid = instance['Id'][:6]
        log.msg('Container created, Id: %s...' % (shortid,))
        instance['image'] = image
        self.instance = instance
        self.client.start(instance)
        return [instance['Id'], image]

    def stop_instance(self, fast=False):
        if self.instance is None:
            # be gentle. Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        instance = self.instance
        self.instance = None
        return threads.deferToThreadPool(self.reactor, self.threadPool,
                                         self._thd_stop_instance, instance, fast)

    def _thd_stop_instance(self, instance, fast):
        log.msg('Stopping container %s...' % instance['Id'][:6])
        self.client.stop(instance['Id'])
        if not fast:
            self.client.wait(instance['Id'])
        self.client.remove_container(instance['Id'], v=True, force=True)
