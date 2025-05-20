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

from __future__ import annotations

import multiprocessing
import os.path
import platform
import socket
import sys
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import cast

from twisted.application import service
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

import buildbot_worker
from buildbot_worker.commands import base
from buildbot_worker.commands import registry
from buildbot_worker.compat import bytes2unicode
from buildbot_worker.util import buffer_manager
from buildbot_worker.util import lineboundaries

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IReactorCore
    from twisted.internet.interfaces import IReactorTime
    from twisted.python.failure import Failure
    from twisted.spread.pb import RemoteReference


class UnknownCommand(pb.Error):
    pass


class ProtocolCommandBase:
    def __init__(
        self,
        unicode_encoding: str,
        worker_basedir: str,
        buffer_size: int,
        buffer_timeout: int,
        max_line_length: int,
        newline_re: str,
        builder_is_running: int,
        on_command_complete: Callable[[], None],
        on_lost_remote_step: Callable[[RemoteReference], None] | None,
        command: str,
        command_id: str,
        args: dict[str, list[str] | str],
    ) -> None:
        self.unicode_encoding = unicode_encoding
        self.worker_basedir = worker_basedir
        self.buffer_size = buffer_size
        self.buffer_timeout = buffer_timeout
        self.max_line_length = max_line_length
        self.newline_re = newline_re
        self.builder_is_running = builder_is_running
        self.on_command_complete = on_command_complete
        self.on_lost_remote_step = on_lost_remote_step
        self.command_id = command_id

        self.protocol_args_setup(command, args)

        try:
            factory = registry.getFactory(command)
        except KeyError as e:
            raise UnknownCommand(
                f"(command {command_id}): unrecognized WorkerCommand '{command}'"
            ) from e

        # .command points to a WorkerCommand instance, and is set while the step is running.
        self.command = factory(self, command_id, args)
        self._lbfs: dict[str, lineboundaries.LineBoundaryFinder] = {}
        self.buffer = buffer_manager.BufferManager(
            cast("IReactorTime", reactor),
            self.protocol_send_update_message,
            self.buffer_size,
            self.buffer_timeout,
        )

        self.is_complete = False

    def protocol_args_setup(self, command: str, args: dict[str, list[str] | str]) -> None:
        raise NotImplementedError

    def protocol_send_update_message(self, message: list[tuple[str, Any]]) -> None:
        raise NotImplementedError

    def protocol_complete(self, failure: Failure | None) -> Deferred[None]:
        raise NotImplementedError

    def log_msg(self, msg: str) -> None:
        log.msg(f"(command {self.command_id}): {msg}")

    def split_lines(
        self,
        stream: str,
        text: str,
        text_time: float,
    ) -> tuple[str, list[int], list[float]] | None:
        try:
            return self._lbfs[stream].append(text, text_time)
        except KeyError:
            lbf = self._lbfs[stream] = lineboundaries.LineBoundaryFinder(
                self.max_line_length, self.newline_re
            )
            return lbf.append(text, text_time)

    def flush_command_output(self) -> Deferred[None]:
        for key in sorted(list(self._lbfs)):
            lbf = self._lbfs[key]
            if key in ['stdout', 'stderr', 'header']:
                whole_line = lbf.flush()
                if whole_line is not None:
                    self.buffer.append(key, whole_line)
            else:  # custom logfile
                logname = key
                whole_line = lbf.flush()
                if whole_line is not None:
                    self.buffer.append('log', (logname, whole_line))

        self.buffer.flush()
        return defer.succeed(None)

    # sendUpdate is invoked by the Commands we spawn
    def send_update(self, data: list[tuple[str, Any]]) -> None:
        if not self.builder_is_running:
            # if builder is not running, do not send any status messages
            return

        if not self.is_complete:
            # first element of the tuple is dictionary key, second element is value
            data_time = time.time()
            for key, value in data:
                if key in ['stdout', 'stderr', 'header']:
                    assert isinstance(value, str)
                    whole_line = self.split_lines(key, value, data_time)
                    if whole_line is not None:
                        self.buffer.append(key, whole_line)
                elif key == 'log':
                    logname, data = value
                    assert isinstance(data, str)
                    whole_line = self.split_lines(logname, data, data_time)
                    if whole_line is not None:
                        self.buffer.append('log', (logname, whole_line))
                else:
                    self.buffer.append(key, value)

    def _ack_failed(self, why: Failure, where: str) -> None:
        self.log_msg(f"ProtocolCommandBase._ack_failed: {where}")
        log.err(why)  # we don't really care

    # this is fired by the Deferred attached to each Command
    def command_complete(self, failure: Failure | None) -> None:
        if failure:
            self.log_msg(f"ProtocolCommandBase.command_complete (failure) {self.command}")
            log.err(failure)
            # failure, if present, is a failure.Failure. To send it across
            # the wire, we must turn it into a pb.CopyableFailure.
            failure = pb.CopyableFailure(failure)
            failure.unsafeTracebacks = True
        else:
            # failure is None
            self.log_msg(f"ProtocolCommandBase.command_complete (success) {self.command}")

        self.on_command_complete()
        if not self.builder_is_running:
            self.log_msg(" but we weren't running, quitting silently")
            return
        if not self.is_complete:
            d = self.protocol_complete(failure)
            d.addErrback(self._ack_failed, "ProtocolCommandBase.command_complete")
            self.is_complete = True


class WorkerForBuilderBase(service.Service):
    ProtocolCommand: type[ProtocolCommandBase] = ProtocolCommandBase

    def remote_startCommand(
        self,
        command_ref: RemoteReference,
        command_id: str,
        command: str,
        args: dict[str, list[str] | str],
    ) -> None:
        raise NotImplementedError


class BotBase(service.MultiService):
    """I represent the worker-side bot."""

    name: str | None = "bot"  # type: ignore[assignment]
    WorkerForBuilder: type[WorkerForBuilderBase] = WorkerForBuilderBase

    os_release_file = "/etc/os-release"

    def __init__(
        self,
        basedir: str,
        unicode_encoding: str | None = None,
        delete_leftover_dirs: bool = False,
    ) -> None:
        service.MultiService.__init__(self)
        self.basedir = basedir
        self.numcpus: int | None = None
        self.unicode_encoding = unicode_encoding or sys.getfilesystemencoding() or 'ascii'
        self.delete_leftover_dirs = delete_leftover_dirs
        self.builders: dict[str, WorkerForBuilderBase] = {}
        # Don't send any data until at least buffer_size bytes have been collected
        # or buffer_timeout elapsed
        self.buffer_size = 64 * 1024
        self.buffer_timeout = 5
        self.max_line_length = 4096
        self.newline_re = r'(\r\n|\r(?=.)|\033\[u|\033\[[0-9]+;[0-9]+[Hf]|\033\[2J|\x08+)'

    # for testing purposes
    def setOsReleaseFile(self, os_release_file: str) -> None:
        self.os_release_file = os_release_file

    def startService(self) -> Deferred[None] | None:
        assert os.path.isdir(self.basedir)
        return service.MultiService.startService(self)

    def remote_getCommands(self) -> dict[str, str]:
        commands = {n: base.command_version for n in registry.getAllCommandNames()}
        return commands

    def remote_print(self, message: str) -> None:
        log.msg("message from master:", message)

    @staticmethod
    def _read_os_release(os_release_file: str, props: dict[str, str]) -> None:
        if not os.path.exists(os_release_file):
            return

        with open(os_release_file) as fin:
            for line in fin:
                line = line.strip("\r\n")
                # as per man page: Lines beginning with "#" shall be ignored as comments.
                if len(line) == 0 or line.startswith('#'):
                    continue
                # parse key-values
                key, value = line.split("=", 1)
                if value:
                    key = f'os_{key.lower()}'
                    props[key] = value.strip('"')

    def remote_getWorkerInfo(self) -> dict[str, Any]:
        """This command retrieves data from the files in WORKERDIR/info/* and
        sends the contents to the buildmaster. These are used to describe
        the worker and its configuration, and should be created and
        maintained by the worker administrator. They will be retrieved each
        time the master-worker connection is established.
        """

        files: dict[str, Any] = {}
        basedir = os.path.join(self.basedir, "info")
        if os.path.isdir(basedir):
            for f in os.listdir(basedir):
                filename = os.path.join(basedir, f)
                if os.path.isfile(filename):
                    with open(filename) as fin:
                        try:
                            files[f] = bytes2unicode(fin.read())
                        except UnicodeDecodeError as e:
                            log.err(e, f'error while reading file: {filename}')

        self._read_os_release(self.os_release_file, files)

        if not self.numcpus:
            try:
                self.numcpus = multiprocessing.cpu_count()
            except NotImplementedError:
                log.msg(
                    "warning: could not detect the number of CPUs for this worker. Assuming 1 CPU."
                )
                self.numcpus = 1
        files['environ'] = os.environ.copy()
        files['system'] = os.name
        files['basedir'] = self.basedir
        files['numcpus'] = self.numcpus

        files['version'] = self.remote_getVersion()
        files['worker_commands'] = self.remote_getCommands()
        files['delete_leftover_dirs'] = self.delete_leftover_dirs
        return files

    def remote_getVersion(self) -> str:
        """Send our version back to the Master"""
        return buildbot_worker.version

    def remote_shutdown(self) -> None:
        log.msg("worker shutting down on command from master")
        # there's no good way to learn that the PB response has been delivered,
        # so we'll just wait a bit, in hopes the master hears back.  Masters are
        # resilient to workers dropping their connections, so there is no harm
        # if this timeout is too short.
        cast("IReactorTime", reactor).callLater(0.2, cast("IReactorCore", reactor).stop)

    def remote_setBuilderList(self, builder_info: list[tuple[str, str]]) -> Deferred[list[str]]:
        raise NotImplementedError


class WorkerBase(service.MultiService):
    name: str | None  # type: ignore[assignment]

    def __init__(
        self,
        name: str,
        basedir: str,
        bot_class: type[BotBase],
        umask: int | None = None,
        unicode_encoding: str | None = None,
        delete_leftover_dirs: bool = False,
    ) -> None:
        service.MultiService.__init__(self)
        self.name = name
        bot = bot_class(
            basedir, unicode_encoding=unicode_encoding, delete_leftover_dirs=delete_leftover_dirs
        )
        bot.setServiceParent(self)
        self.bot = bot
        self.umask = umask
        self.basedir = basedir

    def startService(self) -> Deferred[None] | None:
        log.msg(f"Starting Worker -- version: {buildbot_worker.version}")

        if self.umask is not None:
            os.umask(self.umask)

        self.recordHostname(self.basedir)

        return service.MultiService.startService(self)

    def recordHostname(self, basedir: str) -> None:
        "Record my hostname in twistd.hostname, for user convenience"
        log.msg("recording hostname in twistd.hostname")
        filename = os.path.join(basedir, "twistd.hostname")

        hostname = platform.uname()[1]
        if not hostname:
            # this tends to fail on non-connected hosts, e.g., laptops
            # on planes
            hostname = socket.getfqdn()

        try:
            with open(filename, "w") as f:
                f.write(f"{hostname}\n")
        except Exception:
            log.msg("failed - ignoring")
