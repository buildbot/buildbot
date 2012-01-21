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

from twisted.python import log
from twisted.internet import defer

from buildbot.process import buildstep
from buildbot.steps.source import Source
from buildbot.interfaces import BuildSlaveTooOldError

class Git(Source):
    """ Class for Git with all the smarts """
    name='git'
    renderables = [ "repourl"]

    def __init__(self, repourl=None, branch='HEAD', mode='incremental',
                 method=None, submodules=False, shallow=False, progress=False,
                 retryFetch=False, clobberOnFailure=False, **kwargs):
        """
        @type  repourl: string
        @param repourl: the URL which points at the git repository

        @type  branch: string
        @param branch: The branch or tag to check out by default. If
                       a build specifies a different branch, it will
                       be used instead of this.

        @type  submodules: boolean
        @param submodules: Whether or not to update (and initialize)
                       git submodules.

        @type  mode: string
        @param mode: Type of checkout. Described in docs.

        @type  method: string
        @param method: Full builds can be done is different ways. This parameter
                       specifies which method to use.

        @type  progress: boolean
        @param progress: Pass the --progress option when fetching. This
                         can solve long fetches getting killed due to
                         lack of output, but requires Git 1.7.2+.
        @type  shallow: boolean
        @param shallow: Use a shallow or clone, if possible

        @type  retryFetch: boolean
        @param retryFetch: Retry fetching before failing source checkout.
        """

        self.branch    = branch
        self.method    = method
        self.prog  = progress
        self.repourl   = repourl
        self.retryFetch = retryFetch
        self.submodules = submodules
        self.shallow   = shallow
        self.fetchcount = 0
        self.clobberOnFailure = clobberOnFailure
        self.mode = mode
        Source.__init__(self, **kwargs)
        self.addFactoryArguments(branch=branch,
                                 mode=mode,
                                 method=method,
                                 progress=progress,
                                 repourl=repourl,
                                 submodules=submodules,
                                 shallow=shallow,
                                 retryFetch=retryFetch,
                                 clobberOnFailure=
                                 clobberOnFailure,
                                 )

        assert self.mode in ['incremental', 'full']
        assert self.repourl is not None
        if self.mode == 'full':
            assert self.method in ['clean', 'fresh', 'clobber', 'copy', None]

    def startVC(self, branch, revision, patch):
        self.branch = branch or 'HEAD'
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = self.addLog("stdio")

        d = self.checkGit()
        def checkInstall(gitInstalled):
            if not gitInstalled:
                raise BuildSlaveTooOldError("git is not installed on slave")
            return 0
        d.addCallback(checkInstall)

        if self.mode == 'incremental':
            d.addCallback(lambda _: self.incremental())
        elif self.mode == 'full':
            d.addCallback(lambda _: self.full())
        if patch:
            d.addCallback(self.patch, patch)
        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        d.addErrback(self.failed)
        return d

    @defer.deferredGenerator
    def full(self):
        if self.method == 'clobber':
            wfd = defer.waitForDeferred(self.clobber())
            yield wfd
            wfd.getResult()
            return
        elif self.method == 'copy':
            wfd = defer.waitForDeferred(self.copy())
            yield wfd
            wfd.getResult()
            return

        wfd = defer.waitForDeferred(self._sourcedirIsUpdatable())
        yield wfd
        updatable = wfd.getResult()
        if not updatable:
            log.msg("No git repo present, making full clone")
            d = self._doFull()
        elif self.method == 'clean':
            d = self.clean()
        elif self.method == 'fresh':
            d = self.fresh()
        else:
            raise ValueError("Unknown method, check your configuration")
        wfd = defer.waitForDeferred(d)
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def incremental(self):
        wfd = defer.waitForDeferred(
            self._sourcedirIsUpdatable())
        yield wfd
        updatable = wfd.getResult()

        # if not updateable, do a full checkout
        if not updatable:
            wfd = defer.waitForDeferred(
                    self._doFull())
            yield wfd
            yield wfd.getResult() # return value
            return

        # test for existence of the revision; rc=1 indicates it does not exist
        if self.revision:
            wfd = defer.waitForDeferred(
                self._dovccmd(['cat-file', '-e', self.revision], False))
            yield wfd
            rc = wfd.getResult()
        else:
            rc = 1

        # if revision exists checkout to that revision
        # else fetch and update
        if rc == 0:
            wfd = defer.waitForDeferred(
                    self._dovccmd(['reset', '--hard', self.revision]))
            yield wfd
            wfd.getResult()

            if self.branch != 'HEAD':
                wfd = defer.waitForDeferred(
                    self._dovccmd(['branch', '-M', self.branch], abandonOnFailure=False))
                yield wfd
                wfd.getResult()
        else:
            wfd = defer.waitForDeferred(
                    self._doFetch(None))
            yield wfd
            wfd.getResult()

        wfd = defer.waitForDeferred(
                self._updateSubmodule(None))
        yield wfd
        wfd.getResult()

    def clean(self):
        command = ['clean', '-f', '-d']
        d = self._dovccmd(command)
        d.addCallback(self._doFetch)
        d.addCallback(self._updateSubmodule)
        d.addCallback(self._cleanSubmodule)
        return d

    def clobber(self):
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.workdir,
                                                'logEnviron': self.logEnviron,})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def checkRemoval(res):
            if res != 0:
                raise RuntimeError("Failed to delete directory")
            return res
        d.addCallback(lambda _: checkRemoval(cmd.rc))
        d.addCallback(lambda _: self._doFull())
        return d

    def fresh(self):
        command = ['clean', '-f', '-d', '-x']
        d = self._dovccmd(command)
        d.addCallback(self._doFetch)
        d.addCallback(self._updateSubmodule)
        d.addCallback(self._cleanSubmodule)
        return d

    def copy(self):
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.workdir,
                                                'logEnviron': self.logEnviron,})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)

        self.workdir = 'source'
        d.addCallback(lambda _: self.incremental())
        def copy(_):
            cmd = buildstep.RemoteCommand('cpdir',
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

    def finish(self, res):
        d = defer.succeed(res)
        def _gotResults(results):
            self.setStatus(self.cmd, results)
            log.msg("Closing log, sending result of the command %s " % \
                        (self.cmd))
            return results
        d.addCallback(_gotResults)
        d.addCallbacks(self.finished, self.checkDisconnect)
        return d

    def parseGotRevision(self, _):
        d = self._dovccmd(['rev-parse', 'HEAD'], collectStdout=True)
        def setrev(stdout):
            revision = stdout.strip()
            if len(revision) != 40:
                raise buildstep.BuildStepFailed()
            log.msg("Got Git revision %s" % (revision, ))
            self.setProperty('got_revision', revision, 'Source')
            return 0
        d.addCallback(setrev)
        return d

    def _dovccmd(self, command, abandonOnFailure=True, collectStdout=False, extra_args={}):
        cmd = buildstep.RemoteShellCommand(self.workdir, ['git'] + command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           collectStdout=collectStdout,
                                           **extra_args)
        cmd.useLog(self.stdio_log, False)
        log.msg("Starting git command : git %s" % (" ".join(command), ))
        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if abandonOnFailure and cmd.rc != 0:
                log.msg("Source step failed while running command %s" % cmd)
                raise buildstep.BuildStepFailed()
            if collectStdout:
                return cmd.stdout
            else:
                return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

    def _fetch(self, _):
        command = ['fetch', '-t', self.repourl, self.branch]
        # If the 'progress' option is set, tell git fetch to output
        # progress information to the log. This can solve issues with
        # long fetches killed due to lack of output, but only works
        # with Git 1.7.2 or later.
        if self.prog:
            command.append('--progress')

        d = self._dovccmd(command)
        def checkout(_):
            if self.revision:
                rev = self.revision
            else:
                rev = 'FETCH_HEAD'
            command = ['reset', '--hard', rev]
            abandonOnFailure = not self.retryFetch and not self.clobberOnFailure
            return self._dovccmd(command, abandonOnFailure)
        d.addCallback(checkout)
        def renameBranch(res):
            if res != 0:
                return res
            d = self._dovccmd(['branch', '-M', self.branch], abandonOnFailure=False)
            # Ignore errors
            d.addCallback(lambda _: res)
            return d

        if self.branch != 'HEAD':
            d.addCallback(renameBranch)
        return d

    def patch(self, _, patch):
        d = self._dovccmd(['apply', '--index'], extra_args={'initial_stdin': patch})
        return d

    @defer.deferredGenerator
    def _doFetch(self, _):
        """
        Handles fallbacks for failure of fetch,
        wrapper for self._fetch
        """
        wfd = defer.waitForDeferred(self._fetch(None))
        yield wfd
        res = wfd.getResult()
        if res == 0:
            yield res
            return
        elif self.retryFetch:
            d = self._fetch(None)
        elif self.clobberOnFailure:
            d = self.clobber()
        else:
            raise buildstep.BuildStepFailed()

        wfd = defer.waitForDeferred(d)
        yield wfd
        res = wfd.getResult()

    def _full(self):
        if self.shallow:
            command = ['clone', '--depth', '1', '--branch', self.branch, self.repourl, '.']
        else:
            command = ['clone', '--branch', self.branch, self.repourl, '.']
        #Fix references
        if self.prog:
            command.append('--progress')

        d = self._dovccmd(command, not self.clobberOnFailure)
        # If revision specified checkout that revision
        if self.revision:
            d.addCallback(lambda _: self._dovccmd(['reset', '--hard',
                                                   self.revision],
                                                  not self.clobberOnFailure))
        # init and update submodules, recurisively. If there's not recursion
        # it will not do it.
        if self.submodules:
            d.addCallback(lambda _: self._dovccmd(['submodule', 'update',
                                                   '--init', '--recursive'],
                                                  not self.clobberOnFailure))
        return d

    def _doFull(self):
        d = self._full()
        def clobber(res):
            if res != 0:
                if self.clobberOnFailure:
                    return self.clobber()
                else:
                    raise buildstep.BuildStepFailed()
            else:
                return res
        d.addCallback(clobber)
        return d

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return changes[-1].revision

    def _sourcedirIsUpdatable(self):
        cmd = buildstep.RemoteCommand('stat', {'file': self.workdir + '/.git',
                                               'logEnviron': self.logEnviron,})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def _fail(tmp):
            if cmd.rc != 0:
                return False
            return True
        d.addCallback(_fail)
        return d

    def _updateSubmodule(self, _):
        if self.submodules:
            return self._dovccmd(['submodule', 'update', '--recursive'])
        else:
            return defer.succeed(0)

    def _cleanSubmodule(self, _):
        if self.submodules:
            command = ['submodule', 'foreach', 'git', 'clean', '-f', '-d']
            if self.mode == 'full' and self.method == 'fresh':
                command.append('-x')
            return self._dovccmd(command)
        else:
            return defer.succeed(0)

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'

    def checkGit(self):
        d = self._dovccmd(['--version'])
        def check(res):
            if res == 0:
                return True
            return False
        d.addCallback(check)
        return d
