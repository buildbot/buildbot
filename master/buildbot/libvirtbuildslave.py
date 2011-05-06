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
# Portions Copyright Buildbot Team Members
# Portions Copyright 2010 Isotoma Limited

import os

from twisted.internet import defer, utils, reactor, threads
from twisted.python import log
from buildbot.buildslave import AbstractBuildSlave, AbstractLatentBuildSlave

import libvirt


class WorkQueue(object):
    """
    I am a class that turns parallel access into serial access.

    I exist because we want to run libvirt access in threads as we don't
    trust calls not to block, but under load libvirt doesnt seem to like
    this kind of threaded use.
    """

    def __init__(self):
        self.queue = []

    def _process(self):
        log.msg("Looking to start a piece of work now...")

        # Is there anything to do?
        if not self.queue:
            log.msg("_process called when there is no work")
            return

        # Peek at the top of the stack - get a function to call and
        # a deferred to fire when its all over
        d, next_operation, args, kwargs = self.queue[0]

        # Start doing some work - expects a deferred
        try:
            d2 = next_operation(*args, **kwargs)
        except:
            d2 = defer.fail()

        # Whenever a piece of work is done, whether it worked or not 
        # call this to schedule the next piece of work
        def _work_done(res):
            log.msg("Completed a piece of work")
            self.queue.pop(0)
            if self.queue:
                log.msg("Preparing next piece of work")
                reactor.callLater(0, self._process)
            return res
        d2.addBoth(_work_done)

        # When the work is done, trigger d
        d2.chainDeferred(d)

    def execute(self, cb, *args, **kwargs):
        kickstart_processing = not self.queue
        d = defer.Deferred()
        self.queue.append((d, cb, args, kwargs))
        if kickstart_processing:
            self._process()
        return d

    def executeInThread(self, cb, *args, **kwargs):
        return self.execute(threads.deferToThread, cb, *args, **kwargs)


# A module is effectively a singleton class, so this is OK
queue = WorkQueue()


class Domain(object):

    """
    I am a wrapper around a libvirt Domain object
    """

    def __init__(self, connection, domain):
        self.connection = connection
        self.domain = domain

    def create(self):
        return queue.executeInThread(self.domain.create)

    def shutdown(self):
        return queue.executeInThread(self.domain.shutdown)

    def destroy(self):
        return queue.executeInThread(self.domain.destroy)


class Connection(object):

    """
    I am a wrapper around a libvirt Connection object.
    """

    def __init__(self, uri):
        self.uri = uri
        self.connection = libvirt.open(uri)

    def lookupByName(self, name):
        """ I lookup an existing prefined domain """
        d = queue.executeInThread(self.connection.lookupByName, name)
        def _(res):
            return Domain(self, res)
        d.addCallback(_)
        return d

    def create(self, xml):
        """ I take libvirt XML and start a new VM """
        d = queue.executeInThread(self.connection.createXML, xml, 0)
        def _(res):
            return Domain(self, res)
        d.addCallback(_)
        return d


class LibVirtSlave(AbstractLatentBuildSlave):

    def __init__(self, name, password, connection, hd_image, base_image = None, xml=None, max_builds=None, notify_on_missing=[],
                 missing_timeout=60*20, build_wait_timeout=60*10, properties={}, locks=None):
        AbstractLatentBuildSlave.__init__(self, name, password, max_builds, notify_on_missing,
                                          missing_timeout, build_wait_timeout, properties, locks)
        self.name = name
        self.connection = connection
        self.image = hd_image
        self.base_image = base_image
        self.xml = xml

        self.insubstantiate_after_build = True
        self.cheap_copy = True
        self.graceful_shutdown = False

        self.domain = None

    def _prepare_base_image(self):
        """
        I am a private method for creating (possibly cheap) copies of a
        base_image for start_instance to boot.
        """
        if not self.base_image:
            return defer.succeed(True)

        if self.cheap_copy:
            clone_cmd = "qemu-img"
            clone_args = "create -b %(base)s -f qcow2 %(image)s"
        else:
            clone_cmd = "cp"
            clone_args = "%(base)s %(image)s"

        clone_args = clone_args % {
                "base": self.base_image,
                "image": self.image,
                }

        log.msg("Cloning base image: %s %s'" % (clone_cmd, clone_args))

        def _log_result(res):
            log.msg("Cloning exit code was: %d" % res)
            return res

        d = utils.getProcessValue(clone_cmd, clone_args.split())
        d.addBoth(_log_result)
        return d

    def start_instance(self, build):
        """
        I start a new instance of a VM.

        If a base_image is specified, I will make a clone of that otherwise i will
        use image directly.

        If i'm not given libvirt domain definition XML, I will look for my name
        in the list of defined virtual machines and start that.
        """
        if self.domain is not None:
             raise ValueError('domain active')

        d = self._prepare_base_image()

        def _start(res):
            if self.xml:
                return self.connection.create(self.xml)
            d = self.connection.lookupByName(self.name)
            def _really_start(res):
                return res.create()
            d.addCallback(_really_start)
            return d
        d.addCallback(_start)

        def _started(res):
            self.domain = res
            return True
        d.addCallback(_started)

        def _start_failed(failure):
            log.msg("Cannot start a VM (%s), failing gracefully and triggering a new build check" % self.name)
            log.err(failure)
            self.domain = None
            return False
        d.addErrback(_start_failed)

        return d

    def stop_instance(self, fast=False):
        """
        I attempt to stop a running VM.
        I make sure any connection to the slave is removed.
        If the VM was using a cloned image, I remove the clone
        When everything is tidied up, I ask that bbot looks for work to do
        """
        log.msg("Attempting to stop '%s'" % self.name)
        if self.domain is None:
             log.msg("I don't think that domain is evening running, aborting")
             return defer.succeed(None)

        domain = self.domain
        self.domain = None

        if self.graceful_shutdown and not fast:
            log.msg("Graceful shutdown chosen for %s" % self.name)
            d = domain.shutdown()
        else:
            d = domain.destroy()

        def _disconnect(res):
            log.msg("VM destroyed (%s): Forcing its connection closed." % self.name)
            return AbstractBuildSlave.disconnect(self)
        d.addCallback(_disconnect)

        def _disconnected(res):
            log.msg("We forced disconnection (%s), cleaning up and triggering new build" % self.name)
            if self.base_image:
                os.remove(self.image)
            self.botmaster.maybeStartBuildsForSlave(self.name)
            return res
        d.addBoth(_disconnected)

        return d

    def buildFinished(self, *args, **kwargs):
        """
        I insubstantiate a slave after it has done a build, if that is
        desired behaviour.
        """
        AbstractLatentBuildSlave.buildFinished(self, *args, **kwargs)
        if self.insubstantiate_after_build:
            log.msg("Got buildFinished notification - attempting to insubstantiate")
            self.insubstantiate()


