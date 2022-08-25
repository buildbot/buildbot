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


import re
import time
from email.utils import formatdate

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process import results
from buildbot.process.remotetransfer import StringFileWriter
from buildbot.steps.source.base import Source


class CVS(Source):

    name = "cvs"

    renderables = ["cvsroot"]

    def __init__(self, cvsroot=None, cvsmodule='', mode='incremental',
                 method=None, branch=None, global_options=None, extra_options=None,
                 login=None, **kwargs):

        self.cvsroot = cvsroot
        self.cvsmodule = cvsmodule
        self.branch = branch
        if global_options is None:
            global_options = []
        self.global_options = global_options
        if extra_options is None:
            extra_options = []
        self.extra_options = extra_options
        self.login = login
        self.mode = mode
        self.method = method
        self.srcdir = 'source'

        if not self._hasAttrGroupMember('mode', self.mode):
            raise ValueError(f"mode {self.mode} is not one of {self._listAttrGroupMembers('mode')}")
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run_vc(self, branch, revision, patch):
        self.branch = branch
        self.revision = revision
        self.stdio_log = yield self.addLogForRemoteCommands("stdio")
        self.method = self._getMethod()

        installed = yield self.checkCvs()
        if not installed:
            raise WorkerSetupError("CVS is not installed on worker")

        yield self.checkLogin()

        patched = yield self.sourcedirIsPatched()

        if patched:
            yield self.purge(False)

        yield self._getAttrGroupMember('mode', self.mode)()

        if patch:
            yield self.patch(patch)
        yield self.parseGotRevision()
        return results.SUCCESS

    @defer.inlineCallbacks
    def mode_incremental(self):
        updatable = yield self._sourcedirIsUpdatable()
        if updatable:
            rv = yield self.doUpdate()
        else:
            rv = yield self.clobber()
        return rv

    @defer.inlineCallbacks
    def mode_full(self):
        if self.method == 'clobber':
            rv = yield self.clobber()
            return rv

        elif self.method == 'copy':
            rv = yield self.copy()
            return rv

        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            log.msg("CVS repo not present, making full checkout")
            rv = yield self.doCheckout(self.workdir)
        elif self.method == 'clean':
            rv = yield self.clean()
        elif self.method == 'fresh':
            rv = yield self.fresh()
        else:
            raise ValueError("Unknown method, check your configuration")
        return rv

    @defer.inlineCallbacks
    def _clobber(self):
        cmd = remotecommand.RemoteCommand('rmdir', {'dir': self.workdir,
                                                    'logEnviron': self.logEnviron,
                                                    'timeout': self.timeout})
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if cmd.rc:
            raise RuntimeError("Failed to delete directory")

    @defer.inlineCallbacks
    def clobber(self):
        yield self._clobber()
        res = yield self.doCheckout(self.workdir)
        return res

    @defer.inlineCallbacks
    def fresh(self, ):
        yield self.purge(True)
        res = yield self.doUpdate()
        return res

    @defer.inlineCallbacks
    def clean(self, ):
        yield self.purge(False)
        res = yield self.doUpdate()
        return res

    @defer.inlineCallbacks
    def copy(self):
        cmd = remotecommand.RemoteCommand('rmdir', {'dir': self.workdir,
                                                    'logEnviron': self.logEnviron,
                                                    'timeout': self.timeout})
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        old_workdir = self.workdir
        self.workdir = self.srcdir
        yield self.mode_incremental()

        cmd = remotecommand.RemoteCommand('cpdir', {
            'fromdir': self.srcdir,
            'todir': old_workdir,
            'logEnviron': self.logEnviron,
            'timeout': self.timeout})
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        self.workdir = old_workdir

        return results.SUCCESS

    @defer.inlineCallbacks
    def purge(self, ignore_ignores):
        command = ['cvsdiscard']
        if ignore_ignores:
            command += ['--ignore']
        cmd = remotecommand.RemoteShellCommand(self.workdir, command,
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if cmd.didFail():
            raise buildstep.BuildStepFailed()

    @defer.inlineCallbacks
    def doCheckout(self, dir):
        command = ['-d', self.cvsroot, '-z3', 'checkout', '-d', dir]
        command = self.global_options + command + self.extra_options
        if self.branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        command += [self.cvsmodule]
        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True
        res = yield self._dovccmd(command, '', abandonOnFailure=abandonOnFailure)

        if self.retry:
            if self.stopped or res == 0:
                return res
            delay, repeats = self.retry
            if repeats > 0:
                log.msg(f"Checkout failed, trying {repeats} more times after {delay} seconds")
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self._clobber())
                df.addCallback(lambda _: self.doCheckout(self.workdir))
                reactor.callLater(delay, df.callback, None)
                res = yield df
        return res

    @defer.inlineCallbacks
    def doUpdate(self):
        command = ['-z3', 'update', '-dP']
        branch = self.branch
        # special case. 'cvs update -r HEAD -D today' gives no files; see #2351
        if branch == 'HEAD' and self.revision:
            branch = None
        if branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        res = yield self._dovccmd(command)
        return res

    @defer.inlineCallbacks
    def checkLogin(self):
        if self.login:
            yield self._dovccmd(['-d', self.cvsroot, 'login'],
                                initialStdin=self.login + "\n")

    @defer.inlineCallbacks
    def _dovccmd(self, command, workdir=None, abandonOnFailure=True,
                 initialStdin=None):
        if workdir is None:
            workdir = self.workdir
        if not command:
            raise ValueError("No command specified")
        cmd = remotecommand.RemoteShellCommand(workdir,
                                               ['cvs'] + command,
                                               env=self.env,
                                               timeout=self.timeout,
                                               logEnviron=self.logEnviron,
                                               initialStdin=initialStdin)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if cmd.rc != 0 and abandonOnFailure:
            log.msg(f"Source step failed while running command {cmd}")
            raise buildstep.BuildStepFailed()
        return cmd.rc

    def _cvsEntriesContainStickyDates(self, entries):
        for line in entries.splitlines():
            if line == 'D':  # the last line contains just a single 'D'
                pass
            elif line.split('/')[-1].startswith('D'):
                # fields are separated by slashes, the last field contains the tag or date
                # sticky dates start with 'D'
                return True
        return False  # no sticky dates

    @defer.inlineCallbacks
    def _sourcedirIsUpdatable(self):
        myFileWriter = StringFileWriter()
        args = {
            'workdir': self.build.path_module.join(self.workdir, 'CVS'),
            'writer': myFileWriter,
            'maxsize': None,
            'blocksize': 32 * 1024,
        }

        def uploadFileArgs(source):
            full_args = dict(args)
            if self.workerVersionIsOlderThan('uploadFile', '3.0'):
                full_args['slavesrc'] = source
            else:
                full_args['workersrc'] = source
            return full_args

        cmd = remotecommand.RemoteCommand('uploadFile',
                                          uploadFileArgs('Root'),
                                          ignore_updates=True)
        yield self.runCommand(cmd)
        if cmd.rc is not None and cmd.rc != 0:
            return False

        # on Windows, the cvsroot may not contain the password, so compare to
        # both
        cvsroot_without_pw = re.sub("(:pserver:[^:]*):[^@]*(@.*)",
                                    r"\1\2", self.cvsroot)
        if myFileWriter.buffer.strip() not in (self.cvsroot,
                                               cvsroot_without_pw):
            return False

        myFileWriter.buffer = ""
        cmd = remotecommand.RemoteCommand('uploadFile',
                                          uploadFileArgs('Repository'),
                                          ignore_updates=True)
        yield self.runCommand(cmd)
        if cmd.rc is not None and cmd.rc != 0:
            return False
        if myFileWriter.buffer.strip() != self.cvsmodule:
            return False

        # if there are sticky dates (from an earlier build with revision),
        # we can't update (unless we remove those tags with cvs update -A)
        myFileWriter.buffer = ""
        cmd = remotecommand.RemoteCommand('uploadFile',
                                          uploadFileArgs('Entries'),
                                          ignore_updates=True)
        yield self.runCommand(cmd)
        if cmd.rc is not None and cmd.rc != 0:
            return False
        if self._cvsEntriesContainStickyDates(myFileWriter.buffer):
            return False

        return True

    def parseGotRevision(self):
        revision = time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime())
        self.updateSourceProperty('got_revision', revision)

    @defer.inlineCallbacks
    def checkCvs(self):
        res = yield self._dovccmd(['--version'])
        return res == 0

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'
        return None

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        lastChange = max(c.when for c in changes)
        lastSubmit = max(br.submittedAt for br in self.build.requests)
        when = (lastChange + lastSubmit) / 2
        return formatdate(when)
