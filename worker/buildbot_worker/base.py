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

from __future__ import absolute_import
from __future__ import print_function

import multiprocessing
import os.path
import socket
import sys

from twisted.application import service
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

import buildbot_worker
from buildbot_worker import monkeypatches
from buildbot_worker.commands import base
from buildbot_worker.commands import registry
from buildbot_worker.compat import bytes2NativeString


class UnknownCommand(pb.Error):
    pass


class WorkerForBuilderBase(service.Service):

    """This is the local representation of a single Builder: it handles a
    single kind of build (like an all-warnings build). It has a name and a
    home directory. The rest of its behavior is determined by the master.
    """

    stopCommandOnShutdown = True

    # remote is a ref to the Builder object on the master side, and is set
    # when they attach. We use it to detect when the connection to the master
    # is severed.
    remote = None

    # .command points to a WorkerCommand instance, and is set while the step
    # is running. We use it to implement the stopBuild method.
    command = None

    # .remoteStep is a ref to the master-side BuildStep object, and is set
    # when the step is started
    remoteStep = None

    bf = None

    def __init__(self, name):
        # service.Service.__init__(self) # Service has no __init__ method
        self.setName(name)

    def __repr__(self):
        return "<WorkerForBuilder '%s' at %d>" % (self.name, id(self))

    def setServiceParent(self, parent):
        service.Service.setServiceParent(self, parent)
        self.bot = self.parent
        # note that self.parent will go away when the buildmaster's config
        # file changes and this Builder is removed (possibly because it has
        # been changed, so the Builder will be re-added again in a moment).
        # This may occur during a build, while a step is running.

    def setBuilddir(self, builddir):
        assert self.parent
        self.builddir = builddir
        self.basedir = os.path.join(bytes2NativeString(self.bot.basedir),
                                    bytes2NativeString(self.builddir))
        if not os.path.isdir(self.basedir):
            os.makedirs(self.basedir)

    def stopService(self):
        service.Service.stopService(self)
        if self.stopCommandOnShutdown:
            self.stopCommand()

    def activity(self):
        bot = self.parent
        if bot:
            bworker = bot.parent
            if bworker and self.bf:
                bf = bworker.bf
                bf.activity()

    def remote_setMaster(self, remote):
        self.remote = remote
        self.remote.notifyOnDisconnect(self.lostRemote)

    def remote_print(self, message):
        log.msg("WorkerForBuilder.remote_print(%s): message from master: %s" %
                (self.name, message))

    def lostRemote(self, remote):
        log.msg("lost remote")
        self.remote = None

    def lostRemoteStep(self, remotestep):
        log.msg("lost remote step")
        self.remoteStep = None
        if self.stopCommandOnShutdown:
            self.stopCommand()

    # the following are Commands that can be invoked by the master-side
    # Builder
    def remote_startBuild(self):
        """This is invoked before the first step of any new build is run.  It
        doesn't do much, but masters call it so it's still here."""
        pass

    def remote_startCommand(self, stepref, stepId, command, args):
        """
        This gets invoked by L{buildbot.process.step.RemoteCommand.start}, as
        part of various master-side BuildSteps, to start various commands
        that actually do the build. I return nothing. Eventually I will call
        .commandComplete() to notify the master-side RemoteCommand that I'm
        done.
        """

        self.activity()

        if self.command:
            log.msg("leftover command, dropping it")
            self.stopCommand()

        try:
            factory = registry.getFactory(command)
        except KeyError:
            raise UnknownCommand("unrecognized WorkerCommand '%s'" % command)
        self.command = factory(self, stepId, args)

        log.msg(" startCommand:%s [id %s]" % (command, stepId))
        self.remoteStep = stepref
        self.remoteStep.notifyOnDisconnect(self.lostRemoteStep)
        d = self.command.doStart()
        d.addCallback(lambda res: None)
        d.addBoth(self.commandComplete)
        return None

    def remote_interruptCommand(self, stepId, why):
        """Halt the current step."""
        log.msg("asked to interrupt current command: %s" % why)
        self.activity()
        if not self.command:
            # TODO: just log it, a race could result in their interrupting a
            # command that wasn't actually running
            log.msg(" .. but none was running")
            return
        self.command.doInterrupt()

    def stopCommand(self):
        """Make any currently-running command die, with no further status
        output. This is used when the worker is shutting down or the
        connection to the master has been lost. Interrupt the command,
        silence it, and then forget about it."""
        if not self.command:
            return
        log.msg("stopCommand: halting current command %s" % self.command)
        self.command.doInterrupt()  # shut up! and die!
        self.command = None  # forget you!

    # sendUpdate is invoked by the Commands we spawn
    def sendUpdate(self, data):
        """This sends the status update to the master-side
        L{buildbot.process.step.RemoteCommand} object, giving it a sequence
        number in the process. It adds the update to a queue, and asks the
        master to acknowledge the update so it can be removed from that
        queue."""

        if not self.running:
            # .running comes from service.Service, and says whether the
            # service is running or not. If we aren't running, don't send any
            # status messages.
            return
        # the update[1]=0 comes from the leftover 'updateNum', which the
        # master still expects to receive. Provide it to avoid significant
        # interoperability issues between new workers and old masters.
        if self.remoteStep:
            update = [data, 0]
            updates = [update]
            d = self.remoteStep.callRemote("update", updates)
            d.addCallback(self.ackUpdate)
            d.addErrback(self._ackFailed, "WorkerForBuilder.sendUpdate")

    def ackUpdate(self, acknum):
        self.activity()  # update the "last activity" timer

    def ackComplete(self, dummy):
        self.activity()  # update the "last activity" timer

    def _ackFailed(self, why, where):
        log.msg("WorkerForBuilder._ackFailed:", where)
        log.err(why)  # we don't really care

    # this is fired by the Deferred attached to each Command
    def commandComplete(self, failure):
        if failure:
            log.msg("WorkerForBuilder.commandFailed", self.command)
            log.err(failure)
            # failure, if present, is a failure.Failure. To send it across
            # the wire, we must turn it into a pb.CopyableFailure.
            failure = pb.CopyableFailure(failure)
            failure.unsafeTracebacks = True
        else:
            # failure is None
            log.msg("WorkerForBuilder.commandComplete", self.command)
        self.command = None
        if not self.running:
            log.msg(" but we weren't running, quitting silently")
            return
        if self.remoteStep:
            self.remoteStep.dontNotifyOnDisconnect(self.lostRemoteStep)
            d = self.remoteStep.callRemote("complete", failure)
            d.addCallback(self.ackComplete)
            d.addErrback(self._ackFailed, "sendComplete")
            self.remoteStep = None


class BotBase(service.MultiService):

    """I represent the worker-side bot."""
    name = "bot"
    WorkerForBuilder = WorkerForBuilderBase

    def __init__(self, basedir, unicode_encoding=None):
        service.MultiService.__init__(self)
        self.basedir = basedir
        self.numcpus = None
        self.unicode_encoding = unicode_encoding or sys.getfilesystemencoding(
        ) or 'ascii'
        self.builders = {}

    def startService(self):
        assert os.path.isdir(self.basedir)
        service.MultiService.startService(self)

    def remote_getCommands(self):
        commands = dict([
            (n, base.command_version)
            for n in registry.getAllCommandNames()
        ])
        return commands

    @defer.inlineCallbacks
    def remote_setBuilderList(self, wanted):
        retval = {}
        wanted_names = set([name for (name, builddir) in wanted])
        wanted_dirs = set([builddir for (name, builddir) in wanted])
        wanted_dirs.add('info')
        for (name, builddir) in wanted:
            b = self.builders.get(name, None)
            if b:
                if b.builddir != builddir:
                    log.msg("changing builddir for builder %s from %s to %s"
                            % (name, b.builddir, builddir))
                    b.setBuilddir(builddir)
            else:
                b = self.WorkerForBuilder(name)
                b.unicode_encoding = self.unicode_encoding
                b.setServiceParent(self)
                b.setBuilddir(builddir)
                self.builders[name] = b
            retval[name] = b

        # disown any builders no longer desired
        to_remove = list(set(self.builders.keys()) - wanted_names)
        if to_remove:
            yield defer.gatherResults([
                defer.maybeDeferred(self.builders[name].disownServiceParent)
                for name in to_remove])

        # and *then* remove them from the builder list
        for name in to_remove:
            del self.builders[name]

        # finally warn about any leftover dirs
        for dir in os.listdir(self.basedir):
            if os.path.isdir(os.path.join(self.basedir, dir)):
                if dir not in wanted_dirs:
                    log.msg("I have a leftover directory '%s' that is not "
                            "being used by the buildmaster: you can delete "
                            "it now" % dir)

        defer.returnValue(retval)

    def remote_print(self, message):
        log.msg("message from master:", message)

    def remote_getWorkerInfo(self):
        """This command retrieves data from the files in WORKERDIR/info/* and
        sends the contents to the buildmaster. These are used to describe
        the worker and its configuration, and should be created and
        maintained by the worker administrator. They will be retrieved each
        time the master-worker connection is established.
        """

        files = {}
        basedir = os.path.join(self.basedir, "info")
        if os.path.isdir(basedir):
            for f in os.listdir(basedir):
                filename = os.path.join(basedir, f)
                if os.path.isfile(filename):
                    with open(filename, "r") as fin:
                        files[f] = fin.read()
        if not self.numcpus:
            try:
                self.numcpus = multiprocessing.cpu_count()
            except NotImplementedError:
                log.msg("warning: could not detect the number of CPUs for "
                        "this worker. Assuming 1 CPU.")
                self.numcpus = 1
        files['environ'] = os.environ.copy()
        files['system'] = os.name
        files['basedir'] = self.basedir
        files['numcpus'] = self.numcpus

        files['version'] = self.remote_getVersion()
        files['worker_commands'] = self.remote_getCommands()
        return files

    def remote_getVersion(self):
        """Send our version back to the Master"""
        return buildbot_worker.version

    def remote_shutdown(self):
        log.msg("worker shutting down on command from master")
        # there's no good way to learn that the PB response has been delivered,
        # so we'll just wait a bit, in hopes the master hears back.  Masters are
        # resilient to workers dropping their connections, so there is no harm
        # if this timeout is too short.
        reactor.callLater(0.2, reactor.stop)


class WorkerBase(service.MultiService):
    Bot = BotBase

    def __init__(self, name, basedir,
                 umask=None,
                 unicode_encoding=None):

        service.MultiService.__init__(self)
        self.name = name
        bot = self.Bot(basedir, unicode_encoding=unicode_encoding)
        bot.setServiceParent(self)
        self.bot = bot
        self.umask = umask
        self.basedir = basedir

    def startService(self):
        # first, apply all monkeypatches
        monkeypatches.patch_all()

        log.msg("Starting Worker -- version: %s" % buildbot_worker.version)

        if self.umask is not None:
            os.umask(self.umask)

        self.recordHostname(self.basedir)

        service.MultiService.startService(self)

    def recordHostname(self, basedir):
        "Record my hostname in twistd.hostname, for user convenience"
        log.msg("recording hostname in twistd.hostname")
        filename = os.path.join(basedir, "twistd.hostname")

        try:
            hostname = os.uname()[1]  # only on unix
        except AttributeError:
            # this tends to fail on non-connected hosts, e.g., laptops
            # on planes
            hostname = socket.getfqdn()

        try:
            with open(filename, "w") as f:
                f.write("%s\n" % hostname)
        except Exception:
            log.msg("failed - ignoring")
