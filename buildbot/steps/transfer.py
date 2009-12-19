# -*- test-case-name: buildbot.test.test_transfer -*-

import os.path, tarfile, tempfile
from twisted.internet import reactor
from twisted.spread import pb
from twisted.python import log
from buildbot.process.buildstep import RemoteCommand, BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE, SKIPPED
from buildbot.interfaces import BuildSlaveTooOldError


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
        self.fp = open(destfile, "wb")
        if mode is not None:
            os.chmod(destfile, mode)
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

    def remote_close(self):
        """
        Called by remote slave to state that no more data will be transfered
        """
        self.fp.close()
        self.fp = None

    def __del__(self):
        # unclean shutdown, the file is probably truncated, so delete it
        # altogether rather than deliver a corrupted file
        fp = getattr(self, "fp", None)
        if fp:
            fp.close()
            os.unlink(self.destfile)


def _extractall(self, path=".", members=None):
    """Fallback extractall method for TarFile, in case it doesn't have its own."""

    import copy
    import operator

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

        self.fd, self.tarname = tempfile.mkstemp()
        self.compress = compress
        _FileWriter.__init__(self, self.tarname, maxsize, mode)

    def remote_unpack(self):
        """
        Called by remote slave to state that no more data will be transfered
        """
        if self.fp:
            self.fp.close()
            self.fp = None
        fileobj = os.fdopen(self.fd, 'r')
        if self.compress == 'bz2':
            mode='r|bz2'
        elif self.compress == 'gz':
            mode='r|gz'
        else:
            mode = 'r'
        if not hasattr(tarfile.TarFile, 'extractall'):
            tarfile.TarFile.extractall = _extractall
        archive = tarfile.open(name=self.tarname, mode=mode, fileobj=fileobj)
        archive.extractall(path=self.destroot)
        os.remove(self.tarname)


class StatusRemoteCommand(RemoteCommand):
    def __init__(self, remote_command, args):
        RemoteCommand.__init__(self, remote_command, args)

        self.rc = None
        self.stderr = ''

    def remoteUpdate(self, update):
        #log.msg('StatusRemoteCommand: update=%r' % update)
        if 'rc' in update:
            self.rc = update['rc']
        if 'stderr' in update:
            self.stderr = self.stderr + update['stderr'] + '\n'

class _TransferBuildStep(BuildStep):
    """
    Base class for FileUpload and FileDownload to factor out common
    functionality.
    """
    DEFAULT_WORKDIR = "build"           # is this redundant?

    def setDefaultWorkdir(self, workdir):
        if self.workdir is None:
            self.workdir = workdir

    def _getWorkdir(self):
        properties = self.build.getProperties()
        if self.workdir is None:
            workdir = self.DEFAULT_WORKDIR
        else:
            workdir = self.workdir
        return properties.render(workdir)

    def finished(self, result):
        # Subclasses may choose to skip a transfer. In those cases, self.cmd
        # will be None, and we should just let BuildStep.finished() handle
        # the rest
        if result == SKIPPED:
            return BuildStep.finished(self, SKIPPED)
        if self.cmd.stderr != '':
            self.addCompleteLog('stderr', self.cmd.stderr)

        if self.cmd.rc is None or self.cmd.rc == 0:
            return BuildStep.finished(self, SUCCESS)
        return BuildStep.finished(self, FAILURE)


class FileUpload(_TransferBuildStep):
    """
    Build step to transfer a file from the slave to the master.

    arguments:

    - ['slavesrc']   filename of source file at slave, relative to workdir
    - ['masterdest'] filename of destination file at master
    - ['workdir']    string with slave working directory relative to builder
                     base dir, default 'build'
    - ['maxsize']    maximum size of the file, default None (=unlimited)
    - ['blocksize']  maximum size of each block being transfered
    - ['mode']       file access mode for the resulting master-side file.
                     The default (=None) is to leave it up to the umask of
                     the buildmaster process.

    """

    name = 'upload'

    def __init__(self, slavesrc, masterdest,
                 workdir=None, maxsize=None, blocksize=16*1024, mode=None,
                 **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.addFactoryArguments(slavesrc=slavesrc,
                                 masterdest=masterdest,
                                 workdir=workdir,
                                 maxsize=maxsize,
                                 blocksize=blocksize,
                                 mode=mode,
                                 )

        self.slavesrc = slavesrc
        self.masterdest = masterdest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        assert isinstance(mode, (int, type(None)))
        self.mode = mode

    def start(self):
        version = self.slaveVersion("uploadFile")
        properties = self.build.getProperties()

        if not version:
            m = "slave is too old, does not know about uploadFile"
            raise BuildSlaveTooOldError(m)

        source = properties.render(self.slavesrc)
        masterdest = properties.render(self.masterdest)
        # we rely upon the fact that the buildmaster runs chdir'ed into its
        # basedir to make sure that relative paths in masterdest are expanded
        # properly. TODO: maybe pass the master's basedir all the way down
        # into the BuildStep so we can do this better.
        masterdest = os.path.expanduser(masterdest)
        log.msg("FileUpload started, from slave %r to master %r"
                % (source, masterdest))

        self.step_status.setText(['uploading', os.path.basename(source)])

        # we use maxsize to limit the amount of data on both sides
        fileWriter = _FileWriter(masterdest, self.maxsize, self.mode)

        # default arguments
        args = {
            'slavesrc': source,
            'workdir': self._getWorkdir(),
            'writer': fileWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            }

        self.cmd = StatusRemoteCommand('uploadFile', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)


class DirectoryUpload(BuildStep):
    """
    Build step to transfer a directory from the slave to the master.

    arguments:

    - ['slavesrc']   name of source directory at slave, relative to workdir
    - ['masterdest'] name of destination directory at master
    - ['workdir']    string with slave working directory relative to builder
                     base dir, default 'build'
    - ['maxsize']    maximum size of the compressed tarfile containing the
                     whole directory
    - ['blocksize']  maximum size of each block being transfered
    - ['compress']   compression type to use: one of [None, 'gz', 'bz2']

    """

    name = 'upload'

    def __init__(self, slavesrc, masterdest,
                 workdir="build", maxsize=None, blocksize=16*1024,
                 compress=None, **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.addFactoryArguments(slavesrc=slavesrc,
                                 masterdest=masterdest,
                                 workdir=workdir,
                                 maxsize=maxsize,
                                 blocksize=blocksize,
                                 compress=compress,
                                 )

        self.slavesrc = slavesrc
        self.masterdest = masterdest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        assert compress in (None, 'gz', 'bz2')
        self.compress = compress

    def start(self):
        version = self.slaveVersion("uploadDirectory")
        properties = self.build.getProperties()

        if not version:
            m = "slave is too old, does not know about uploadDirectory"
            raise BuildSlaveTooOldError(m)

        source = properties.render(self.slavesrc)
        masterdest = properties.render(self.masterdest)
        # we rely upon the fact that the buildmaster runs chdir'ed into its
        # basedir to make sure that relative paths in masterdest are expanded
        # properly. TODO: maybe pass the master's basedir all the way down
        # into the BuildStep so we can do this better.
        masterdest = os.path.expanduser(masterdest)
        log.msg("DirectoryUpload started, from slave %r to master %r"
                % (source, masterdest))

        self.step_status.setText(['uploading', os.path.basename(source)])
        
        # we use maxsize to limit the amount of data on both sides
        dirWriter = _DirectoryWriter(masterdest, self.maxsize, self.compress, 0600)

        # default arguments
        args = {
            'slavesrc': source,
            'workdir': self.workdir,
            'writer': dirWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'compress': self.compress
            }

        self.cmd = StatusRemoteCommand('uploadDirectory', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

    def finished(self, result):
        # Subclasses may choose to skip a transfer. In those cases, self.cmd
        # will be None, and we should just let BuildStep.finished() handle
        # the rest
        if result == SKIPPED:
            return BuildStep.finished(self, SKIPPED)
        if self.cmd.stderr != '':
            self.addCompleteLog('stderr', self.cmd.stderr)

        if self.cmd.rc is None or self.cmd.rc == 0:
            return BuildStep.finished(self, SUCCESS)
        return BuildStep.finished(self, FAILURE)




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
    """
    Download the first 'maxsize' bytes of a file, from the buildmaster to the
    buildslave. Set the mode of the file

    Arguments::

     ['mastersrc'] filename of source file at master
     ['slavedest'] filename of destination file at slave
     ['workdir']   string with slave working directory relative to builder
                   base dir, default 'build'
     ['maxsize']   maximum size of the file, default None (=unlimited)
     ['blocksize'] maximum size of each block being transfered
     ['mode']      use this to set the access permissions of the resulting
                   buildslave-side file. This is traditionally an octal
                   integer, like 0644 to be world-readable (but not
                   world-writable), or 0600 to only be readable by
                   the buildslave account, or 0755 to be world-executable.
                   The default (=None) is to leave it up to the umask of
                   the buildslave process.

    """
    name = 'download'

    def __init__(self, mastersrc, slavedest,
                 workdir=None, maxsize=None, blocksize=16*1024, mode=None,
                 **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.addFactoryArguments(mastersrc=mastersrc,
                                 slavedest=slavedest,
                                 workdir=workdir,
                                 maxsize=maxsize,
                                 blocksize=blocksize,
                                 mode=mode,
                                 )

        self.mastersrc = mastersrc
        self.slavedest = slavedest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        assert isinstance(mode, (int, type(None)))
        self.mode = mode

    def start(self):
        properties = self.build.getProperties()

        version = self.slaveVersion("downloadFile")
        if not version:
            m = "slave is too old, does not know about downloadFile"
            raise BuildSlaveTooOldError(m)

        # we are currently in the buildmaster's basedir, so any non-absolute
        # paths will be interpreted relative to that
        source = os.path.expanduser(properties.render(self.mastersrc))
        slavedest = properties.render(self.slavedest)
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
            reactor.callLater(0, BuildStep.finished, self, FAILURE)
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

        self.cmd = StatusRemoteCommand('downloadFile', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

