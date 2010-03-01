import os, tarfile, tempfile

from twisted.python import log
from twisted.internet import reactor, defer

from buildbot.slave.commands.base import Command, command_version
from buildbot.slave.commands.registry import registerSlaveCommand

class SlaveFileUploadCommand(Command):
    """
    Upload a file from slave to build master
    Arguments:

        - ['workdir']:   base directory to use
        - ['slavesrc']:  name of the slave-side file to read from
        - ['writer']:    RemoteReference to a transfer._FileWriter object
        - ['maxsize']:   max size (in bytes) of file to write
        - ['blocksize']: max size for each data block
    """
    debug = False

    def setup(self, args):
        self.workdir = args['workdir']
        self.filename = args['slavesrc']
        self.writer = args['writer']
        self.remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.stderr = None
        self.rc = 0

    def start(self):
        if self.debug:
            log.msg('SlaveFileUploadCommand started')

        # Open file
        self.path = os.path.join(self.builder.basedir,
                                 self.workdir,
                                 os.path.expanduser(self.filename))
        try:
            self.fp = open(self.path, 'rb')
            if self.debug:
                log.msg('Opened %r for upload' % self.path)
        except:
            # TODO: this needs cleanup
            self.fp = None
            self.stderr = 'Cannot open file %r for upload' % self.path
            self.rc = 1
            if self.debug:
                log.msg('Cannot open file %r for upload' % self.path)

        self.sendStatus({'header': "sending %s" % self.path})

        d = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)
        def _close(res):
            # close the file, but pass through any errors from _loop
            d1 = self.writer.callRemote("close")
            d1.addErrback(log.err)
            d1.addCallback(lambda ignored: res)
            return d1
        d.addBoth(_close)
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
                self.stderr = 'Maximum filesize reached, truncating file %r' \
                                % self.path
                self.rc = 1
            data = ''
        else:
            data = self.fp.read(length)

        if self.debug:
            log.msg('SlaveFileUploadCommand._writeBlock(): '+
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

    def interrupt(self):
        if self.debug:
            log.msg('interrupted')
        if self.interrupted:
            return
        if self.stderr is None:
            self.stderr = 'Upload of %r interrupted' % self.path
            self.rc = 1
        self.interrupted = True
        # the next _writeBlock call will notice the .interrupted flag

    def finished(self, res):
        if self.debug:
            log.msg('finished: stderr=%r, rc=%r' % (self.stderr, self.rc))
        if self.stderr is None:
            self.sendStatus({'rc': self.rc})
        else:
            self.sendStatus({'stderr': self.stderr, 'rc': self.rc})
        return res

registerSlaveCommand("uploadFile", SlaveFileUploadCommand, command_version)


class SlaveDirectoryUploadCommand(SlaveFileUploadCommand):
    """
    Upload a directory from slave to build master
    Arguments:

        - ['workdir']:   base directory to use
        - ['slavesrc']:  name of the slave-side directory to read from
        - ['writer']:    RemoteReference to a transfer._DirectoryWriter object
        - ['maxsize']:   max size (in bytes) of file to write
        - ['blocksize']: max size for each data block
        - ['compress']:  one of [None, 'bz2', 'gz']
    """
    debug = True

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
            mode='w|bz2'
        elif self.compress == 'gz':
            mode='w|gz'
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
            # unpack the archive, but pass through any errors from _loop
            d1 = self.writer.callRemote("unpack")
            d1.addErrback(log.err)
            d1.addCallback(lambda ignored: res)
            return d1
        d.addCallback(unpack)
        d.addBoth(self.finished)
        return d

    def finished(self, res):
        self.fp.close()
        os.remove(self.tarname)
        if self.debug:
            log.msg('finished: stderr=%r, rc=%r' % (self.stderr, self.rc))
        if self.stderr is None:
            self.sendStatus({'rc': self.rc})
        else:
            self.sendStatus({'stderr': self.stderr, 'rc': self.rc})
        return res

registerSlaveCommand("uploadDirectory", SlaveDirectoryUploadCommand, command_version)


class SlaveFileDownloadCommand(Command):
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
                log.msg('Opened %r for download' % self.path)
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
            self.stderr = 'Cannot open file %r for download' % self.path
            self.rc = 1
            if self.debug:
                log.msg('Cannot open file %r for download' % self.path)

        d = defer.Deferred()
        self._reactor.callLater(0, self._loop, d)
        def _close(res):
            # close the file, but pass through any errors from _loop
            d1 = self.reader.callRemote('close')
            d1.addErrback(log.err)
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
                self.stderr = 'Maximum filesize reached, truncating file %r' \
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

    def interrupt(self):
        if self.debug:
            log.msg('interrupted')
        if self.interrupted:
            return
        if self.stderr is None:
            self.stderr = 'Download of %r interrupted' % self.path
            self.rc = 1
        self.interrupted = True
        # now we wait for the next read request to return. _readBlock will
        # abandon the file when it sees self.interrupted set.

    def finished(self, res):
        if self.fp is not None:
            self.fp.close()

        if self.debug:
            log.msg('finished: stderr=%r, rc=%r' % (self.stderr, self.rc))
        if self.stderr is None:
            self.sendStatus({'rc': self.rc})
        else:
            self.sendStatus({'stderr': self.stderr, 'rc': self.rc})
        return res

registerSlaveCommand("downloadFile", SlaveFileDownloadCommand, command_version)



