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
import stat

from buildbot import config
from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.process import remotecommand
from buildbot.process import remotetransfer
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SKIPPED
from buildbot.process.buildstep import SUCCESS
from buildbot.util import json
from buildbot.util.eventual import eventually
from twisted.internet import defer
from twisted.python import log


def makeStatusRemoteCommand(step, remote_command, args):
    self = remotecommand.RemoteCommand(remote_command, args, decodeRC={None: SUCCESS, 0: SUCCESS})
    callback = lambda arg: step.step_status.addLog('stdio')
    self.useLogDelayed('stdio', callback, True)
    return self


class _TransferBuildStep(BuildStep):

    """
    Base class for FileUpload and FileDownload to factor out common
    functionality.
    """

    renderables = ['workdir']

    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, workdir=None, **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.workdir = workdir

    def runTransferCommand(self, cmd, writer=None):
        # Run a transfer step, add a callback to extract the command status,
        # add an error handler that cancels the writer.
        self.cmd = cmd
        d = self.runCommand(cmd)

        @d.addCallback
        def checkResult(_):
            if writer and cmd.didFail():
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
        self.checkSlaveHasCommand("uploadFile")

        source = self.slavesrc
        masterdest = self.masterdest
        # we rely upon the fact that the buildmaster runs chdir'ed into its
        # basedir to make sure that relative paths in masterdest are expanded
        # properly. TODO: maybe pass the master's basedir all the way down
        # into the BuildStep so we can do this better.
        masterdest = os.path.expanduser(masterdest)
        log.msg("FileUpload started, from slave %r to master %r"
                % (source, masterdest))

        self.descriptionDone = "uploading %s" % os.path.basename(source)
        if self.url is not None:
            self.addURL(os.path.basename(os.path.normpath(masterdest)), self.url)

        # we use maxsize to limit the amount of data on both sides
        fileWriter = remotetransfer.FileWriter(masterdest, self.maxsize, self.mode)

        if self.keepstamp and self.slaveVersionIsOlderThan("uploadFile", "2.13"):
            m = ("This buildslave (%s) does not support preserving timestamps. "
                 "Please upgrade the buildslave." % self.build.slavename)
            raise BuildSlaveTooOldError(m)

        # default arguments
        args = {
            'slavesrc': source,
            'workdir': self.workdir,
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
        self.checkSlaveHasCommand("uploadDirectory")

        source = self.slavesrc
        masterdest = self.masterdest
        # we rely upon the fact that the buildmaster runs chdir'ed into its
        # basedir to make sure that relative paths in masterdest are expanded
        # properly. TODO: maybe pass the master's basedir all the way down
        # into the BuildStep so we can do this better.
        masterdest = os.path.expanduser(masterdest)
        log.msg("DirectoryUpload started, from slave %r to master %r"
                % (source, masterdest))

        self.descriptionDone = "uploading %s" % os.path.basename(source)
        if self.url is not None:
            self.addURL(os.path.basename(os.path.normpath(masterdest)), self.url)

        # we use maxsize to limit the amount of data on both sides
        dirWriter = remotetransfer.DirectoryWriter(masterdest, self.maxsize, self.compress, 0o600)

        # default arguments
        args = {
            'slavesrc': source,
            'workdir': self.workdir,
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
        fileWriter = remotetransfer.FileWriter(masterdest, self.maxsize, self.mode)

        args = {
            'slavesrc': source,
            'workdir': self.workdir,
            'writer': fileWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'keepstamp': self.keepstamp,
        }

        cmd = makeStatusRemoteCommand(self, 'uploadFile', args)
        return self.runTransferCommand(cmd, fileWriter)

    def uploadDirectory(self, source, masterdest):
        dirWriter = remotetransfer.DirectoryWriter(masterdest, self.maxsize, self.compress, 0o600)

        args = {
            'slavesrc': source,
            'workdir': self.workdir,
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
            'workdir': self.workdir
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
            self.addURL(os.path.basename(os.path.normpath(masterdest)), self.url)

    def start(self):
        self.checkSlaveHasCommand("uploadDirectory")
        self.checkSlaveHasCommand("uploadFile")
        self.checkSlaveHasCommand("stat")

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
                    defer.returnValue(FAILURE)
                    return
            defer.returnValue(SUCCESS)

        d = uploadSources()

        @d.addCallback
        def allUploadsDone(result):
            d = defer.maybeDeferred(self.allUploadsDone, result, sources, masterdest)
            d.addCallback(lambda _: result)
            return d

        log.msg("MultipleFileUpload started, from slave %r to master %r"
                % (sources, masterdest))

        nsrcs = len(sources)
        self.descriptionDone = 'uploading %d %s' % (
            nsrcs, 'file' if nsrcs == 1 else 'files')

        d.addCallback(self.finished).addErrback(self.failed)

    def finished(self, result):
        return BuildStep.finished(self, result)


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
        self.checkSlaveHasCommand("downloadFile")

        # we are currently in the buildmaster's basedir, so any non-absolute
        # paths will be interpreted relative to that
        source = os.path.expanduser(self.mastersrc)
        slavedest = self.slavedest
        log.msg("FileDownload started, from master %r to slave %r" %
                (source, slavedest))

        self.descriptionDone = "downloading to %s" % os.path.basename(slavedest)

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
        fileReader = remotetransfer.FileReader(fp)

        # default arguments
        args = {
            'slavedest': slavedest,
            'maxsize': self.maxsize,
            'reader': fileReader,
            'blocksize': self.blocksize,
            'workdir': self.workdir,
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
        self.checkSlaveHasCommand("downloadFile")

        # we are currently in the buildmaster's basedir, so any non-absolute
        # paths will be interpreted relative to that
        slavedest = self.slavedest
        log.msg("StringDownload started, from master to slave %r" % slavedest)

        self.descriptionDone = "downloading to %s" % os.path.basename(slavedest)

        # setup structures for reading the file
        fileReader = remotetransfer.StringFileReader(self.s)

        # default arguments
        args = {
            'slavedest': slavedest,
            'maxsize': self.maxsize,
            'reader': fileReader,
            'blocksize': self.blocksize,
            'workdir': self.workdir,
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
