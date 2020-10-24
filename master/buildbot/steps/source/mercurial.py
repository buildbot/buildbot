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
"""
Source step code for mercurial
"""


from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.config import ConfigErrors
from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process import results
from buildbot.process.results import SUCCESS
from buildbot.steps.source.base import Source


class Mercurial(Source):

    """ Class for Mercurial with all the smarts """
    name = "hg"

    renderables = ["repourl"]
    possible_methods = (None, 'clean', 'fresh', 'clobber')
    possible_branchTypes = ('inrepo', 'dirname')

    def __init__(self, repourl=None, mode='incremental',
                 method=None, defaultBranch=None, branchType='dirname',
                 clobberOnBranchChange=True, **kwargs):
        """
        @type  repourl: string
        @param repourl: the URL which points at the Mercurial repository.
                        if 'dirname' branches are enabled, this is the base URL
                        to which a branch name will be appended. It should
                        probably end in a slash.

        @param defaultBranch: if branches are enabled, this is the branch
                              to use if the Build does not specify one
                              explicitly.
                              For 'dirname' branches, It will simply be
                              appended to C{repourl} and the result handed to
                              the 'hg update' command.
                              For 'inrepo' branches, this specifies the named
                              revision to which the tree will update after a
                              clone.

        @param branchType: either 'dirname' or 'inrepo' depending on whether
                           the branch name should be appended to the C{repourl}
                           or the branch is a mercurial named branch and can be
                           found within the C{repourl}

        @param clobberOnBranchChange: boolean, defaults to True. If set and
                                      using inrepos branches, clobber the tree
                                      at each branch change. Otherwise, just
                                      update to the branch.
        """

        self.repourl = repourl
        self.defaultBranch = self.branch = defaultBranch
        self.branchType = branchType
        self.method = method
        self.clobberOnBranchChange = clobberOnBranchChange
        self.mode = mode
        super().__init__(**kwargs)

        errors = []
        if not self._hasAttrGroupMember('mode', self.mode):
            errors.append("mode {} is not one of {}".format(self.mode,
                                                            self._listAttrGroupMembers('mode')))
        if self.method not in self.possible_methods:
            errors.append("method {} is not one of {}".format(self.method, self.possible_methods))
        if self.branchType not in self.possible_branchTypes:
            errors.append("branchType {} is not one of {}".format(self.branchType,
                                                                  self.possible_branchTypes))

        if repourl is None:
            errors.append("you must provide a repourl")

        if errors:
            raise ConfigErrors(errors)

    @defer.inlineCallbacks
    def run_vc(self, branch, revision, patch):
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = yield self.addLogForRemoteCommands("stdio")

        installed = yield self.checkHg()

        if not installed:
            raise WorkerSetupError("Mercurial is not installed on worker")

        # FIXME: this does not do anything
        yield self.sourcedirIsPatched()

        if self.branchType == 'dirname':
            self.repourl = self.repourl + (branch or '')
            self.branch = self.defaultBranch
            self.update_branch = branch
        elif self.branchType == 'inrepo':
            self.update_branch = (branch or 'default')

        yield self._getAttrGroupMember('mode', self.mode)()

        if patch:
            yield self.patch(patch)

        yield self.parseGotRevision()
        return results.SUCCESS

    @defer.inlineCallbacks
    def mode_full(self):
        if self.method == 'clobber':
            yield self.clobber()
            return

        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            yield self._clone()
            yield self._update()
        elif self.method == 'clean':
            yield self.clean()
        elif self.method == 'fresh':
            yield self.fresh()
        else:
            raise ValueError("Unknown method, check your configuration")

    @defer.inlineCallbacks
    def mode_incremental(self):
        if self.method is not None:
            raise ValueError(self.method)

        updatable = yield self._sourcedirIsUpdatable()

        if updatable:
            yield self._dovccmd(self.getHgPullCommand())
        else:
            yield self._clone()

        yield self._checkBranchChange()

    @defer.inlineCallbacks
    def clean(self):
        command = ['--config', 'extensions.purge=', 'purge']
        yield self._dovccmd(command)
        yield self._pullUpdate()

    @defer.inlineCallbacks
    def _clobber(self):
        cmd = remotecommand.RemoteCommand('rmdir', {'dir': self.workdir,
                                                    'logEnviron': self.logEnviron})
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

    @defer.inlineCallbacks
    def clobber(self):
        yield self._clobber()
        yield self._clone()
        yield self._update()

    @defer.inlineCallbacks
    def fresh(self):
        command = ['--config', 'extensions.purge=', 'purge', '--all']
        yield self._dovccmd(command)
        yield self._pullUpdate()

    @defer.inlineCallbacks
    def parseGotRevision(self):
        stdout = yield self._dovccmd(['parents', '--template', '{node}\\n'], collectStdout=True)

        revision = stdout.strip()
        if len(revision) != 40:
            raise ValueError("Incorrect revision id")
        log.msg("Got Mercurial revision {}".format(revision))
        self.updateSourceProperty('got_revision', revision)

    @defer.inlineCallbacks
    def _checkBranchChange(self):
        current_branch = yield self._getCurrentBranch()
        msg = "Working dir is on in-repo branch '{}' and build needs '{}'.".format(current_branch,
                self.update_branch)
        if current_branch != self.update_branch and self.clobberOnBranchChange:
            msg += ' Clobbering.'
            log.msg(msg)
            yield self.clobber()
            return
        msg += ' Updating.'
        log.msg(msg)
        yield self._removeAddedFilesAndUpdate(None)

    def getHgPullCommand(self):
        command = ['pull', self.repourl]
        if self.revision:
            command.extend(['--rev', self.revision])
        elif self.branchType == 'inrepo':
            command.extend(['--rev', self.update_branch])
        return command

    @defer.inlineCallbacks
    def _pullUpdate(self):
        command = self.getHgPullCommand()
        yield self._dovccmd(command)
        yield self._checkBranchChange()

    @defer.inlineCallbacks
    def _dovccmd(self, command, collectStdout=False, initialStdin=None, decodeRC=None,
                 abandonOnFailure=True):
        if not command:
            raise ValueError("No command specified")

        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        cmd = remotecommand.RemoteShellCommand(self.workdir, ['hg', '--verbose'] + command,
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout,
                                               collectStdout=collectStdout,
                                               initialStdin=initialStdin,
                                               decodeRC=decodeRC)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if abandonOnFailure and cmd.didFail():
            log.msg("Source step failed while running command {}".format(cmd))
            raise buildstep.BuildStepFailed()
        if collectStdout:
            return cmd.stdout
        return cmd.rc

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        # without knowing the revision ancestry graph, we can't sort the
        # changes at all. So for now, assume they were given to us in sorted
        # order, and just pay attention to the last one. See ticket #103 for
        # more details.
        if len(changes) > 1:
            log.msg("Mercurial.computeSourceRevision: warning: "
                    "there are %d changes here, assuming the last one is "
                    "the most recent" % len(changes))
        return changes[-1].revision

    @defer.inlineCallbacks
    def _getCurrentBranch(self):
        if self.branchType == 'dirname':
            return self.branch
        stdout = yield self._dovccmd(['identify', '--branch'], collectStdout=True)
        return stdout.strip()

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'
        return None

    def _sourcedirIsUpdatable(self):
        return self.pathExists(self.build.path_module.join(self.workdir, '.hg'))

    @defer.inlineCallbacks
    def _removeAddedFilesAndUpdate(self, _):
        command = ['locate', 'set:added()']
        stdout = yield self._dovccmd(command, collectStdout=True, decodeRC={0: SUCCESS, 1: SUCCESS})

        files = []
        for filename in stdout.splitlines():
            filename = self.workdir + '/' + filename
            files.append(filename)
        if files:
            if self.workerVersionIsOlderThan('rmdir', '2.14'):
                yield self.removeFiles(files)
            else:
                cmd = remotecommand.RemoteCommand('rmdir', {'dir': files,
                                                            'logEnviron':
                                                            self.logEnviron, })
                cmd.useLog(self.stdio_log, False)
                yield self.runCommand(cmd)

        yield self._update()

    @defer.inlineCallbacks
    def removeFiles(self, files):
        for filename in files:
            cmd = remotecommand.RemoteCommand('rmdir', {'dir': filename,
                                                        'logEnviron': self.logEnviron, })
            cmd.useLog(self.stdio_log, False)
            yield self.runCommand(cmd)
            if cmd.rc != 0:
                return cmd.rc
        return 0

    @defer.inlineCallbacks
    def _update(self):
        command = ['update', '--clean']
        if self.revision:
            command += ['--rev', self.revision]
        elif self.branchType == 'inrepo':
            command += ['--rev', self.update_branch]
        yield self._dovccmd(command)

    def _clone(self):
        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True
        d = self._dovccmd(['clone', '--noupdate', self.repourl, '.'],
                          abandonOnFailure=abandonOnFailure)

        def _retry(res):
            if self.stopped or res == 0:
                return res
            delay, repeats = self.retry
            if repeats > 0:
                log.msg("Checkout failed, trying %d more times after %d seconds"
                        % (repeats, delay))
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self._clobber())
                df.addCallback(lambda _: self._clone())
                reactor.callLater(delay, df.callback, None)
                return df
            return res

        if self.retry:
            d.addCallback(_retry)
        return d

    def checkHg(self):
        d = self._dovccmd(['--version'])

        @d.addCallback
        def check(res):
            return res == 0
        return d

    def applyPatch(self, patch):
        d = self._dovccmd(['import', '--no-commit', '-p', str(patch[0]), '-'],
                          initialStdin=patch[1])
        return d
