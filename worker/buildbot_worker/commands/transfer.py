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

import os
import tarfile
import tempfile
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log

from buildbot_worker.commands.base import Command

if TYPE_CHECKING:
    from io import BufferedIOBase
    from io import BufferedWriter
    from typing import TypeVar

    from twisted.internet.defer import Deferred
    from twisted.python.failure import Failure

    from buildbot_worker.util.twisted import InlineCallbacksType

    _T = TypeVar("_T")


class TransferCommand(Command):
    stderr: str | None = None

    def finished(self, res: bool | Failure | None) -> bool | Failure | None:
        if self.debug:
            self.log_msg(f'finished: stderr={self.stderr!r}, rc={self.rc!r}')

        # don't use self.sendStatus here, since we may no longer be running
        # if we have been interrupted
        updates: list[tuple[str, Any]] = [('rc', self.rc)]
        if self.stderr:
            updates.append(('stderr', self.stderr))
        self.protocol_command.send_update(updates)
        return res

    def interrupt(self) -> None:
        if self.debug:
            self.log_msg('interrupted')
        if self.interrupted:
            return
        self.rc = 1
        self.interrupted = True
        # now we wait for the next trip around the loop.  It abandon the file
        # when it sees self.interrupted set.


class WorkerFileUploadCommand(TransferCommand):
    """
    Upload a file from worker to build master
    Arguments:

        - ['path']:      path to read from
        - ['writer']:    RemoteReference to a buildbot_worker.protocols.base.FileWriterProxy object
        - ['maxsize']:   max size (in bytes) of file to write
        - ['blocksize']: max size for each data block
        - ['keepstamp']: whether to preserve file modified and accessed times
    """

    debug = False

    requiredArgs = ['path', 'writer', 'blocksize']

    # TODO: args: TypedDict
    def setup(self, args: dict[str, Any]) -> None:
        self.path: str = args['path']
        self.writer = args['writer']
        self.remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.keepstamp = args.get('keepstamp', False)
        self.stderr = None
        self.rc = 0
        self.fp: BufferedIOBase | None = None

    def start(self) -> Deferred[None]:
        if self.debug:
            self.log_msg('WorkerFileUploadCommand started')

        access_time = None
        modified_time = None
        try:
            if self.keepstamp:
                access_time = os.path.getatime(self.path)
                modified_time = os.path.getmtime(self.path)

            self.fp = open(self.path, 'rb')
            if self.debug:
                self.log_msg(f"Opened '{self.path}' for upload")
        except Exception:
            self.fp = None
            self.stderr = f"Cannot open file '{self.path}' for upload"
            self.rc = 1
            if self.debug:
                self.log_msg(f"Cannot open file '{self.path}' for upload")

        self.sendStatus([('header', f"sending {self.path}\n")])

        d: Deferred[None] = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)

        @defer.inlineCallbacks
        def _close_ok(res: Any) -> InlineCallbacksType[None]:
            if self.fp:
                self.fp.close()
            self.fp = None
            yield self.protocol_command.protocol_update_upload_file_close(self.writer)  # type: ignore[attr-defined]

            if self.keepstamp:
                yield self.protocol_command.protocol_update_upload_file_utime(  # type: ignore[attr-defined]
                    self.writer, access_time, modified_time
                )

        def _close_err(f: _T) -> Deferred[_T]:
            self.rc = 1
            if self.fp:
                self.fp.close()
            self.fp = None
            # call remote's close(), but keep the existing failure
            d1: Deferred[_T] = self.protocol_command.protocol_update_upload_file_close(self.writer)  # type: ignore[attr-defined]

            def eb(f2: Failure) -> None:
                self.log_msg("ignoring error from remote close():")
                log.err(f2)

            d1.addErrback(eb)
            d1.addBoth(lambda _: f)  # always return _loop failure
            return d1

        d.addCallbacks(_close_ok, _close_err)
        d.addBoth(self.finished)
        return d

    def _loop(self, fire_when_done: Deferred[None]) -> None:
        # FIXME: _writeBlock should return bool OR Deferred[bool] not union of them
        d: Deferred[bool] = defer.maybeDeferred(self._writeBlock)  # type: ignore[call-overload]

        def _done(finished: bool) -> None:
            if finished:
                fire_when_done.callback(None)
            else:
                self._loop(fire_when_done)

        def _err(why: Failure) -> None:
            fire_when_done.errback(why)

        d.addCallbacks(_done, _err)
        return None

    def _writeBlock(self) -> Deferred[bool] | bool:
        """Write a block of data to the remote writer"""

        if self.interrupted or self.fp is None:
            if self.debug:
                self.log_msg('WorkerFileUploadCommand._writeBlock(): end')
            return True

        length = self.blocksize
        if self.remaining is not None and length > self.remaining:
            length = self.remaining

        if length <= 0:
            if self.stderr is None:
                self.stderr = f'Maximum filesize reached, truncating file \'{self.path}\''
                self.rc = 1
            data = b''
        else:
            data = self.fp.read(length)

        if self.debug:
            self.log_msg(
                'WorkerFileUploadCommand._writeBlock(): ' + f'allowed={length} readlen={len(data)}'
            )
        if not data:
            self.log_msg("EOF: callRemote(close)")
            return True

        if self.remaining is not None:
            self.remaining = self.remaining - len(data)
            assert self.remaining >= 0
        d = self.do_protocol_write(data)
        d.addCallback(lambda res: False)
        return d

    def do_protocol_write(self, data: bytes) -> Deferred:
        return self.protocol_command.protocol_update_upload_file_write(self.writer, data)  # type: ignore[attr-defined]


class WorkerDirectoryUploadCommand(WorkerFileUploadCommand):
    debug = False
    requiredArgs = ['path', 'writer', 'blocksize']

    # TODO: args: TypedDict
    def setup(self, args: dict[str, Any]) -> None:
        self.path = args['path']
        self.writer = args['writer']
        self.remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.compress = args['compress']
        self.stderr: str | None = None
        self.rc = 0

    def start(self) -> Deferred:
        if self.debug:
            self.log_msg('WorkerDirectoryUploadCommand started')

        if self.debug:
            self.log_msg(f"path: {self.path!r}")

        # Create temporary archive
        fd, self.tarname = tempfile.mkstemp(prefix='buildbot-transfer-')
        self.fp = os.fdopen(fd, "rb+")
        if self.compress == 'bz2':
            mode = 'w|bz2'
        elif self.compress == 'gz':
            mode = 'w|gz'
        else:
            mode = 'w'

        with tarfile.TarFile.open(mode=mode, fileobj=self.fp) as archive:
            try:
                archive.add(self.path, '')
            except OSError as e:
                # if directory does not exist, bail out with an error
                self.stderr = f"Cannot read directory '{self.path}' for upload: {e}"
                self.rc = 1
                archive.close()  # need to close it before self.finished() runs below
                d = defer.succeed(False)
                d.addCallback(self.finished)
                return d

        # Transfer it
        self.fp.seek(0)

        self.sendStatus([('header', f"sending {self.path}\n")])

        d = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)

        def unpack(res: _T) -> Deferred[_T]:
            d1 = self.protocol_command.protocol_update_upload_directory(self.writer)  # type: ignore[attr-defined]

            def unpack_err(f: _T) -> _T:
                self.rc = 1
                return f

            d1.addErrback(unpack_err)
            d1.addCallback(lambda ignored: res)
            return d1

        d.addCallback(unpack)
        d.addBoth(self.finished)
        return d

    def finished(self, res: bool | Failure | None) -> bool | Failure | None:
        assert self.fp is not None
        self.fp.close()
        self.fp = None
        os.remove(self.tarname)
        return TransferCommand.finished(self, res)

    def do_protocol_write(self, data: bytes) -> Deferred:
        return self.protocol_command.protocol_update_upload_directory_write(self.writer, data)  # type: ignore[attr-defined]


class WorkerFileDownloadCommand(TransferCommand):
    """
    Download a file from master to worker
    Arguments:

        - ['path']: path of the worker-side file to be created
        - ['reader']:    RemoteReference to a buildbot_worker.protocols.base.FileReaderProxy object
        - ['maxsize']:   max size (in bytes) of file to write
        - ['blocksize']: max size for each data block
        - ['mode']:      access mode for the new file
    """

    debug = False
    requiredArgs = ['path', 'reader', 'blocksize']

    def setup(self, args: dict[str, Any]) -> None:
        self.path: str = args['path']
        self.reader = args['reader']
        self.bytes_remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.mode = args['mode']
        self.stderr = None
        self.rc = 0
        self.fp: BufferedWriter | None = None

    def start(self) -> Deferred[None]:
        if self.debug:
            self.log_msg('WorkerFileDownloadCommand starting')

        dirname = os.path.dirname(self.path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        try:
            self.fp = open(self.path, 'wb')
            if self.debug:
                self.log_msg(f"Opened '{self.path}' for download")
            if self.mode is not None:
                # note: there is a brief window during which the new file
                # will have the worker's default (umask) mode before we
                # set the new one. Don't use this mode= feature to keep files
                # private: use the worker's umask for that instead. (it
                # is possible to call os.umask() before and after the open()
                # call, but cleaning up from exceptions properly is more of a
                # nuisance that way).
                os.chmod(self.path, self.mode)
        except OSError:
            # TODO: this still needs cleanup
            if self.fp:
                self.fp.close()
            self.fp = None
            self.stderr = f"Cannot open file '{self.path}' for download"
            self.rc = 1
            if self.debug:
                self.log_msg(f"Cannot open file '{self.path}' for download")

        d: defer.Deferred[None] = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)

        def _close(res: _T) -> Deferred[_T]:
            # close the file, but pass through any errors from _loop
            d1 = self.protocol_command.protocol_update_read_file_close(self.reader)  # type: ignore[attr-defined]
            d1.addErrback(log.err, 'while trying to close reader')
            d1.addCallback(lambda ignored: res)
            return d1

        d.addBoth(_close)
        d.addBoth(self.finished)
        return d

    def _loop(self, fire_when_done: Deferred[None]) -> None:
        d = defer.maybeDeferred(self._readBlock)

        def _done(finished: bool) -> None:
            if finished:
                fire_when_done.callback(None)
            else:
                self._loop(fire_when_done)

        def _err(why: Failure) -> None:
            fire_when_done.errback(why)

        d.addCallbacks(_done, _err)
        return None

    @defer.inlineCallbacks
    def _readBlock(self) -> InlineCallbacksType[bool]:
        """Read a block of data from the remote reader."""

        if self.interrupted or self.fp is None:
            if self.debug:
                self.log_msg('WorkerFileDownloadCommand._readBlock(): end')
            return True

        length = self.blocksize
        if self.bytes_remaining is not None and length > self.bytes_remaining:
            length = self.bytes_remaining

        if length <= 0:
            if self.stderr is None:
                self.stderr = f"Maximum filesize reached, truncating file '{self.path}'"
                self.rc = 1
            return True
        else:
            data = yield self.protocol_command.protocol_update_read_file(self.reader, length)  # type: ignore[attr-defined]
            return self._writeData(data)

    def _writeData(self, data: bytes) -> bool:
        if self.debug:
            self.log_msg(f'WorkerFileDownloadCommand._readBlock(): readlen={len(data)}')
        if not data:
            return True

        if self.bytes_remaining is not None:
            self.bytes_remaining = self.bytes_remaining - len(data)
            assert self.bytes_remaining >= 0

        assert self.fp is not None
        self.fp.write(data)
        return False

    def finished(self, res: bool | Failure | None) -> bool | Failure | None:
        if self.fp:
            self.fp.close()
        self.fp = None

        return TransferCommand.finished(self, res)
