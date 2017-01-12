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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

from twisted.internet import defer
from twisted.internet import threads
from twisted.internet import utils
from twisted.python import failure
from twisted.python import log

from buildbot import config
from buildbot.util.eventual import eventually
from buildbot.worker import AbstractLatentWorker
from buildbot.worker import AbstractWorker

try:
    import libvirt
    libvirt = libvirt
except ImportError:
    libvirt = None


class WorkQueue(object):

    """
    I am a class that turns parallel access into serial access.

    I exist because we want to run libvirt access in threads as we don't
    trust calls not to block, but under load libvirt doesn't seem to like
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
        except Exception:
            d2 = defer.fail()

        # Whenever a piece of work is done, whether it worked or not
        # call this to schedule the next piece of work
        @d2.addBoth
        def _work_done(res):
            log.msg("Completed a piece of work")
            self.queue.pop(0)
            if self.queue:
                log.msg("Preparing next piece of work")
                eventually(self._process)
            return res

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

    def name(self):
        return queue.executeInThread(self.domain.name)

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

    DomainClass = Domain

    def __init__(self, uri):
        self.uri = uri
        self.connection = libvirt.open(uri)

    @defer.inlineCallbacks
    def lookupByName(self, name):
        """ I lookup an existing predefined domain """
        res = yield queue.executeInThread(self.connection.lookupByName, name)
        defer.returnValue(self.DomainClass(self, res))

    @defer.inlineCallbacks
    def create(self, xml):
        """ I take libvirt XML and start a new VM """
        res = yield queue.executeInThread(self.connection.createXML, xml, 0)
        defer.returnValue(self.DomainClass(self, res))

    @defer.inlineCallbacks
    def all(self):
        domains = []
        domain_ids = yield queue.executeInThread(self.connection.listDomainsID)

        for did in domain_ids:
            domain = yield queue.executeInThread(self.connection.lookupByID, did)
            domains.append(self.DomainClass(self, domain))

        defer.returnValue(domains)


class LibVirtWorker(AbstractLatentWorker):

    def __init__(self, name, password, connection, hd_image, base_image=None, xml=None,
                 **kwargs):
        AbstractLatentWorker.__init__(self, name, password, **kwargs)
        if not libvirt:
            config.error(
                "The python module 'libvirt' is needed to use a LibVirtWorker")

        self.connection = connection
        self.image = hd_image
        self.base_image = base_image
        self.xml = xml

        self.cheap_copy = True
        self.graceful_shutdown = False

        self.domain = None

        self.ready = False
        self._find_existing_deferred = self._find_existing_instance()

    @defer.inlineCallbacks
    def _find_existing_instance(self):
        """
        I find existing VMs that are already running that might be orphaned instances of this worker.
        """
        if not self.connection:
            defer.returnValue(None)

        domains = yield self.connection.all()
        for d in domains:
            name = yield d.name()
            if name.startswith(self.workername):
                self.domain = d
                break

        self.ready = True

    def canStartBuild(self):
        if not self.ready:
            log.msg("Not accepting builds as existing domains not iterated")
            return False

        if self.domain and not self.isConnected():
            log.msg(
                "Not accepting builds as existing domain but worker not connected")
            return False

        return AbstractLatentWorker.canStartBuild(self)

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

        d = utils.getProcessValue(clone_cmd, clone_args.split())

        def _log_result(res):
            log.msg("Cloning exit code was: %d" % res)
            return res

        def _log_error(err):
            log.err("Cloning failed: %s" % err)
            return err

        d.addCallbacks(_log_result, _log_error)

        return d

    @defer.inlineCallbacks
    def start_instance(self, build):
        """
        I start a new instance of a VM.

        If a base_image is specified, I will make a clone of that otherwise i will
        use image directly.

        If i'm not given libvirt domain definition XML, I will look for my name
        in the list of defined virtual machines and start that.
        """
        if self.domain is not None:
            log.msg("Cannot start_instance '%s' as already active" %
                    self.workername)
            defer.returnValue(False)

        yield self._prepare_base_image()

        try:
            if self.xml:
                self.domain = yield self.connection.create(self.xml)
            else:
                self.domain = yield self.connection.lookupByName(self.workername)
                yield self.domain.create()
        except Exception:
            log.err(failure.Failure(),
                    "Cannot start a VM (%s), failing gracefully and triggering"
                    "a new build check" % self.workername)
            self.domain = None
            defer.returnValue(False)

        defer.returnValue(True)

    def stop_instance(self, fast=False):
        """
        I attempt to stop a running VM.
        I make sure any connection to the worker is removed.
        If the VM was using a cloned image, I remove the clone
        When everything is tidied up, I ask that bbot looks for work to do
        """
        log.msg("Attempting to stop '%s'" % self.workername)
        if self.domain is None:
            log.msg("I don't think that domain is even running, aborting")
            return defer.succeed(None)

        domain = self.domain
        self.domain = None

        if self.graceful_shutdown and not fast:
            log.msg("Graceful shutdown chosen for %s" % self.workername)
            d = domain.shutdown()
        else:
            d = domain.destroy()

        @d.addCallback
        def _disconnect(res):
            log.msg("VM destroyed (%s): Forcing its connection closed." %
                    self.workername)
            return AbstractWorker.disconnect(self)

        @d.addBoth
        def _disconnected(res):
            log.msg(
                "We forced disconnection (%s), cleaning up and triggering new build" % self.workername)
            if self.base_image:
                os.remove(self.image)
            self.botmaster.maybeStartBuildsForWorker(self.workername)
            return res

        return d
