"""
A LatentSlave which uses Libcloud library. This means it should work with all
the providers supported by Libcloud which supported 'deployment' functionality.

More info and supported providers: http://libcloud.apache.org/
"""

from twisted.python import log
from twisted.internet import defer, threads

from libcloud.compute.providers import get_driver
from libcloud.compute.types import NodeState
from libcloud.compute.deployment import ScriptDeployment

from buildbot.buildslave import AbstractLatentBuildSlave

class LibcloudLatentBuildSlave(AbstractLatentBuildSlave):

    def __init__(self, name, password,
                 key, secret, provider, buildslave_installed=False,
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

        @param buildslave_installed: True if the image which has buildbot
        installed and configured is used, False otherwise.

        If False, buildslave will be installed and configured on the started
        server.
        @type buildslave_installed: bool
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

        if self.buildslave_installed:
            return threads.deferToThread(self._create_instance)
        else:
            return threads.deferToThread(self._deploy_instance)

    def stop_instance(self, instance, fast=False):
        if not self.instance:
            return defer.succeed(None)

        if instance.state not in (NodeState.TERMINATED):
            return threads.deferToThread(self._stop_instance,
                                         instance=instance, fast=fast)

    def _create_instance(self):
        log.msg('%s %s creating and starting instance: %s' %(
                self.__class__.__name__, self.slavename, self.name))

        node = self.driver.create_node(name=self.name, size=self.size,
                                       image=self.image)
        log.msg('Instance %s created' % (node.id))

        self.driver._wait_until_running(node=node, wait_period=3,
                                        timeout=200)
        log.msg('Instance %s is up and running' % (node.id))

    def _deploy_instance(self):
        log.msg('%s %s starting and deploying instance: %s' %(
                self.__class__.__name__, self.slavename, self.name))

        script = self._get_install_and_configure_builslave_script()

        # deploy_node blocks and waits until node is running
        node = self.driver.deploy_node(name=self.name, size=self.size,
                                       image=self.image, deploy=script)

        log.msg('Instance %s started and deployed' % (node.id))


    def _start_instance(self):
        log.msg('%s %s starting and deploying instance: %s' %(
                self.__class__.__name__, self.slavename, self.name))

        # deploy_node blocks and waits until node is running
        node = self.driver.deploy_node(name=self.name, size=self.size,
                                       image=self.image)

        log.msg('Instance %s started and deployed' % (node.id))

    def _stop_instance(self, instance, fast):
        destroyed = instance.destroy()
        assert destroyed is True

        self.log.msg('Instance %s stopped' % (self.instance.id))

    def _get_install_and_configure_builslave_script(self):
        # TODO
        script = ScriptDeployment('')
        return script
