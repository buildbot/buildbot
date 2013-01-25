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

## Source step code for mercurial

from twisted.python import log
from twisted.internet import defer

from buildbot.process import buildstep
from buildbot.steps.source.base import Source
from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.config import ConfigErrors
from buildbot.status.results import SUCCESS

class Mercurial(Source):
    """ Class for Mercurial with all the smarts """
    name = "hg"

    renderables = [ "repourl" ]
    possible_modes = ('incremental', 'full')
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
        Source.__init__(self, **kwargs)

        errors = []
        if self.mode not in self.possible_modes:
            errors.append("mode %s is not one of %s" %
                            (self.mode, self.possible_modes))
        if self.method not in self.possible_methods:
            errors.append("method %s is not one of %s" %
                            (self.method, self.possible_methods))
        if self.branchType not in self.possible_branchTypes:
            errors.append("branchType %s is not one of %s" %
                            (self.branchType, self.possible_branchTypes))

        if repourl is None:
            errors.append("you must provide a repourl")
        
        if errors:
            raise ConfigErrors(errors)

    def startVC(self, branch, revision, patch):
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = self.addLogForRemoteCommands("stdio")
        d = self.checkHg()
        def checkInstall(hgInstalled):
            if not hgInstalled:
                raise BuildSlaveTooOldError("Mercurial is not installed on slave")
            return 0
        d.addCallback(checkInstall)

        if self.branchType == 'dirname':
            self.repourl = self.repourl + (branch or '')
            self.branch = self.defaultBranch
            self.update_branch = branch
        elif self.branchType == 'inrepo':
            self.update_branch = (branch or 'default')

        if self.mode == 'full':
            d.addCallback(lambda _: self.full())
        elif self.mode == 'incremental':
            d.addCallback(lambda _: self.incremental())

        if patch:
            d.addCallback(self.patch, patch)

        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        d.addErrback(self.failed)

    @defer.inlineCallbacks
    def full(self):
        if self.method == 'clobber':
            yield self.clobber(None)
            return

        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            yield self._dovccmd(['clone', self.repourl, '.'])
        elif self.method == 'clean':
            yield self.clean(None)
        elif self.method == 'fresh':
            yield self.fresh(None)
        else:
            raise ValueError("Unknown method, check your configuration")

    def incremental(self):
        if self.method is not None:
            raise ValueError(self.method)

        d = self._sourcedirIsUpdatable()
        def _cmd(updatable):
            if updatable:
                command = ['pull', self.repourl]
            else:
                command = ['clone', self.repourl, '.', '--noupdate']
            return command

        d.addCallback(_cmd)
        d.addCallback(self._dovccmd)
        d.addCallback(self._checkBranchChange)
        return d

    def clean(self, _):
        command = ['--config', 'extensions.purge=', 'purge']
        d =  self._dovccmd(command)
        d.addCallback(self._pullUpdate)
        return d

    def clobber(self, _):
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.workdir,
                                                'logEnviron':self.logEnviron})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        d.addCallback(lambda _: self._dovccmd(['clone', '--noupdate'
                                               , self.repourl, "."]))
        d.addCallback(self._update)
        return d

    def fresh(self, _):
        command = ['--config', 'extensions.purge=', 'purge', '--all']
        d = self._dovccmd(command)
        d.addCallback(self._pullUpdate)
        return d

    def finish(self, res):
        d = defer.succeed(res)
        def _gotResults(results):
            self.setStatus(self.cmd, results)
            return results
        d.addCallback(_gotResults)
        d.addCallbacks(self.finished, self.checkDisconnect)
        return d

    def parseGotRevision(self, _):
        d = self._dovccmd(['parents', '--template', '{node}\\n'], collectStdout=True)
        def _setrev(stdout):
            revision = stdout.strip()
            if len(revision) != 40:
                raise ValueError("Incorrect revision id")
            log.msg("Got Mercurial revision %s" % (revision, ))
            self.updateSourceProperty('got_revision', revision)
            return 0
        d.addCallback(_setrev)
        return d

    @defer.inlineCallbacks
    def _checkBranchChange(self, _):
        current_branch = yield self._getCurrentBranch()
        msg = "Working dir is on in-repo branch '%s' and build needs '%s'." % \
              (current_branch, self.update_branch)
        if current_branch != self.update_branch and self.clobberOnBranchChange:
                msg += ' Clobbering.'
                log.msg(msg)
                yield self.clobber(None)
                return
        msg += ' Updating.'
        log.msg(msg)
        yield self._removeAddedFilesAndUpdate(None)

    def _pullUpdate(self, res):
        command = ['pull' , self.repourl]
        if self.revision:
            command.extend(['--rev', self.revision])
        d = self._dovccmd(command)
        d.addCallback(self._checkBranchChange)
        return d

    def _dovccmd(self, command, collectStdout=False, initialStdin=None, decodeRC={0:SUCCESS}):
        if not command:
            raise ValueError("No command specified")
        cmd = buildstep.RemoteShellCommand(self.workdir, ['hg', '--verbose'] + command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout,
                                           collectStdout=collectStdout,
                                           initialStdin=initialStdin,
                                           decodeRC=decodeRC)
        cmd.useLog(self.stdio_log, False)
        log.msg("Starting mercurial command : hg %s" % (" ".join(command), ))
        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if cmd.didFail():
                log.msg("Source step failed while running command %s" % cmd)
                raise buildstep.BuildStepFailed()
            if collectStdout:
                return cmd.stdout
            else:
                return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

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

    def patch(self, _, patch):
        d = self._dovccmd(['import', '--no-commit', '-p', str(patch[0]), '-'],
                initialStdin=patch[1])
        return d

    def _getCurrentBranch(self):
        if self.branchType == 'dirname':
            return defer.succeed(self.branch)
        else:
            d = self._dovccmd(['identify', '--branch'], collectStdout=True)
            def _getbranch(stdout):
                return stdout.strip()
            d.addCallback(_getbranch).addErrback
            return d

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'

    def _sourcedirIsUpdatable(self):
        return self.pathExists(self.build.path_module.join(self.workdir, '.hg'))

    def _removeAddedFilesAndUpdate(self, _):
        command = ['locate', 'set:added()']
        d = self._dovccmd(command, collectStdout=True, decodeRC={0:SUCCESS,1:SUCCESS})
        def parseAndRemove(stdout):
            files = []
            for filename in stdout.splitlines() :
                filename = self.workdir+'/'+filename
                files.append(filename)
            if len(files) == 0:
                d = defer.succeed(0)
            else:
                if self.slaveVersionIsOlderThan('rmdir', '2.14'):
                    d = self.removeFiles(files)
                else:
                    cmd = buildstep.RemoteCommand('rmdir', {'dir': files,
                                                            'logEnviron':
                                                            self.logEnviron,})
                    cmd.useLog(self.stdio_log, False)
                    d = self.runCommand(cmd)
                    d.addCallback(lambda _: cmd.rc)
            return d
        d.addCallback(parseAndRemove)
        d.addCallback(self._update)
        return d

    @defer.inlineCallbacks
    def removeFiles(self, files):
        for filename in files:
            cmd = buildstep.RemoteCommand('rmdir', {'dir': filename,
                                                    'logEnviron': self.logEnviron,})
            cmd.useLog(self.stdio_log, False)
            yield self.runCommand(cmd)
            if cmd.rc != 0:
                defer.returnValue(cmd.rc)
                return
        defer.returnValue(0)

    def _update(self, _):
        command = ['update', '--clean']
        if self.revision:
            command += ['--rev', self.revision]
        elif self.branchType == 'inrepo':
            command += ['--rev', self.update_branch]
        d = self._dovccmd(command)
        return d

    def checkHg(self):
        d = self._dovccmd(['--version'])
        def check(res):
            if res == 0:
                return True
            return False
        d.addCallback(check)
        return d

