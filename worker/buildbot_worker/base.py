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
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

import buildbot_worker
from buildbot_worker import monkeypatches
from buildbot_worker.commands import base
from buildbot_worker.commands import registry


class UnknownCommand(pb.Error):
    pass


class ProtocolCommandBase:
    def __init__(self, unicode_encoding, worker_basedir, builder_is_running,
                 on_command_complete, on_lost_remote_step, command, command_id, args):
        self.unicode_encoding = unicode_encoding
        self.worker_basedir = worker_basedir
        self.builder_is_running = builder_is_running
        self.on_command_complete = on_command_complete
        self.on_lost_remote_step = on_lost_remote_step

        self.protocol_args_setup(command, args)

        try:
            factory = registry.getFactory(command)
        except KeyError:
            raise UnknownCommand(u"unrecognized WorkerCommand '{0}'".format(command))

        # .command points to a WorkerCommand instance, and is set while the step is running.
        self.command = factory(self, command_id, args)

        self.is_complete = False

    # sendUpdate is invoked by the Commands we spawn
    def send_update(self, data):
        """This sends the status update to the master-side
        L{buildbot.process.step.RemoteCommand} object, giving it a sequence
        number in the process. It adds the update to a queue, and asks the
        master to acknowledge the update so it can be removed from that
        queue."""

        if not self.builder_is_running:
            # .running comes from service.Service, and says whether the
            # service is running or not. If we aren't running, don't send any
            # status messages.
            return
        # the update[1]=0 comes from the leftover 'updateNum', which the
        # master still expects to receive. Provide it to avoid significant
        # interoperability issues between new workers and old masters.
        if not self.is_complete:
            update = [data, 0]
            updates = [update]
            d = self.protocol_update(updates)
            d.addErrback(self._ack_failed, "ProtocolCommandBase.send_update")

    def _ack_failed(self, why, where):
        log.msg("ProtocolCommandBase._ack_failed:", where)
        log.err(why)  # we don't really care

    # this is fired by the Deferred attached to each Command
    def command_complete(self, failure):
        if failure:
            log.msg("ProtocolCommandBase.command_complete (failure)", self.command)
            log.err(failure)
            # failure, if present, is a failure.Failure. To send it across
            # the wire, we must turn it into a pb.CopyableFailure.
            failure = pb.CopyableFailure(failure)
            failure.unsafeTracebacks = True
        else:
            # failure is None
            log.msg("ProtocolCommandBase.command_complete (success)", self.command)

        self.on_command_complete()
        if not self.builder_is_running:
            log.msg(" but we weren't running, quitting silently")
            return
        if not self.is_complete:
            d = self.protocol_complete(failure)
            d.addErrback(self._ack_failed, "ProtocolCommandBase.command_complete")
            self.is_complete = True


class WorkerForBuilderBase(service.Service):
    ProtocolCommand = ProtocolCommandBase


class BotBase(service.MultiService):

    """I represent the worker-side bot."""
    name = "bot"
    WorkerForBuilder = WorkerForBuilderBase

    os_release_file = "/etc/os-release"

    def __init__(self, basedir, unicode_encoding=None, delete_leftover_dirs=False):
        service.MultiService.__init__(self)
        self.basedir = basedir
        self.numcpus = None
        self.unicode_encoding = unicode_encoding or sys.getfilesystemencoding(
        ) or 'ascii'
        self.delete_leftover_dirs = delete_leftover_dirs
        self.builders = {}

    # for testing purposes
    def setOsReleaseFile(self, os_release_file):
        self.os_release_file = os_release_file

    def startService(self):
        assert os.path.isdir(self.basedir)
        service.MultiService.startService(self)

    def remote_getCommands(self):
        commands = {
            n: base.command_version
            for n in registry.getAllCommandNames()
        }
        return commands

    def remote_print(self, message):
        log.msg("message from master:", message)

    @staticmethod
    def _read_os_release(os_release_file, props):
        if not os.path.exists(os_release_file):
            return

        with open(os_release_file, "r") as fin:
            for line in fin:
                line = line.strip("\r\n")
                # as per man page: Lines beginning with "#" shall be ignored as comments.
                if len(line) == 0 or line.startswith('#'):
                    continue
                # parse key-values
                key, value = line.split("=", 1)
                if value:
                    key = 'os_{}'.format(key.lower())
                    props[key] = value.strip('"')

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

        self._read_os_release(self.os_release_file, files)

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
        files['delete_leftover_dirs'] = self.delete_leftover_dirs
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

    def __init__(self, name, basedir, bot_class,
                 umask=None,
                 unicode_encoding=None,
                 delete_leftover_dirs=False):

        service.MultiService.__init__(self)
        self.name = name
        bot = bot_class(basedir, unicode_encoding=unicode_encoding,
                       delete_leftover_dirs=delete_leftover_dirs)
        bot.setServiceParent(self)
        self.bot = bot
        self.umask = umask
        self.basedir = basedir

    def startService(self):
        # first, apply all monkeypatches
        monkeypatches.patch_all()

        log.msg("Starting Worker -- version: {0}".format(buildbot_worker.version))

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
                f.write("{0}\n".format(hostname))
        except Exception:
            log.msg("failed - ignoring")
