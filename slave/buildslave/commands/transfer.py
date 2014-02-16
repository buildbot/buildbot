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

import os
import tarfile
import tempfile

from twisted.internet import defer
from twisted.python import log

from buildslave.commands.base import Command


class TransferCommand(Command):

    def finished(self, res):
        if self.debug:
            log.msg('finished: stderr=%r, rc=%r' % (self.stderr, self.rc))

        # don't use self.sendStatus here, since we may no longer be running
        # if we have been interrupted
        upd = {'rc': self.rc}
        if self.stderr:
            upd['stderr'] = self.stderr
        self.builder.sendUpdate(upd)
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


class SlaveFileUploadCommand(TransferCommand):

    """
    Upload a file from slave to build master
    Arguments:

        - ['workdir']:   base directory to use
        - ['slavesrc']:  name of the slave-side file to read from
        - ['writer']:    RemoteReference to a transfer._FileWriter object
        - ['maxsize']:   max size (in bytes) of file to write
        - ['blocksize']: max size for each data block
        - ['keepstamp']: whether to preserve file modified and accessed times
    """
    debug = False
    requiredArgs = ['workdir', 'slavesrc', 'writer', 'blocksize']

    def setup(self, args):
        self.workdir = args['workdir']
        self.filename = args['slavesrc']
        self.writer = args['writer']
        self.remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.keepstamp = args.get('keepstamp', False)
        self.stderr = None
        self.rc = 0

    def start(self):
        if self.debug:
            log.msg('SlaveFileUploadCommand started')

        # Open file
        self.path = os.path.join(self.builder.basedir,
                                 self.workdir,
                                 os.path.expanduser(self.filename))
        accessed_modified = None
        try:
            if self.keepstamp:
                accessed_modified = (os.path.getatime(self.path),
                                     os.path.getmtime(self.path))

            self.fp = open(self.path, 'rb')
            if self.debug:
                log.msg("Opened '%s' for upload" % self.path)
        except:
            self.fp = None
            self.stderr = "Cannot open file '%s' for upload" % self.path
            self.rc = 1
            if self.debug:
                log.msg("Cannot open file '%s' for upload" % self.path)

        self.sendStatus({'header': "sending %s" % self.path})

        d = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)

        def _close_ok(res):
            self.fp = None
            d1 = self.writer.callRemote("close")

            def _utime_ok(res):
                return self.writer.callRemote("utime", accessed_modified)
            if self.keepstamp:
                d1.addCallback(_utime_ok)
            return d1

        def _close_err(f):
            self.rc = 1
            self.fp = None
            # call remote's close(), but keep the existing failure
            d1 = self.writer.callRemote("close")

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
                log.msg('SlaveFileUploadCommand._writeBlock(): end')
            return True

        length = self.blocksize
        if self.remaining is not None and length > self.remaining:
            length = self.remaining

        if length <= 0:
            if self.stderr is None:
                self.stderr = 'Maximum filesize reached, truncating file \'%s\'' \
                    % self.path
                self.rc = 1
            data = ''
        else:
            data = self.fp.read(length)

        if self.debug:
            log.msg('SlaveFileUploadCommand._writeBlock(): ' +
                    'allowed=%d readlen=%d' % (length, len(data)))
        if len(data) == 0:
            log.msg("EOF: callRemote(close)")
            return True

        if self.remaining is not None:
            self.remaining = self.remaining - len(data)
            assert self.remaining >= 0
        d = self.writer.callRemote('write', data)
        d.addCallback(lambda res: False)
        return d


class SlaveDirectoryUploadCommand(SlaveFileUploadCommand):
    debug = False
    requiredArgs = ['workdir', 'slavesrc', 'writer', 'blocksize']

    def setup(self, args):
        self.workdir = args['workdir']
        self.dirname = args['slavesrc']
        self.writer = args['writer']
        self.remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.compress = args['compress']
        self.stderr = None
        self.rc = 0

    def start(self):
        if self.debug:
            log.msg('SlaveDirectoryUploadCommand started')

        self.path = os.path.join(self.builder.basedir,
                                 self.workdir,
                                 os.path.expanduser(self.dirname))
        if self.debug:
            log.msg("path: %r" % self.path)

        # Create temporary archive
        fd, self.tarname = tempfile.mkstemp()
        fileobj = os.fdopen(fd, 'w')
        if self.compress == 'bz2':
            mode = 'w|bz2'
        elif self.compress == 'gz':
            mode = 'w|gz'
        else:
            mode = 'w'
        archive = tarfile.open(name=self.tarname, mode=mode, fileobj=fileobj)
        archive.add(self.path, '')
        archive.close()
        fileobj.close()

        # Transfer it
        self.fp = open(self.tarname, 'rb')

        self.sendStatus({'header': "sending %s" % self.path})

        d = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)

        def unpack(res):
            d1 = self.writer.callRemote("unpack")

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
        os.remove(self.tarname)
        return TransferCommand.finished(self, res)


class SlaveFileDownloadCommand(TransferCommand):

    """
    Download a file from master to slave
    Arguments:

        - ['workdir']:   base directory to use
        - ['slavedest']: name of the slave-side file to be created
        - ['reader']:    RemoteReference to a transfer._FileReader object
        - ['maxsize']:   max size (in bytes) of file to write
        - ['blocksize']: max size for each data block
        - ['mode']:      access mode for the new file
    """
    debug = False
    requiredArgs = ['workdir', 'slavedest', 'reader', 'blocksize']

    def setup(self, args):
        self.workdir = args['workdir']
        self.filename = args['slavedest']
        self.reader = args['reader']
        self.bytes_remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.mode = args['mode']
        self.stderr = None
        self.rc = 0

    def start(self):
        if self.debug:
            log.msg('SlaveFileDownloadCommand starting')

        # Open file
        self.path = os.path.join(self.builder.basedir,
                                 self.workdir,
                                 os.path.expanduser(self.filename))

        dirname = os.path.dirname(self.path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        try:
            self.fp = open(self.path, 'wb')
            if self.debug:
                log.msg("Opened '%s' for download" % self.path)
            if self.mode is not None:
                # note: there is a brief window during which the new file
                # will have the buildslave's default (umask) mode before we
                # set the new one. Don't use this mode= feature to keep files
                # private: use the buildslave's umask for that instead. (it
                # is possible to call os.umask() before and after the open()
                # call, but cleaning up from exceptions properly is more of a
                # nuisance that way).
                os.chmod(self.path, self.mode)
        except IOError:
            # TODO: this still needs cleanup
            self.fp = None
            self.stderr = "Cannot open file '%s' for download" % self.path
            self.rc = 1
            if self.debug:
                log.msg("Cannot open file '%s' for download" % self.path)

        d = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)

        def _close(res):
            # close the file, but pass through any errors from _loop
            d1 = self.reader.callRemote('close')
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
                log.msg('SlaveFileDownloadCommand._readBlock(): end')
            return True

        length = self.blocksize
        if self.bytes_remaining is not None and length > self.bytes_remaining:
            length = self.bytes_remaining

        if length <= 0:
            if self.stderr is None:
                self.stderr = "Maximum filesize reached, truncating file '%s'" \
                    % self.path
                self.rc = 1
            return True
        else:
            d = self.reader.callRemote('read', length)
            d.addCallback(self._writeData)
            return d

    def _writeData(self, data):
        if self.debug:
            log.msg('SlaveFileDownloadCommand._readBlock(): readlen=%d' %
                    len(data))
        if len(data) == 0:
            return True

        if self.bytes_remaining is not None:
            self.bytes_remaining = self.bytes_remaining - len(data)
            assert self.bytes_remaining >= 0
        self.fp.write(data)
        return False

    def finished(self, res):
        if self.fp is not None:
            self.fp.close()

        return TransferCommand.finished(self, res)
