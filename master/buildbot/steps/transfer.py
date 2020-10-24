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


import json
import os
import stat

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.interfaces import WorkerSetupError
from buildbot.process import remotecommand
from buildbot.process import remotetransfer
from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SKIPPED
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep
from buildbot.steps.worker import CompositeStepMixin
from buildbot.util import flatten


def makeStatusRemoteCommand(step, remote_command, args):
    self = remotecommand.RemoteCommand(
        remote_command, args, decodeRC={None: SUCCESS, 0: SUCCESS})
    self.useLog(step.stdio_log)
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
        super().__init__(**buildstep_kwargs)
        self.workdir = workdir

    @defer.inlineCallbacks
    def runTransferCommand(self, cmd, writer=None):
        # Run a transfer step, add a callback to extract the command status,
        # add an error handler that cancels the writer.
        self.cmd = cmd
        try:
            yield self.runCommand(cmd)
            return cmd.results()
        finally:
            if writer:
                writer.cancel()

    @defer.inlineCallbacks
    def interrupt(self, reason):
        yield self.addCompleteLog('interrupt', str(reason))
        if self.cmd:
            yield self.cmd.interrupt(reason)
        return None


class FileUpload(_TransferBuildStep):

    name = 'upload'

    renderables = [
        'masterdest',
        'url',
        'urlText',
        'workersrc',
    ]

    def __init__(self, workersrc=None, masterdest=None,
                 workdir=None, maxsize=None, blocksize=256 * 1024, mode=None,
                 keepstamp=False, url=None, urlText=None,
                 **buildstep_kwargs):
        # Emulate that first two arguments are positional.
        if workersrc is None or masterdest is None:
            raise TypeError("__init__() takes at least 3 arguments")

        super().__init__(workdir=workdir, **buildstep_kwargs)

        self.workersrc = workersrc
        self.masterdest = masterdest
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error(
                'mode must be an integer or None')
        self.mode = mode
        self.keepstamp = keepstamp
        self.url = url
        self.urlText = urlText

    @defer.inlineCallbacks
    def run(self):
        self.checkWorkerHasCommand("uploadFile")
        self.stdio_log = yield self.addLog("stdio")

        source = self.workersrc
        masterdest = self.masterdest
        # we rely upon the fact that the buildmaster runs chdir'ed into its
        # basedir to make sure that relative paths in masterdest are expanded
        # properly. TODO: maybe pass the master's basedir all the way down
        # into the BuildStep so we can do this better.
        masterdest = os.path.expanduser(masterdest)
        log.msg("FileUpload started, from worker %r to master %r"
                % (source, masterdest))

        if self.description is None:
            self.description = ['uploading {}'.format(os.path.basename(source))]

        if self.descriptionDone is None:
            self.descriptionDone = self.description

        if self.url is not None:
            urlText = self.urlText

            if urlText is None:
                urlText = os.path.basename(masterdest)

            yield self.addURL(urlText, self.url)

        # we use maxsize to limit the amount of data on both sides
        fileWriter = remotetransfer.FileWriter(
            masterdest, self.maxsize, self.mode)

        if self.keepstamp and self.workerVersionIsOlderThan("uploadFile", "2.13"):
            m = (("This worker ({}) does not support preserving timestamps. "
                  "Please upgrade the worker.").format(self.build.workername))
            raise WorkerSetupError(m)

        # default arguments
        args = {
            'workdir': self.workdir,
            'writer': fileWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'keepstamp': self.keepstamp,
        }

        if self.workerVersionIsOlderThan('uploadFile', '3.0'):
            args['slavesrc'] = source
        else:
            args['workersrc'] = source

        cmd = makeStatusRemoteCommand(self, 'uploadFile', args)
        res = yield self.runTransferCommand(cmd, fileWriter)

        log.msg("File '{}' upload finished with results {}".format(
            os.path.basename(self.workersrc), str(res)))

        return res


class DirectoryUpload(_TransferBuildStep):

    name = 'upload'

    renderables = [
        'workersrc',
        'masterdest',
        'url',
        'urlText'
    ]

    def __init__(self, workersrc=None, masterdest=None,
                 workdir=None, maxsize=None, blocksize=16 * 1024,
                 compress=None, url=None, urlText=None,
                 **buildstep_kwargs
                 ):
        # Emulate that first two arguments are positional.
        if workersrc is None or masterdest is None:
            raise TypeError("__init__() takes at least 3 arguments")

        super().__init__(workdir=workdir, **buildstep_kwargs)

        self.workersrc = workersrc
        self.masterdest = masterdest
        self.maxsize = maxsize
        self.blocksize = blocksize
        if compress not in (None, 'gz', 'bz2'):
            config.error(
                "'compress' must be one of None, 'gz', or 'bz2'")
        self.compress = compress
        self.url = url
        self.urlText = urlText

    @defer.inlineCallbacks
    def run(self):
        self.checkWorkerHasCommand("uploadDirectory")
        self.stdio_log = yield self.addLog("stdio")

        source = self.workersrc
        masterdest = self.masterdest
        # we rely upon the fact that the buildmaster runs chdir'ed into its
        # basedir to make sure that relative paths in masterdest are expanded
        # properly. TODO: maybe pass the master's basedir all the way down
        # into the BuildStep so we can do this better.
        masterdest = os.path.expanduser(masterdest)
        log.msg("DirectoryUpload started, from worker {} to master {}".format(repr(source),
                                                                              repr(masterdest)))

        self.descriptionDone = "uploading {}".format(os.path.basename(source))
        if self.url is not None:
            urlText = self.urlText

            if urlText is None:
                urlText = os.path.basename(os.path.normpath(masterdest))

            yield self.addURL(urlText, self.url)

        # we use maxsize to limit the amount of data on both sides
        dirWriter = remotetransfer.DirectoryWriter(
            masterdest, self.maxsize, self.compress, 0o600)

        # default arguments
        args = {
            'workdir': self.workdir,
            'writer': dirWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'compress': self.compress
        }

        if self.workerVersionIsOlderThan('uploadDirectory', '3.0'):
            args['slavesrc'] = source
        else:
            args['workersrc'] = source

        cmd = makeStatusRemoteCommand(self, 'uploadDirectory', args)
        res = yield self.runTransferCommand(cmd, dirWriter)
        return res


class MultipleFileUpload(_TransferBuildStep, CompositeStepMixin):

    name = 'upload'
    logEnviron = False

    renderables = [
        'workersrcs',
        'masterdest',
        'url',
        'urlText'
    ]

    def __init__(self, workersrcs=None, masterdest=None,
                 workdir=None, maxsize=None, blocksize=16 * 1024, glob=False,
                 mode=None, compress=None, keepstamp=False, url=None, urlText=None,
                 **buildstep_kwargs):

        # Emulate that first two arguments are positional.
        if workersrcs is None or masterdest is None:
            raise TypeError("__init__() takes at least 3 arguments")

        super().__init__(workdir=workdir, **buildstep_kwargs)

        self.workersrcs = workersrcs
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
        self.glob = glob
        self.keepstamp = keepstamp
        self.url = url
        self.urlText = urlText

    def uploadFile(self, source, masterdest):
        fileWriter = remotetransfer.FileWriter(
            masterdest, self.maxsize, self.mode)

        args = {
            'workdir': self.workdir,
            'writer': fileWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'keepstamp': self.keepstamp,
        }

        if self.workerVersionIsOlderThan('uploadFile', '3.0'):
            args['slavesrc'] = source
        else:
            args['workersrc'] = source

        cmd = makeStatusRemoteCommand(self, 'uploadFile', args)
        return self.runTransferCommand(cmd, fileWriter)

    def uploadDirectory(self, source, masterdest):
        dirWriter = remotetransfer.DirectoryWriter(
            masterdest, self.maxsize, self.compress, 0o600)

        args = {
            'workdir': self.workdir,
            'writer': dirWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'compress': self.compress
        }

        if self.workerVersionIsOlderThan('uploadDirectory', '3.0'):
            args['slavesrc'] = source
        else:
            args['workersrc'] = source

        cmd = makeStatusRemoteCommand(self, 'uploadDirectory', args)
        return self.runTransferCommand(cmd, dirWriter)

    @defer.inlineCallbacks
    def startUpload(self, source, destdir):
        masterdest = os.path.join(destdir, os.path.basename(source))
        args = {
            'file': source,
            'workdir': self.workdir
        }

        cmd = makeStatusRemoteCommand(self, 'stat', args)
        yield self.runCommand(cmd)
        if cmd.rc != 0:
            msg = 'File {}/{} not available at worker'.format(self.workdir, source)
            yield self.addCompleteLog('stderr', msg)
            return FAILURE
        s = cmd.updates['stat'][-1]
        if stat.S_ISDIR(s[stat.ST_MODE]):
            result = yield self.uploadDirectory(source, masterdest)
        elif stat.S_ISREG(s[stat.ST_MODE]):
            result = yield self.uploadFile(source, masterdest)
        else:
            msg = '{} is neither a regular file, nor a directory'.format(source)
            yield self.addCompleteLog('stderr', msg)
            return FAILURE

        yield self.uploadDone(result, source, masterdest)
        return result

    def uploadDone(self, result, source, masterdest):
        pass

    @defer.inlineCallbacks
    def allUploadsDone(self, result, sources, masterdest):
        if self.url is not None:
            urlText = self.urlText

            if urlText is None:
                urlText = os.path.basename(os.path.normpath(masterdest))

            yield self.addURL(urlText, self.url)

    @defer.inlineCallbacks
    def run(self):
        self.checkWorkerHasCommand("uploadDirectory")
        self.checkWorkerHasCommand("uploadFile")
        self.checkWorkerHasCommand("stat")
        self.stdio_log = yield self.addLog("stdio")

        masterdest = os.path.expanduser(self.masterdest)
        sources = self.workersrcs if isinstance(self.workersrcs, list) else [self.workersrcs]

        if self.keepstamp and self.workerVersionIsOlderThan("uploadFile", "2.13"):
            m = (("This worker ({}) does not support preserving timestamps. "
                  "Please upgrade the worker.").format(self.build.workername))
            raise WorkerSetupError(m)

        if not sources:
            return SKIPPED

        if self.glob:
            results = yield defer.gatherResults([
                self.runGlob(os.path.join(self.workdir, source), abandonOnFailure=False)
                for source in sources
            ])
            sources = [self.workerPathToMasterPath(p) for p in flatten(results)]

        log.msg("MultipleFileUpload started, from worker {!r} to master {!r}".format(sources,
                                                                                     masterdest))

        self.descriptionDone = ['uploading', str(len(sources)),
                                'file' if len(sources) == 1 else 'files']

        if not sources:
            result = SKIPPED
        else:
            result = SUCCESS
            for source in sources:
                result_single = yield self.startUpload(source, masterdest)
                if result_single == FAILURE:
                    result = FAILURE
                    break

        yield self.allUploadsDone(result, sources, masterdest)

        return result


class FileDownload(_TransferBuildStep):

    name = 'download'

    renderables = ['mastersrc', 'workerdest']

    def __init__(self, mastersrc, workerdest=None,
                 workdir=None, maxsize=None, blocksize=16 * 1024, mode=None,
                 **buildstep_kwargs):
        # Emulate that first two arguments are positional.
        if workerdest is None:
            raise TypeError("__init__() takes at least 3 arguments")

        super().__init__(workdir=workdir, **buildstep_kwargs)

        self.mastersrc = mastersrc
        self.workerdest = workerdest
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error(
                'mode must be an integer or None')
        self.mode = mode

    @defer.inlineCallbacks
    def run(self):
        self.checkWorkerHasCommand("downloadFile")
        self.stdio_log = yield self.addLog("stdio")

        # we are currently in the buildmaster's basedir, so any non-absolute
        # paths will be interpreted relative to that
        source = os.path.expanduser(self.mastersrc)
        workerdest = self.workerdest
        log.msg("FileDownload started, from master %r to worker %r" %
                (source, workerdest))

        self.descriptionDone = ["downloading to", os.path.basename(workerdest)]

        # setup structures for reading the file
        try:
            fp = open(source, 'rb')
        except IOError:
            # if file does not exist, bail out with an error
            yield self.addCompleteLog('stderr', 'File {!r} not available at master'.format(source))
            raise

        fileReader = remotetransfer.FileReader(fp)

        # default arguments
        args = {
            'maxsize': self.maxsize,
            'reader': fileReader,
            'blocksize': self.blocksize,
            'workdir': self.workdir,
            'mode': self.mode,
        }

        if self.workerVersionIsOlderThan('downloadFile', '3.0'):
            args['slavedest'] = workerdest
        else:
            args['workerdest'] = workerdest

        cmd = makeStatusRemoteCommand(self, 'downloadFile', args)
        res = yield self.runTransferCommand(cmd)
        return res


class StringDownload(_TransferBuildStep):

    name = 'string_download'

    renderables = ['workerdest', 's']

    def __init__(self, s, workerdest=None,
                 workdir=None, maxsize=None, blocksize=16 * 1024, mode=None,
                 **buildstep_kwargs):
        # Emulate that first two arguments are positional.
        if workerdest is None:
            raise TypeError("__init__() takes at least 3 arguments")

        super().__init__(workdir=workdir, **buildstep_kwargs)

        self.s = s
        self.workerdest = workerdest
        self.maxsize = maxsize
        self.blocksize = blocksize
        if not isinstance(mode, (int, type(None))):
            config.error("StringDownload step's mode must be an integer or None, got '{}'".format(
                    mode))
        self.mode = mode

    @defer.inlineCallbacks
    def run(self):
        # we use 'downloadFile' remote command on the worker
        self.checkWorkerHasCommand("downloadFile")
        self.stdio_log = yield self.addLog("stdio")

        # we are currently in the buildmaster's basedir, so any non-absolute
        # paths will be interpreted relative to that
        workerdest = self.workerdest
        log.msg("StringDownload started, from master to worker %r" %
                workerdest)

        self.descriptionDone = ["downloading to", os.path.basename(workerdest)]

        # setup structures for reading the file
        fileReader = remotetransfer.StringFileReader(self.s)

        # default arguments
        args = {
            'maxsize': self.maxsize,
            'reader': fileReader,
            'blocksize': self.blocksize,
            'workdir': self.workdir,
            'mode': self.mode,
        }

        if self.workerVersionIsOlderThan('downloadFile', '3.0'):
            args['slavedest'] = workerdest
        else:
            args['workerdest'] = workerdest

        cmd = makeStatusRemoteCommand(self, 'downloadFile', args)
        res = yield self.runTransferCommand(cmd)
        return res


class JSONStringDownload(StringDownload):

    name = "json_download"

    def __init__(self, o, workerdest=None,
                 **buildstep_kwargs):
        # Emulate that first two arguments are positional.
        if workerdest is None:
            raise TypeError("__init__() takes at least 3 arguments")

        if 's' in buildstep_kwargs:
            del buildstep_kwargs['s']
        s = json.dumps(o)
        super().__init__(s=s, workerdest=workerdest, **buildstep_kwargs)


class JSONPropertiesDownload(StringDownload):

    name = "json_properties_download"

    def __init__(self, workerdest=None,
                 **buildstep_kwargs):
        # Emulate that first two arguments are positional.
        if workerdest is None:
            raise TypeError("__init__() takes at least 2 arguments")

        if 's' in buildstep_kwargs:
            del buildstep_kwargs['s']
        super().__init__(s=None, workerdest=workerdest, **buildstep_kwargs)

    @defer.inlineCallbacks
    def run(self):
        properties = self.build.getProperties()
        props = {}
        for key, value, source in properties.asList():
            props[key] = value

        self.s = json.dumps(dict(
            properties=props,
            sourcestamps=[ss.asDict()
                          for ss in self.build.getAllSourceStamps()],
        ),
        )
        res = yield super().run()
        return res
