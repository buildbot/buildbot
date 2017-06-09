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
import stat

from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process import remotetransfer
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.util import ascii2unicode
from buildbot.worker_transition import deprecatedWorkerClassMethod


class WorkerBuildStep(buildstep.BuildStep):
    pass


class SetPropertiesFromEnv(WorkerBuildStep):

    """
    Sets properties from environment variables on the worker.

    Note this is transferred when the worker first connects
    """
    name = 'SetPropertiesFromEnv'
    description = ['Setting']
    descriptionDone = ['Set']

    def __init__(self, variables, source="WorkerEnvironment", **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.variables = variables
        self.source = source

    def start(self):
        # on Windows, environment variables are case-insensitive, but we have
        # a case-sensitive dictionary in worker_environ.  Fortunately, that
        # dictionary is also folded to uppercase, so we can simply fold the
        # variable names to uppercase to duplicate the case-insensitivity.
        fold_to_uppercase = (self.worker.worker_system == 'win32')

        properties = self.build.getProperties()
        environ = self.worker.worker_environ
        variables = self.variables
        log = []
        if isinstance(variables, str):
            variables = [self.variables]
        for variable in variables:
            key = variable
            if fold_to_uppercase:
                key = variable.upper()
            value = environ.get(key, None)
            if value:
                # note that the property is not uppercased
                properties.setProperty(variable, value, self.source,
                                       runtime=True)
                log.append("%s = %r" % (variable, value))
        self.addCompleteLog("properties", "\n".join(log))
        self.finished(SUCCESS)


class FileExists(WorkerBuildStep):

    """
    Check for the existence of a file on the worker.
    """
    name = 'FileExists'
    renderables = ['file']
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, file, **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.file = file

    def start(self):
        self.checkWorkerHasCommand('stat')
        cmd = remotecommand.RemoteCommand('stat', {'file': self.file})
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        if cmd.didFail():
            self.descriptionDone = ["File not found."]
            self.finished(FAILURE)
            return
        s = cmd.updates["stat"][-1]
        if stat.S_ISREG(s[stat.ST_MODE]):
            self.descriptionDone = ["File found."]
            self.finished(SUCCESS)
        else:
            self.descriptionDone = ["Not a file."]
            self.finished(FAILURE)


class CopyDirectory(WorkerBuildStep):

    """
    Copy a directory tree on the worker.
    """
    name = 'CopyDirectory'
    description = ['Copying']
    descriptionDone = ['Copied']

    renderables = ['src', 'dest']

    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, src, dest, timeout=None, maxTime=None, **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.src = src
        self.dest = dest
        self.timeout = timeout
        self.maxTime = maxTime

    def start(self):
        self.checkWorkerHasCommand('cpdir')

        args = {'fromdir': self.src, 'todir': self.dest}
        if self.timeout:
            args['timeout'] = self.timeout
        if self.maxTime:
            args['maxTime'] = self.maxTime

        cmd = remotecommand.RemoteCommand('cpdir', args)
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        if cmd.didFail():
            self.step_status.setText(["Copying", self.src, "to", self.dest, "failed."])
            self.finished(FAILURE)
            return
        self.step_status.setText(self.describe(done=True))
        self.finished(SUCCESS)

    # TODO: BuildStep subclasses don't have a describe()....
    def getResultSummary(self):
        src = ascii2unicode(self.src, 'replace')
        dest = ascii2unicode(self.dest, 'replace')
        copy = u"%s to %s" % (src, dest)
        if self.results == SUCCESS:
            rv = u'Copied ' + copy
        else:
            rv = u'Copying ' + copy + ' failed.'
        return {u'step': rv}


class RemoveDirectory(WorkerBuildStep):

    """
    Remove a directory tree on the worker.
    """
    name = 'RemoveDirectory'
    description = ['Deleting']
    descriptionDone = ['Deleted']

    renderables = ['dir']

    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, dir, **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.dir = dir

    def start(self):
        self.checkWorkerHasCommand('rmdir')
        cmd = remotecommand.RemoteCommand('rmdir', {'dir': self.dir})
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        if cmd.didFail():
            self.step_status.setText(["Delete failed."])
            self.finished(FAILURE)
            return
        self.finished(SUCCESS)


class MakeDirectory(WorkerBuildStep):

    """
    Create a directory on the worker.
    """
    name = 'MakeDirectory'
    description = ['Creating']
    descriptionDone = ['Created']

    renderables = ['dir']

    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, dir, **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.dir = dir

    def start(self):
        self.checkWorkerHasCommand('mkdir')
        cmd = remotecommand.RemoteCommand('mkdir', {'dir': self.dir})
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        if cmd.didFail():
            self.step_status.setText(["Create failed."])
            self.finished(FAILURE)
            return
        self.finished(SUCCESS)


class CompositeStepMixin():

    def addLogForRemoteCommands(self, logname):
        """This method must be called by user classes
        composite steps could create several logs, this mixin functions will write
        to the last one.
        """
        self.rc_log = self.addLog(logname)
        return self.rc_log

    def runRemoteCommand(self, cmd, args, abandonOnFailure=True,
                         evaluateCommand=lambda cmd: cmd.didFail()):
        """generic RemoteCommand boilerplate"""
        cmd = remotecommand.RemoteCommand(cmd, args)
        if hasattr(self, "rc_log"):
            cmd.useLog(self.rc_log, False)
        d = self.runCommand(cmd)

        def commandComplete(cmd):
            if abandonOnFailure and cmd.didFail():
                raise buildstep.BuildStepFailed()
            return evaluateCommand(cmd)

        d.addCallback(lambda res: commandComplete(cmd))
        return d

    def runRmdir(self, dir, timeout=None, **kwargs):
        """ remove a directory from the worker """
        cmd_args = {'dir': dir, 'logEnviron': self.logEnviron}
        if timeout:
            cmd_args['timeout'] = timeout
        return self.runRemoteCommand('rmdir', cmd_args, **kwargs)

    def runRmFile(self, path, timeout=None, **kwargs):
        """ remove a file from the worker """
        cmd_args = {'path': path, 'logEnviron': self.logEnviron}
        if timeout:
            cmd_args['timeout'] = timeout
        if self.workerVersionIsOlderThan('rmfile', '3.1'):
            cmd_args['dir'] = os.path.abspath(path)
            return self.runRemoteCommand('rmdir', cmd_args, **kwargs)
        return self.runRemoteCommand('rmfile', cmd_args, **kwargs)

    def pathExists(self, path):
        """ test whether path exists"""
        def commandComplete(cmd):
            return not cmd.didFail()

        return self.runRemoteCommand('stat', {'file': path,
                                              'logEnviron': self.logEnviron, },
                                     abandonOnFailure=False,
                                     evaluateCommand=commandComplete)

    def runMkdir(self, _dir, **kwargs):
        """ create a directory and its parents"""
        return self.runRemoteCommand('mkdir', {'dir': _dir,
                                               'logEnviron': self.logEnviron, },
                                     **kwargs)

    def runGlob(self, path, **kwargs):
        """ find files matching a shell-style pattern"""
        def commandComplete(cmd):
            return cmd.updates['files'][-1]

        return self.runRemoteCommand('glob', {'path': path,
                                              'logEnviron': self.logEnviron, },
                                     evaluateCommand=commandComplete, **kwargs)

    def getFileContentFromWorker(self, filename, abandonOnFailure=False):
        self.checkWorkerHasCommand("uploadFile")
        fileWriter = remotetransfer.StringFileWriter()
        # default arguments
        args = {
            'workdir': self.workdir,
            'writer': fileWriter,
            'maxsize': None,
            'blocksize': 32 * 1024,
        }

        if self.workerVersionIsOlderThan('uploadFile', '3.0'):
            args['slavesrc'] = filename
        else:
            args['workersrc'] = filename

        def commandComplete(cmd):
            if cmd.didFail():
                return None
            return fileWriter.buffer

        return self.runRemoteCommand('uploadFile', args,
                                     abandonOnFailure=abandonOnFailure,
                                     evaluateCommand=commandComplete)
    deprecatedWorkerClassMethod(locals(), getFileContentFromWorker)

    def downloadFileContentToWorker(self, workerdest, strfile, abandonOnFailure=False):
        self.checkWorkerHasCommand("downloadFile")
        fileReader = remotetransfer.FileReader(strfile)

        # default arguments
        args = {
            'maxsize': None,
            'reader': fileReader,
            'blocksize': 32 * 1024,
        }

        if self.workerVersionIsOlderThan('downloadFile', '3.0'):
            args['slavedest'] = workerdest
        else:
            args['workerdest'] = workerdest

        def commandComplete(cmd):
            if cmd.didFail():
                return None
            return fileReader

        return self.runRemoteCommand('downloadFile', args,
                                     abandonOnFailure=abandonOnFailure,
                                     evaluateCommand=commandComplete)
