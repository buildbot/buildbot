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


import os.path, tarfile, tempfile
try:
    from cStringIO import StringIO
    assert StringIO
except ImportError:
    from StringIO import StringIO
from twisted.spread import pb
from twisted.python import log
from buildbot.process import buildstep
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE, SKIPPED
from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.util import json
from buildbot.util.eventual import eventually
from buildbot import config


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
        os.utime(self.destfile,accessed_modified)

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
            mode='r|bz2'
        elif self.compress == 'gz':
            mode='r|gz'
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
    self = buildstep.RemoteCommand(remote_command, args,  decodeRC={None:SUCCESS, 0:SUCCESS})
    callback = lambda arg: step.step_status.addLog('stdio')
    self.useLogDelayed('stdio', callback, True)
    return self

class _TransferBuildStep(BuildStep):
    """
    Base class for FileUpload and FileDownload to factor out common
    functionality.
    """
    DEFAULT_WORKDIR = "build"           # is this redundant?

    renderables = [ 'workdir' ]

    haltOnFailure = True
    flunkOnFailure = True

    def setDefaultWorkdir(self, workdir):
        if self.workdir is None:
            self.workdir = workdir

    def _getWorkdir(self):
        if self.workdir is None:
            workdir = self.DEFAULT_WORKDIR
        else:
            workdir = self.workdir
        return workdir

    def interrupt(self, reason):
        self.addCompleteLog('interrupt', str(reason))
        if self.cmd:
            d = self.cmd.interrupt(reason)
            return d

    def finished(self, result):
        # Subclasses may choose to skip a transfer. In those cases, self.cmd
        # will be None, and we should just let BuildStep.finished() handle
        # the rest
        if result == SKIPPED:
            return BuildStep.finished(self, SKIPPED)

        if self.cmd.didFail():
            return BuildStep.finished(self, FAILURE)
        return BuildStep.finished(self, SUCCESS)


class FileUpload(_TransferBuildStep):

    name = 'upload'

    renderables = [ 'slavesrc', 'masterdest', 'url' ]

    def __init__(self, slavesrc, masterdest,
                 workdir=None, maxsize=None, blocksize=16*1024, mode=None,
                 keepstamp=False, url=None,
                 **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)

        self.slavesrc = slavesrc
        self.masterdest = masterdest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error(
                'mode must be an integer or None')
        self.mode = mode
        self.keepstamp = keepstamp
        self.url = url

    def start(self):
        version = self.slaveVersion("uploadFile")

        if not version:
            m = "slave is too old, does not know about uploadFile"
            raise BuildSlaveTooOldError(m)

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

        if self.keepstamp and self.slaveVersionIsOlderThan("uploadFile","2.13"):
            m = ("This buildslave (%s) does not support preserving timestamps. "
                 "Please upgrade the buildslave." % self.build.slavename )
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

        self.cmd = makeStatusRemoteCommand(self, 'uploadFile', args)
        d = self.runCommand(self.cmd)
        @d.addErrback
        def cancel(res):
            fileWriter.cancel()
            return res
        d.addCallback(self.finished).addErrback(self.failed)


class DirectoryUpload(_TransferBuildStep):

    name = 'upload'

    renderables = [ 'slavesrc', 'masterdest', 'url' ]

    def __init__(self, slavesrc, masterdest,
                 workdir=None, maxsize=None, blocksize=16*1024,
                 compress=None, url=None, **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)

        self.slavesrc = slavesrc
        self.masterdest = masterdest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        if compress not in (None, 'gz', 'bz2'):
            config.error(
                "'compress' must be one of None, 'gz', or 'bz2'")
        self.compress = compress
        self.url = url

    def start(self):
        version = self.slaveVersion("uploadDirectory")

        if not version:
            m = "slave is too old, does not know about uploadDirectory"
            raise BuildSlaveTooOldError(m)

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

        self.cmd = makeStatusRemoteCommand(self, 'uploadDirectory', args)
        d = self.runCommand(self.cmd)
        @d.addErrback
        def cancel(res):
            dirWriter.cancel()
            return res
        d.addCallback(self.finished).addErrback(self.failed)

    def finished(self, result):
        # Subclasses may choose to skip a transfer. In those cases, self.cmd
        # will be None, and we should just let BuildStep.finished() handle
        # the rest
        if result == SKIPPED:
            return BuildStep.finished(self, SKIPPED)

        if self.cmd.didFail():
            return BuildStep.finished(self, FAILURE)
        return BuildStep.finished(self, SUCCESS)


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

    renderables = [ 'mastersrc', 'slavedest' ]

    def __init__(self, mastersrc, slavedest,
                 workdir=None, maxsize=None, blocksize=16*1024, mode=None,
                 **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)

        self.mastersrc = mastersrc
        self.slavedest = slavedest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error(
                'mode must be an integer or None')
        self.mode = mode

    def start(self):
        version = self.slaveVersion("downloadFile")
        if not version:
            m = "slave is too old, does not know about downloadFile"
            raise BuildSlaveTooOldError(m)

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

        self.cmd = makeStatusRemoteCommand(self, 'downloadFile', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

class StringDownload(_TransferBuildStep):

    name = 'string_download'

    renderables = [ 'slavedest', 's' ]

    def __init__(self, s, slavedest,
                 workdir=None, maxsize=None, blocksize=16*1024, mode=None,
                 **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)

        self.s = s
        self.slavedest = slavedest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error(
                'mode must be an integer or None')
        self.mode = mode

    def start(self):
        version = self.slaveVersion("downloadFile")
        if not version:
            m = "slave is too old, does not know about downloadFile"
            raise BuildSlaveTooOldError(m)

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

        self.cmd = makeStatusRemoteCommand(self, 'downloadFile', args)
        d = self.runCommand(self.cmd)
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
