
from twisted.internet import reactor
from twisted.spread import pb
from buildbot.process.step import RemoteCommand, BuildStep
from buildbot.process.step import SUCCESS, FAILURE


class FileIO(pb.Referenceable):
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

class FileWriter(FileIO):
    """
    Helper class that acts as a file-object with write access
    """

    def __init__(self,fp, maxsize=None):
        FileIO.__init__(self,fp)
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

class FileReader(FileIO):
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

    def __init__(self, build, **kwargs):
        buildstep_kwargs = {}
        for k in kwargs.keys()[:]:
            if k in BuildStep.parms:
                buildstep_kwargs[k] = kwargs[k]
                del kwargs[k]
            BuildStep.__init__(self,build,**buildstep_kwargs)

        self.args = kwargs
        self.fileWriter = None

    def start(self):
        log.msg("FileUpload started, from slave %r to master %r"
                            % (self.args['slavesrc'],self.args['masterdest']))

        self.step_status.setColor('yellow')
        self.step_status.setText(['uploading', self.args['slavesrc']])

        fp = open(self.args['masterdest'],'w')
        self.fileWriter = FileWriter(fp)

        # default arguments
        args = {
            'maxsize': None,
            'blocksize': 16*1024,
            'workdir': 'build',
            }
        args.update(self.args)
        args['writer'] = self.fileWriter

        self.cmd = StatusRemoteCommand('uploadFile', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

    def finished(self,result):
        if self.cmd.stderr != '':
            self.addCompleteLog('stderr', self.cmd.stderr)

        self.fileWriter = None

        if self.cmd.rc is None or self.cmd.rc == 0:
            self.step_status.setColor('green')
            return BuildStep.finished(self,SUCCESS)
        self.step_status.setColor('red')
        return BuildStep.finished(self,FAILURE)

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

    def __init__(self,build, **kwargs):
        buildstep_kwargs = {}
        for k in kwargs.keys()[:]:
            if k in BuildStep.parms:
                buildstep_kwargs[k] = kwargs[k]
                del kwargs[k]
            BuildStep.__init__(self,build,**buildstep_kwargs)

        self.args = kwargs
        self.fileReader = None

    def start(self):
        log.msg("FileDownload started, from master %r to slave %r"
                            % (self.args['mastersrc'],self.args['slavedest']))

        self.step_status.setColor('yellow')
        self.step_status.setText(['downloading', self.args['slavedest']])

        # If file does not exist, bail out with an error
        if not os.path.isfile(self.args['mastersrc']):
            self.addCompleteLog('stderr',
                    'File %r not available at master' % self.args['mastersrc'])
            reactor.callLater(0, self.reportFail)
            return

        # setup structures for reading the file
        fp = open(self.args['mastersrc'],'r')
        self.fileReader = FileReader(fp)

        a = self.args.copy()
        a['reader'] = self.fileReader

        # add defaults for optional settings
        for k,dv in [('maxsize',None),('blocksize',16*1024),('workdir','build')]:
            if k not in a:
                a[k] = dv

        self.cmd = StatusRemoteCommand('downloadFile', a)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

    def finished(self,result):
        if self.cmd.stderr != '':
            self.addCompleteLog('stderr', self.cmd.stderr)

        self.fileReader = None

        if self.cmd.rc is None or self.cmd.rc == 0:
            self.step_status.setColor('green')
            return BuildStep.finished(self,SUCCESS)
        return self.reportFail()

    def reportFail(self):
        self.step_status.setColor('red')
        return BuildStep.finished(self,FAILURE)

