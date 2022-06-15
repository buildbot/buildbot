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

import os
import tarfile
import tempfile

from twisted.internet import defer
from twisted.python import log

from buildbot_worker.commands.base import Command


class TransferCommand(Command):

    def finished(self, res):
        if self.debug:
            log.msg('finished: stderr={0!r}, rc={1!r}'.format(self.stderr, self.rc))

        # don't use self.sendStatus here, since we may no longer be running
        # if we have been interrupted
        updates = [('rc', self.rc)]
        if self.stderr:
            updates.append(('stderr', self.stderr))
        self.protocol_command.send_update(updates)
        return res

    def interrupt(self):
        if self.debug:
            log.msg('interrupted')
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

    def setup(self, args):
        self.path = args['path']
        self.writer = args['writer']
        self.remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.keepstamp = args.get('keepstamp', False)
        self.stderr = None
        self.rc = 0
        self.fp = None

    def start(self):
        if self.debug:
            log.msg('WorkerFileUploadCommand started')

        access_time = None
        modified_time = None
        try:
            if self.keepstamp:
                access_time = os.path.getatime(self.path)
                modified_time = os.path.getmtime(self.path)

            self.fp = open(self.path, 'rb')
            if self.debug:
                log.msg("Opened '{0}' for upload".format(self.path))
        except Exception:
            self.fp = None
            self.stderr = "Cannot open file '{0}' for upload".format(self.path)
            self.rc = 1
            if self.debug:
                log.msg("Cannot open file '{0}' for upload".format(self.path))

        self.sendStatus([('header', "sending {0}\n".format(self.path))])

        d = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)

        @defer.inlineCallbacks
        def _close_ok(res):
            if self.fp:
                self.fp.close()
            self.fp = None
            yield self.protocol_command.protocol_update_upload_file_close(self.writer)

            if self.keepstamp:
                yield self.protocol_command.protocol_update_upload_file_utime(self.writer,
                                                                              access_time,
                                                                              modified_time)

        def _close_err(f):
            self.rc = 1
            if self.fp:
                self.fp.close()
            self.fp = None
            # call remote's close(), but keep the existing failure
            d1 = self.protocol_command.protocol_update_upload_file_close(self.writer)

            def eb(f2):
                log.msg("ignoring error from remote close():")
                log.err(f2)
            d1.addErrback(eb)
            d1.addBoth(lambda _: f)  # always return _loop failure
            return d1

        d.addCallbacks(_close_ok, _close_err)
        d.addBoth(self.finished)
        return d

    def _loop(self, fire_when_done):
        d = defer.maybeDeferred(self._writeBlock)

        def _done(finished):
            if finished:
                fire_when_done.callback(None)
            else:
                self._loop(fire_when_done)

        def _err(why):
            fire_when_done.errback(why)
        d.addCallbacks(_done, _err)
        return None

    def _writeBlock(self):
        """Write a block of data to the remote writer"""

        if self.interrupted or self.fp is None:
            if self.debug:
                log.msg('WorkerFileUploadCommand._writeBlock(): end')
            return True

        length = self.blocksize
        if self.remaining is not None and length > self.remaining:
            length = self.remaining

        if length <= 0:
            if self.stderr is None:
                self.stderr = 'Maximum filesize reached, truncating file \'{0}\''.format(
                    self.path)
                self.rc = 1
            data = ''
        else:
            data = self.fp.read(length)

        if self.debug:
            log.msg('WorkerFileUploadCommand._writeBlock(): ' +
                    'allowed={0} readlen={1}'.format(length, len(data)))
        if not data:
            log.msg("EOF: callRemote(close)")
            return True

        if self.remaining is not None:
            self.remaining = self.remaining - len(data)
            assert self.remaining >= 0
        d = self.do_protocol_write(data)
        d.addCallback(lambda res: False)
        return d

    def do_protocol_write(self, data):
        return self.protocol_command.protocol_update_upload_file_write(self.writer, data)


class WorkerDirectoryUploadCommand(WorkerFileUploadCommand):
    debug = False
    requiredArgs = ['path', 'writer', 'blocksize']

    def setup(self, args):
        self.path = args['path']
        self.writer = args['writer']
        self.remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.compress = args['compress']
        self.stderr = None
        self.rc = 0

    def start(self):
        if self.debug:
            log.msg('WorkerDirectoryUploadCommand started')

        if self.debug:
            log.msg("path: {0!r}".format(self.path))

        # Create temporary archive
        fd, self.tarname = tempfile.mkstemp(prefix='buildbot-transfer-')
        self.fp = os.fdopen(fd, "rb+")

        if self.compress == 'bz2':
            mode = 'w|bz2'
        elif self.compress == 'gz':
            mode = 'w|gz'
        else:
            mode = 'w'
        # TODO: Use 'with' when depending on Python 2.7
        # Not possible with older versions:
        # exceptions.AttributeError: 'TarFile' object has no attribute '__exit__'
        archive = tarfile.open(mode=mode, fileobj=self.fp)
        archive.add(self.path, '')
        archive.close()

        # Transfer it
        self.fp.seek(0)

        self.sendStatus([('header', "sending {0}\n".format(self.path))])

        d = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)

        def unpack(res):
            d1 = self.protocol_command.protocol_update_upload_directory(self.writer)

            def unpack_err(f):
                self.rc = 1
                return f
            d1.addErrback(unpack_err)
            d1.addCallback(lambda ignored: res)
            return d1
        d.addCallback(unpack)
        d.addBoth(self.finished)
        return d

    def finished(self, res):
        self.fp.close()
        self.fp = None
        os.remove(self.tarname)
        return TransferCommand.finished(self, res)

    def do_protocol_write(self, data):
        return self.protocol_command.protocol_update_upload_directory_write(self.writer, data)


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

    def setup(self, args):
        self.path = args['path']
        self.reader = args['reader']
        self.bytes_remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.mode = args['mode']
        self.stderr = None
        self.rc = 0
        self.fp = None

    def start(self):
        if self.debug:
            log.msg('WorkerFileDownloadCommand starting')

        dirname = os.path.dirname(self.path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        try:
            self.fp = open(self.path, 'wb')
            if self.debug:
                log.msg("Opened '{0}' for download".format(self.path))
            if self.mode is not None:
                # note: there is a brief window during which the new file
                # will have the worker's default (umask) mode before we
                # set the new one. Don't use this mode= feature to keep files
                # private: use the worker's umask for that instead. (it
                # is possible to call os.umask() before and after the open()
                # call, but cleaning up from exceptions properly is more of a
                # nuisance that way).
                os.chmod(self.path, self.mode)
        except IOError:
            # TODO: this still needs cleanup
            if self.fp:
                self.fp.close()
            self.fp = None
            self.stderr = "Cannot open file '{0}' for download".format(self.path)
            self.rc = 1
            if self.debug:
                log.msg("Cannot open file '{0}' for download".format(self.path))

        d = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)

        def _close(res):
            # close the file, but pass through any errors from _loop
            d1 = self.protocol_command.protocol_update_read_file_close(self.reader)
            d1.addErrback(log.err, 'while trying to close reader')
            d1.addCallback(lambda ignored: res)
            return d1
        d.addBoth(_close)
        d.addBoth(self.finished)
        return d

    def _loop(self, fire_when_done):
        d = defer.maybeDeferred(self._readBlock)

        def _done(finished):
            if finished:
                fire_when_done.callback(None)
            else:
                self._loop(fire_when_done)

        def _err(why):
            fire_when_done.errback(why)
        d.addCallbacks(_done, _err)
        return None

    def _readBlock(self):
        """Read a block of data from the remote reader."""

        if self.interrupted or self.fp is None:
            if self.debug:
                log.msg('WorkerFileDownloadCommand._readBlock(): end')
            return True

        length = self.blocksize
        if self.bytes_remaining is not None and length > self.bytes_remaining:
            length = self.bytes_remaining

        if length <= 0:
            if self.stderr is None:
                self.stderr = "Maximum filesize reached, truncating file '{0}'".format(
                    self.path)
                self.rc = 1
            return True
        else:
            d = self.protocol_command.protocol_update_read_file(self.reader, length)
            d.addCallback(self._writeData)
            return d

    def _writeData(self, data):
        if self.debug:
            log.msg('WorkerFileDownloadCommand._readBlock(): readlen=%d' %
                    len(data))
        if not data:
            return True

        if self.bytes_remaining is not None:
            self.bytes_remaining = self.bytes_remaining - len(data)
            assert self.bytes_remaining >= 0
        self.fp.write(data)
        return False

    def finished(self, res):
        if self.fp:
            self.fp.close()
        self.fp = None

        return TransferCommand.finished(self, res)
