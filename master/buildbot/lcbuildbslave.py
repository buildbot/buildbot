"""
A LatentSlave which uses Libcloud library. This means it should work with all
the providers supported by Libcloud which supported 'deployment' functionality.

More info and supported providers: http://libcloud.apache.org/
"""

from twisted.python import log
from twisted.internet import defer, threads

from libcloud.compute.providers import get_driver
from libcloud.compute.types import NodeState

from buildbot.buildslave import AbstractLatentBuildSlave

class LibcloudLatentBuildSlave(AbstractLatentBuildSlave):

    def __init__(self, name, password,
                 key, secret, provider,
                 max_builds=None,
                 notify_on_missing=[], missing_timeout=60*20,
                 build_wait_timeout=60*10,
                 properties={}, locks=None):
        """
        @param key:      Provider API key or username
        @type key        str

        @param secret:   Provider secret
        @type key        str

        @param provider: Provider to use. Must support 'deployment'
                         functionality.
        @type provider:  libcloud.compute.providers.Provider
        """

        AbstractLatentBuildSlave.__init__(
                self, name, password, max_builds, notify_on_missing,
                missing_timeout, build_wait_timeout, properties, locks)

        Cls = get_driver(provider=provider)
        self.driver = Cls(key, secret)
        self.instance = None

    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance already started')

        return threads.deferToThread(self._thd_create_instance)

    def stop_instance(self, instance, fast=False):
        if not self.instance:
            return defer.succeed(None)

        if instance.state not in (NodeState.TERMINATED):
            return threads.deferToThread(self._thd_stop_instance,
                                         instance=instance, fast=fast)

    def _thd_create_instance(self):
        log.msg('%s %s creating and starting instance: %s' %(
                self.__class__.__name__, self.slavename, self.name))

        node = self.driver.create_node(name=self.name, size=self.size,
                                       image=self.image)
        log.msg('Instance %s created' % (node.id))

        self.driver._wait_until_running(node=node, wait_period=3,
                                        timeout=200)
        log.msg('Instance %s is up and running' % (node.id))

    def _thd_stop_instance(self, instance, fast):
        instance.destroy()
        self.log.msg('Instance %s stopped' % (self.instance.id))
