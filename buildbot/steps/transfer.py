# -*- test-case-name: buildbot.test.test_transfer -*-

import os.path
from twisted.internet import reactor
from twisted.spread import pb
from twisted.python import log
from buildbot.process.buildstep import RemoteCommand, BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE


class _FileIO(pb.Referenceable):
    """
    Helper base class that acts as remote-accessible file-object
    """

    def __init__(self,fp):
        self.fp = fp

    def remote_close(self):
        """
        Called by remote slave to state that no more data will be transfered
        """
        if self.fp is not None:
            self.fp.close()
            self.fp = None

class _FileWriter(_FileIO):
    """
    Helper class that acts as a file-object with write access
    """

    def __init__(self,fp, maxsize=None):
        _FileIO.__init__(self,fp)
	self.maxsize = maxsize

    def remote_write(self,data):
	"""
	Called from remote slave to write L{data} to L{fp} within boundaries
	of L{maxsize}

	@type  data: C{string}
	@param data: String of data to write
	"""
        if self.fp is not None:
	    if self.maxsize is not None:
		if len(data) > self.maxsize:
		    data = data[:self.maxsize]
                self.fp.write(data)
		self.maxsize = self.maxsize - len(data)
	    else:
                self.fp.write(data)

class _FileReader(_FileIO):
    """
    Helper class that acts as a file-object with read access
    """

    def remote_read(self,maxlength):
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


class FileUpload(BuildStep):
    """
    Build step to transfer a file from the slave to the master.

    arguments:

    - ['slavesrc']   filename of source file at slave, relative to workdir
    - ['masterdest'] filename of destination file at master
    - ['workdir']    string with slave working directory relative to builder
                     base dir, default 'build'
    - ['maxsize']    maximum size of the file, default None (=unlimited)
    - ['blocksize']  maximum size of each block being transfered

    """

    name = 'upload'

    def __init__(self, build, slavesrc, masterdest,
                 workdir="build", maxsize=None, blocksize=16*1024,
                 **buildstep_kwargs):
        BuildStep.__init__(self, build, **buildstep_kwargs)

        self.slavesrc = slavesrc
        self.masterdest = masterdest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize

    def start(self):
        source = self.slavesrc
        masterdest = self.masterdest
        # we rely upon the fact that the buildmaster runs chdir'ed into its
        # basedir to make sure that relative paths in masterdest are expanded
        # properly. TODO: maybe pass the master's basedir all the way down
        # into the BuildStep so we can do this better.
        target = os.path.expanduser(masterdest)
        log.msg("FileUpload started, from slave %r to master %r"
                % (source, target))

        self.step_status.setColor('yellow')
        self.step_status.setText(['uploading', source])

        fp = open(self.masterdest, 'w')
        self.fileWriter = _FileWriter(fp)

        # default arguments
        args = {
            'slavesrc': source,
            'workdir': self.workdir,
            'writer': self.fileWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize
            }

        self.cmd = StatusRemoteCommand('uploadFile', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

    def finished(self,result):
        if self.cmd.stderr != '':
            self.addCompleteLog('stderr', self.cmd.stderr)

        self.fileWriter = None

        if self.cmd.rc is None or self.cmd.rc == 0:
            self.step_status.setColor('green')
            return BuildStep.finished(self, SUCCESS)
        self.step_status.setColor('red')
        return BuildStep.finished(self, FAILURE)

class FileDownload(BuildStep):
    """
    Build step to download a file
    arguments:

    ['mastersrc'] filename of source file at master
    ['slavedest'] filename of destination file at slave
    ['workdir']   string with slave working directory relative to builder
                  base dir, default 'build'
    ['maxsize']   maximum size of the file, default None (=unlimited)
    ['blocksize'] maximum size of each block being transfered

    """

    name = 'download'

    def __init__(self, build, mastersrc, slavedest,
                 workdir="build", maxsize=None, blocksize=16*1024,
                 **buildstep_kwargs):
        BuildStep.__init__(self, build, **buildstep_kwargs)

        self.mastersrc = mastersrc
        self.slavedest = slavedest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize

    def start(self):
        source = os.path.expanduser(self.mastersrc)
        slavedest = self.slavedest
        log.msg("FileDownload started, from master %r to slave %r" %
                (source, slavedest))

        self.step_status.setColor('yellow')
        self.step_status.setText(['downloading', slavedest])

        # If file does not exist, bail out with an error
        if not os.path.isfile(source):
            self.addCompleteLog('stderr',
                                'File %r not available at master' % source)
            reactor.callLater(0, self.reportFail)
            return

        # setup structures for reading the file
        fp = open(source, 'r')
        self.fileReader = _FileReader(fp)

        # default arguments
        args = {
            'slavedest': self.slavedest,
            'maxsize': self.maxsize,
            'reader': self.fileReader,
            'blocksize': self.blocksize,
            'workdir': self.workdir,
            }

        self.cmd = StatusRemoteCommand('downloadFile', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

    def finished(self,result):
        if self.cmd.stderr != '':
            self.addCompleteLog('stderr', self.cmd.stderr)

        self.fileReader = None

        if self.cmd.rc is None or self.cmd.rc == 0:
            self.step_status.setColor('green')
            return BuildStep.finished(self, SUCCESS)
        return self.reportFail()

    def reportFail(self):
        self.step_status.setColor('red')
        return BuildStep.finished(self, FAILURE)

