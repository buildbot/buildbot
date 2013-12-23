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

from __future__ import with_statement


import os.path
import stat
import tarfile
import tempfile
try:
    from cStringIO import StringIO
    assert StringIO
except ImportError:
    from StringIO import StringIO
from buildbot import config
from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.process import buildstep
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SKIPPED
from buildbot.process.buildstep import SUCCESS
from buildbot.util import json
from buildbot.util.eventual import eventually
from twisted.internet import defer
from twisted.python import log
from twisted.spread import pb


class _FileWriter(pb.Referenceable):

    """
    Helper class that acts as a file-object with write access
    """

    def __init__(self, destfile, maxsize, mode):
        # Create missing directories.
        destfile = os.path.abspath(destfile)
        dirname = os.path.dirname(destfile)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        self.destfile = destfile
        self.mode = mode
        fd, self.tmpname = tempfile.mkstemp(dir=dirname)
        self.fp = os.fdopen(fd, 'wb')
        self.remaining = maxsize

    def remote_write(self, data):
        """
        Called from remote slave to write L{data} to L{fp} within boundaries
        of L{maxsize}

        @type  data: C{string}
        @param data: String of data to write
        """
        if self.remaining is not None:
            if len(data) > self.remaining:
                data = data[:self.remaining]
            self.fp.write(data)
            self.remaining = self.remaining - len(data)
        else:
            self.fp.write(data)

    def remote_utime(self, accessed_modified):
        os.utime(self.destfile, accessed_modified)

    def remote_close(self):
        """
        Called by remote slave to state that no more data will be transfered
        """
        self.fp.close()
        self.fp = None
        # on windows, os.rename does not automatically unlink, so do it manually
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        os.rename(self.tmpname, self.destfile)
        self.tmpname = None
        if self.mode is not None:
            os.chmod(self.destfile, self.mode)

    def cancel(self):
        # unclean shutdown, the file is probably truncated, so delete it
        # altogether rather than deliver a corrupted file
        fp = getattr(self, "fp", None)
        if fp:
            fp.close()
            if self.destfile and os.path.exists(self.destfile):
                os.unlink(self.destfile)
            if self.tmpname and os.path.exists(self.tmpname):
                os.unlink(self.tmpname)


def _extractall(self, path=".", members=None):
    """Fallback extractall method for TarFile, in case it doesn't have its own."""

    import copy

    directories = []

    if members is None:
        members = self

    for tarinfo in members:
        if tarinfo.isdir():
            # Extract directories with a safe mode.
            directories.append(tarinfo)
            tarinfo = copy.copy(tarinfo)
            tarinfo.mode = 0700
        self.extract(tarinfo, path)

    # Reverse sort directories.
    directories.sort(lambda a, b: cmp(a.name, b.name))
    directories.reverse()

    # Set correct owner, mtime and filemode on directories.
    for tarinfo in directories:
        dirpath = os.path.join(path, tarinfo.name)
        try:
            self.chown(tarinfo, dirpath)
            self.utime(tarinfo, dirpath)
            self.chmod(tarinfo, dirpath)
        except tarfile.ExtractError, e:
            if self.errorlevel > 1:
                raise
            else:
                self._dbg(1, "tarfile: %s" % e)


class _DirectoryWriter(_FileWriter):

    """
    A DirectoryWriter is implemented as a FileWriter, with an added post-processing
    step to unpack the archive, once the transfer has completed.
    """

    def __init__(self, destroot, maxsize, compress, mode):
        self.destroot = destroot
        self.compress = compress

        self.fd, self.tarname = tempfile.mkstemp()
        os.close(self.fd)

        _FileWriter.__init__(self, self.tarname, maxsize, mode)

    def remote_unpack(self):
        """
        Called by remote slave to state that no more data will be transfered
        """
        # Make sure remote_close is called, otherwise atomic rename wont happen
        self.remote_close()

        # Map configured compression to a TarFile setting
        if self.compress == 'bz2':
            mode = 'r|bz2'
        elif self.compress == 'gz':
            mode = 'r|gz'
        else:
            mode = 'r'

        # Support old python
        if not hasattr(tarfile.TarFile, 'extractall'):
            tarfile.TarFile.extractall = _extractall

        # Unpack archive and clean up after self
        archive = tarfile.open(name=self.tarname, mode=mode)
        archive.extractall(path=self.destroot)
        archive.close()
        os.remove(self.tarname)


def makeStatusRemoteCommand(step, remote_command, args):
    self = buildstep.RemoteCommand(remote_command, args, decodeRC={None: SUCCESS, 0: SUCCESS})
    callback = lambda arg: step.step_status.addLog('stdio')
    self.useLogDelayed('stdio', callback, True)
    return self


class _TransferBuildStep(BuildStep):

    """
    Base class for FileUpload and FileDownload to factor out common
    functionality.
    """
    DEFAULT_WORKDIR = "build"           # is this redundant?

    renderables = ['workdir']

    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, workdir=None, **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.workdir = workdir

    # Check that buildslave version used have implementation for
    # a remote command. Raise exception if buildslave is to old.
    def checkSlaveVersion(self, command):
        if not self.slaveVersion(command):
            message = "slave is too old, does not know about %s" % command
            raise BuildSlaveTooOldError(message)

    def setDefaultWorkdir(self, workdir):
        if self.workdir is None:
            self.workdir = workdir

    def _getWorkdir(self):
        if self.workdir is None:
            workdir = self.DEFAULT_WORKDIR
        else:
            workdir = self.workdir
        return workdir

    def runTransferCommand(self, cmd, writer=None):
        # Run a transfer step, add a callback to extract the command status,
        # add an error handler that cancels the writer.
        self.cmd = cmd
        d = self.runCommand(cmd)

        @d.addCallback
        def checkResult(_):
            if cmd.didFail():
                writer.cancel()
            return FAILURE if cmd.didFail() else SUCCESS

        @d.addErrback
        def cancel(res):
            if writer:
                writer.cancel()
            return res

        return d

    def interrupt(self, reason):
        self.addCompleteLog('interrupt', str(reason))
        if self.cmd:
            d = self.cmd.interrupt(reason)
            return d


class FileUpload(_TransferBuildStep):

    name = 'upload'

    renderables = ['slavesrc', 'masterdest', 'url']

    def __init__(self, slavesrc, masterdest,
                 workdir=None, maxsize=None, blocksize=16 * 1024, mode=None,
                 keepstamp=False, url=None,
                 **buildstep_kwargs):
        _TransferBuildStep.__init__(self, workdir=workdir, **buildstep_kwargs)

        self.slavesrc = slavesrc
        self.masterdest = masterdest
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error(
                'mode must be an integer or None')
        self.mode = mode
        self.keepstamp = keepstamp
        self.url = url

    def start(self):
        self.checkSlaveVersion("uploadFile")

        source = self.slavesrc
        masterdest = self.masterdest
        # we rely upon the fact that the buildmaster runs chdir'ed into its
        # basedir to make sure that relative paths in masterdest are expanded
        # properly. TODO: maybe pass the master's basedir all the way down
        # into the BuildStep so we can do this better.
        masterdest = os.path.expanduser(masterdest)
        log.msg("FileUpload started, from slave %r to master %r"
                % (source, masterdest))

        self.step_status.setText(['uploading', os.path.basename(source)])
        if self.url is not None:
            self.addURL(os.path.basename(masterdest), self.url)

        # we use maxsize to limit the amount of data on both sides
        fileWriter = _FileWriter(masterdest, self.maxsize, self.mode)

        if self.keepstamp and self.slaveVersionIsOlderThan("uploadFile", "2.13"):
            m = ("This buildslave (%s) does not support preserving timestamps. "
                 "Please upgrade the buildslave." % self.build.slavename)
            raise BuildSlaveTooOldError(m)

        # default arguments
        args = {
            'slavesrc': source,
            'workdir': self._getWorkdir(),
            'writer': fileWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'keepstamp': self.keepstamp,
        }

        cmd = makeStatusRemoteCommand(self, 'uploadFile', args)
        d = self.runTransferCommand(cmd, fileWriter)
        d.addCallback(self.finished).addErrback(self.failed)


class DirectoryUpload(_TransferBuildStep):

    name = 'upload'

    renderables = ['slavesrc', 'masterdest', 'url']

    def __init__(self, slavesrc, masterdest,
                 workdir=None, maxsize=None, blocksize=16 * 1024,
                 compress=None, url=None, **buildstep_kwargs):
        _TransferBuildStep.__init__(self, workdir=workdir, **buildstep_kwargs)

        self.slavesrc = slavesrc
        self.masterdest = masterdest
        self.maxsize = maxsize
        self.blocksize = blocksize
        if compress not in (None, 'gz', 'bz2'):
            config.error(
                "'compress' must be one of None, 'gz', or 'bz2'")
        self.compress = compress
        self.url = url

    def start(self):
        self.checkSlaveVersion("uploadDirectory")

        source = self.slavesrc
        masterdest = self.masterdest
        # we rely upon the fact that the buildmaster runs chdir'ed into its
        # basedir to make sure that relative paths in masterdest are expanded
        # properly. TODO: maybe pass the master's basedir all the way down
        # into the BuildStep so we can do this better.
        masterdest = os.path.expanduser(masterdest)
        log.msg("DirectoryUpload started, from slave %r to master %r"
                % (source, masterdest))

        self.step_status.setText(['uploading', os.path.basename(source)])
        if self.url is not None:
            self.addURL(os.path.basename(masterdest), self.url)

        # we use maxsize to limit the amount of data on both sides
        dirWriter = _DirectoryWriter(masterdest, self.maxsize, self.compress, 0600)

        # default arguments
        args = {
            'slavesrc': source,
            'workdir': self._getWorkdir(),
            'writer': dirWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'compress': self.compress
        }

        cmd = makeStatusRemoteCommand(self, 'uploadDirectory', args)
        d = self.runTransferCommand(cmd, dirWriter)
        d.addCallback(self.finished).addErrback(self.failed)


class MultipleFileUpload(_TransferBuildStep):

    name = 'upload'

    renderables = ['slavesrcs', 'masterdest', 'url']

    def __init__(self, slavesrcs, masterdest,
                 workdir=None, maxsize=None, blocksize=16 * 1024,
                 mode=None, compress=None, keepstamp=False, url=None, **buildstep_kwargs):
        _TransferBuildStep.__init__(self, workdir=workdir, **buildstep_kwargs)

        self.slavesrcs = slavesrcs
        self.masterdest = masterdest
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error(
                'mode must be an integer or None')
        self.mode = mode
        if compress not in (None, 'gz', 'bz2'):
            config.error(
                "'compress' must be one of None, 'gz', or 'bz2'")
        self.compress = compress
        self.keepstamp = keepstamp
        self.url = url

    def uploadFile(self, source, masterdest):
        fileWriter = _FileWriter(masterdest, self.maxsize, self.mode)

        args = {
            'slavesrc': source,
            'workdir': self._getWorkdir(),
            'writer': fileWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'keepstamp': self.keepstamp,
        }

        cmd = makeStatusRemoteCommand(self, 'uploadFile', args)
        return self.runTransferCommand(cmd, fileWriter)

    def uploadDirectory(self, source, masterdest):
        dirWriter = _DirectoryWriter(masterdest, self.maxsize, self.compress, 0600)

        args = {
            'slavesrc': source,
            'workdir': self._getWorkdir(),
            'writer': dirWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'compress': self.compress
        }

        cmd = makeStatusRemoteCommand(self, 'uploadDirectory', args)
        return self.runTransferCommand(cmd, dirWriter)

    def startUpload(self, source, destdir):
        masterdest = os.path.join(destdir, os.path.basename(source))
        args = {
            'file': source,
            'workdir': self._getWorkdir()
        }

        cmd = makeStatusRemoteCommand(self, 'stat', args)
        d = self.runCommand(cmd)

        @d.addCallback
        def checkStat(_):
            s = cmd.updates['stat'][-1]
            if stat.S_ISDIR(s[stat.ST_MODE]):
                return self.uploadDirectory(source, masterdest)
            elif stat.S_ISREG(s[stat.ST_MODE]):
                return self.uploadFile(source, masterdest)
            else:
                return defer.fail('%r is neither a regular file, nor a directory' % source)

        @d.addCallback
        def uploadDone(result):
            d = defer.maybeDeferred(self.uploadDone, result, source, masterdest)
            d.addCallback(lambda _: result)
            return d

        return d

    def uploadDone(self, result, source, masterdest):
        pass

    def allUploadsDone(self, result, sources, masterdest):
        if self.url is not None:
            self.addURL(os.path.basename(masterdest), self.url)

    def start(self):
        self.checkSlaveVersion("uploadDirectory")
        self.checkSlaveVersion("uploadFile")
        self.checkSlaveVersion("stat")

        masterdest = os.path.expanduser(self.masterdest)
        sources = self.slavesrcs

        if self.keepstamp and self.slaveVersionIsOlderThan("uploadFile", "2.13"):
            m = ("This buildslave (%s) does not support preserving timestamps. "
                 "Please upgrade the buildslave." % self.build.slavename)
            raise BuildSlaveTooOldError(m)

        if not sources:
            return self.finished(SKIPPED)

        @defer.inlineCallbacks
        def uploadSources():
            for source in sources:
                result = yield self.startUpload(source, masterdest)
                if result == FAILURE:
                    yield defer.returnValue(FAILURE)
            yield defer.returnValue(SUCCESS)

        d = uploadSources()

        @d.addCallback
        def allUploadsDone(result):
            d = defer.maybeDeferred(self.allUploadsDone, result, sources, masterdest)
            d.addCallback(lambda _: result)
            return d

        log.msg("MultipleFileUpload started, from slave %r to master %r"
                % (sources, masterdest))

        nsrcs = len(sources)
        self.step_status.setText(['uploading', '%d %s' % (nsrcs, 'file' if nsrcs == 1 else 'files')])

        d.addCallback(self.finished).addErrback(self.failed)

    def finished(self, result):
        return BuildStep.finished(self, result)


class _FileReader(pb.Referenceable):

    """
    Helper class that acts as a file-object with read access
    """

    def __init__(self, fp):
        self.fp = fp

    def remote_read(self, maxlength):
        """
        Called from remote slave to read at most L{maxlength} bytes of data

        @type  maxlength: C{integer}
        @param maxlength: Maximum number of data bytes that can be returned

        @return: Data read from L{fp}
        @rtype: C{string} of bytes read from file
        """
        if self.fp is None:
            return ''

        data = self.fp.read(maxlength)
        return data

    def remote_close(self):
        """
        Called by remote slave to state that no more data will be transfered
        """
        if self.fp is not None:
            self.fp.close()
            self.fp = None


class FileDownload(_TransferBuildStep):

    name = 'download'

    renderables = ['mastersrc', 'slavedest']

    def __init__(self, mastersrc, slavedest,
                 workdir=None, maxsize=None, blocksize=16 * 1024, mode=None,
                 **buildstep_kwargs):
        _TransferBuildStep.__init__(self, workdir=workdir, **buildstep_kwargs)

        self.mastersrc = mastersrc
        self.slavedest = slavedest
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error(
                'mode must be an integer or None')
        self.mode = mode

    def start(self):
        self.checkSlaveVersion("downloadFile")

        # we are currently in the buildmaster's basedir, so any non-absolute
        # paths will be interpreted relative to that
        source = os.path.expanduser(self.mastersrc)
        slavedest = self.slavedest
        log.msg("FileDownload started, from master %r to slave %r" %
                (source, slavedest))

        self.step_status.setText(['downloading', "to",
                                  os.path.basename(slavedest)])

        # setup structures for reading the file
        try:
            fp = open(source, 'rb')
        except IOError:
            # if file does not exist, bail out with an error
            self.addCompleteLog('stderr',
                                'File %r not available at master' % source)
            # TODO: once BuildStep.start() gets rewritten to use
            # maybeDeferred, just re-raise the exception here.
            eventually(BuildStep.finished, self, FAILURE)
            return
        fileReader = _FileReader(fp)

        # default arguments
        args = {
            'slavedest': slavedest,
            'maxsize': self.maxsize,
            'reader': fileReader,
            'blocksize': self.blocksize,
            'workdir': self._getWorkdir(),
            'mode': self.mode,
        }

        cmd = makeStatusRemoteCommand(self, 'downloadFile', args)
        d = self.runTransferCommand(cmd)
        d.addCallback(self.finished).addErrback(self.failed)


class StringDownload(_TransferBuildStep):

    name = 'string_download'

    renderables = ['slavedest', 's']

    def __init__(self, s, slavedest,
                 workdir=None, maxsize=None, blocksize=16 * 1024, mode=None,
                 **buildstep_kwargs):
        _TransferBuildStep.__init__(self, workdir=workdir, **buildstep_kwargs)

        self.s = s
        self.slavedest = slavedest
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error(
                "StringDownload step's mode must be an integer or None,"
                " got '%s'" % mode)
        self.mode = mode

    def start(self):
        # we use 'downloadFile' remote command on the slave
        self.checkSlaveVersion("downloadFile")

        # we are currently in the buildmaster's basedir, so any non-absolute
        # paths will be interpreted relative to that
        slavedest = self.slavedest
        log.msg("StringDownload started, from master to slave %r" % slavedest)

        self.step_status.setText(['downloading', "to",
                                  os.path.basename(slavedest)])

        # setup structures for reading the file
        fp = StringIO(self.s)
        fileReader = _FileReader(fp)

        # default arguments
        args = {
            'slavedest': slavedest,
            'maxsize': self.maxsize,
            'reader': fileReader,
            'blocksize': self.blocksize,
            'workdir': self._getWorkdir(),
            'mode': self.mode,
        }

        cmd = makeStatusRemoteCommand(self, 'downloadFile', args)
        d = self.runTransferCommand(cmd)
        d.addCallback(self.finished).addErrback(self.failed)


class JSONStringDownload(StringDownload):

    name = "json_download"

    def __init__(self, o, slavedest, **buildstep_kwargs):
        if 's' in buildstep_kwargs:
            del buildstep_kwargs['s']
        s = json.dumps(o)
        StringDownload.__init__(self, s=s, slavedest=slavedest, **buildstep_kwargs)


class JSONPropertiesDownload(StringDownload):

    name = "json_properties_download"

    def __init__(self, slavedest, **buildstep_kwargs):
        self.super_class = StringDownload
        if 's' in buildstep_kwargs:
            del buildstep_kwargs['s']
        StringDownload.__init__(self, s=None, slavedest=slavedest, **buildstep_kwargs)

    def start(self):
        properties = self.build.getProperties()
        props = {}
        for key, value, source in properties.asList():
            props[key] = value

        self.s = json.dumps(dict(
            properties=props,
            sourcestamp=self.build.getSourceStamp().asDict(),
        ),
        )
        return self.super_class.start(self)
