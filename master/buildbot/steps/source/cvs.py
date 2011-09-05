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

from email.Utils import formatdate
import time

from twisted.python import log
from twisted.internet import defer

from buildbot.process import buildstep
from buildbot.steps.source import Source
from buildbot.interfaces import BuildSlaveTooOldError

class CVS(Source):

    name = "cvs"

    renderables = [ "cvsroot" ]

    def __init__(self, cvsroot=None, cvsmodule='', mode='incremental',
                 method=None, branch=None, global_options=[], extra_options=[],
                 login=None, **kwargs):

        self.cvsroot = cvsroot
        self.cvsmodule = cvsmodule
        self.branch = branch
        self.global_options = global_options
        self.extra_options = extra_options
        self.login = login
        self.mode = mode
        self.method = method
        self.srcdir = 'source'
        Source.__init__(self, **kwargs)
        self.addFactoryArguments(cvsroot=cvsroot,
                                 cvsmodule=cvsmodule,
                                 mode=mode,
                                 method=method,
                                 global_options=global_options,
                                 extra_options=extra_options,
                                 login=login,
                                 )

    def startVC(self, branch, revision, patch):
        self.revision = revision
        self.stdio_log = self.addLog("stdio")
        self.method = self._getMethod()
        d = self.checkCvs()
        def checkInstall(cvsInstalled):
            if not cvsInstalled:
                raise BuildSlaveTooOldError("CVS is not installed on slave")
            return 0
        d.addCallback(checkInstall)
        d.addCallback(self.checkLogin)

        if self.mode == 'incremental':
            d.addCallback(lambda _: self.incremental())
        elif self.mode == 'full':
            d.addCallback(lambda _: self.full())

        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        d.addErrback(self.failed)
        return d

    @defer.deferredGenerator
    def incremental(self):
        wfd = defer.waitForDeferred(self._sourcedirIsUpdatable())
        yield wfd
        updatable = wfd.getResult()
        if updatable:
            d = self.doUpdate()
        else:
            d = self.doCheckout(self.workdir)
        wfd = defer.waitForDeferred(d)
        yield wfd
        yield wfd.getResult()
        return

    @defer.deferredGenerator
    def full(self):
        if self.method == 'clobber':
            wfd = defer.waitForDeferred(self.clobber())
            yield wfd
            yield wfd.getResult()
            return

        elif self.method == 'copy':
            wfd = defer.waitForDeferred(self.copy())
            yield wfd
            yield wfd.getResult()
            return

        wfd = defer.waitForDeferred(self._sourcedirIsUpdatable())
        yield wfd
        updatable = wfd.getResult()
        if not updatable:
            log.msg("CVS repo not present, making full checkout")
            d = self.doCheckout(self.workdir)
        elif self.method == 'clean':
            d = self.clean()
        elif self.method == 'fresh':
            d = self.fresh()
        else:
            raise ValueError("Unknown method, check your configuration")
        wfd = defer.waitForDeferred(d)
        yield wfd
        yield wfd.getResult()

    def clobber(self):
        cmd = buildstep.LoggedRemoteCommand('rmdir', {'dir': self.workdir,
                                                      'logEnviron': self.logEnviron})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def checkRemoval(res):
            if res != 0:
                raise RuntimeError("Failed to delete directory")
            return res
        d.addCallback(lambda _: checkRemoval(cmd.rc))
        d.addCallback(lambda _: self.doCheckout(self.workdir))
        return d

    def fresh(self, ):
        d = self.purge(True)
        d.addCallback(lambda _: self.doUpdate())
        return d

    def clean(self, ):
        d = self.purge(False)
        d.addCallback(lambda _: self.doUpdate())
        return d

    def copy(self):
        cmd = buildstep.LoggedRemoteCommand('rmdir', {'dir': self.workdir,
                                                      'logEnviron': self.logEnviron})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)        
        self.workdir = 'source'
        d.addCallback(lambda _: self.incremental())
        def copy(_):
            cmd = buildstep.LoggedRemoteCommand('cpdir',
                                                {'fromdir': 'source',
                                                 'todir':'build',
                                                 'logEnviron': self.logEnviron,})
            cmd.useLog(self.stdio_log, False)
            d = self.runCommand(cmd)
            return d
        d.addCallback(copy)
        def resetWorkdir(_):
            self.workdir = 'build'
            return 0
        d.addCallback(resetWorkdir)
        return d
        
    def purge(self, ignore_ignores):
        command = ['cvsdiscard']
        if ignore_ignores:
            command += ['--ignore']
        cmd = buildstep.RemoteShellCommand(self.workdir, command,
                                           env=self.env,
                                           logEnviron=self.logEnviron)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def evaluate(rc):
            if rc != 0:
                raise buildstep.BuildStepFailed()
            return rc
        d.addCallback(lambda _: evaluate(cmd.rc))
        return d
        
    def doCheckout(self, dir):
        command = ['-d', self.cvsroot, '-z3', 'checkout', '-d', dir,
                   self.cvsmodule]
        command = self.global_options + command + self.extra_options
        if self.branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        d = self._dovccmd(command, '')
        return d

    def doUpdate(self):
        command = ['-z3', 'update', '-dP']
        if self.branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        d = self._dovccmd(command)
        return d

    def finish(self, res):
        d = defer.succeed(res)
        def _gotResults(results):
            self.setStatus(self.cmd, results)
            return results
        d.addCallback(_gotResults)
        d.addCallbacks(self.finished, self.checkDisconnect)
        return d

    def checkLogin(self, _):
        if self.login:
            d = defer.succeed(0)
        else:
            d = self._dovccmd(['-d', self.cvsroot, 'login'])
            def setLogin(res):
                # this happens only if the login command succeeds.
                self.login = True
                return res
            d.addCallback(setLogin)

        return d

    def _dovccmd(self, command, workdir=None):
        if workdir is None:
            workdir = self.workdir
        if not command:
            raise ValueError("No command specified")
        cmd = buildstep.RemoteShellCommand(workdir, ['cvs'] +
                                           command,
                                           env=self.env,
                                           logEnviron=self.logEnviron)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if cmd.rc != 0:
                log.msg("Source step failed while running command %s" % cmd)
                raise buildstep.BuildStepFailed()
            return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

    def _sourcedirIsUpdatable(self):
        cmd = buildstep.LoggedRemoteCommand('stat', {'file': self.workdir + '/CVS',
                                                     'logEnviron': self.logEnviron})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def _fail(tmp):
            if cmd.rc != 0:
                return False
            return True
        d.addCallback(_fail)
        return d

    def parseGotRevision(self, res):
        revision = time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime())
        self.setProperty('got_revision', revision, 'Source')
        return res

    def checkCvs(self):
        d = self._dovccmd(['--version'])
        def check(res):
            if res == 0:
                return True
            return False
        d.addCallback(check)
        return d

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        lastChange = max([c.when for c in changes])
        lastSubmit = max([br.submittedAt for br in self.build.requests])
        when = (lastChange + lastSubmit) / 2
        return formatdate(when)
