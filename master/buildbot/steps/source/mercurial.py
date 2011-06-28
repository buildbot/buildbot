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

from twisted.python import log, failure
from twisted.internet import defer

from buildbot.process import buildstep
from buildbot.steps.source import Source, _ComputeRepositoryURL
from buildbot.interfaces import BuildSlaveTooOldError

class Mercurial(Source):
    """ Class for Mercurial with all the smarts """
    name = "hg"

    renderables = [ "repourl", "baseURL" ]

    def __init__(self, repourl=None, baseURL=None, mode='incremental', 
                 method=None, defaultBranch=None, branchType='dirname', 
                 clobberOnBranchChange=True, **kwargs):

        """
        @type  repourl: string
        @param repourl: the URL which points at the Mercurial repository.
                        This uses the 'default' branch unless defaultBranch is
                        specified below and the C{branchType} is set to
                        'inrepo'.  It is an error to specify a branch without
                        setting the C{branchType} to 'inrepo'.

        @param baseURL: if 'dirname' branches are enabled, this is the base URL
                        to which a branch name will be appended. It should
                        probably end in a slash.  Use exactly one of C{repourl}
                        and C{baseURL}.

        @param defaultBranch: if branches are enabled, this is the branch
                              to use if the Build does not specify one
                              explicitly.
                              For 'dirname' branches, It will simply be
                              appended to C{baseURL} and the result handed to
                              the 'hg update' command.
                              For 'inrepo' branches, this specifies the named
                              revision to which the tree will update after a
                              clone.

        @param branchType: either 'dirname' or 'inrepo' depending on whether
                           the branch name should be appended to the C{baseURL}
                           or the branch is a mercurial named branch and can be
                           found within the C{repourl}

        @param clobberOnBranchChange: boolean, defaults to True. If set and
                                      using inrepos branches, clobber the tree
                                      at each branch change. Otherwise, just
                                      update to the branch.
        """
        
        self.repourl = repourl
        self.baseURL = baseURL
        self.defaultBranch = self.branch = defaultBranch
        self.branchType = branchType
        self.method = method
        self.clobberOnBranchChange = clobberOnBranchChange
        Source.__init__(self, **kwargs)
        self.mode = mode
        self.addFactoryArguments(repourl=repourl,
                                 baseURL=baseURL,
                                 mode=mode,
                                 method=method,
                                 defaultBranch=defaultBranch,
                                 branchType=branchType,
                                 clobberOnBranchChange=
                                 clobberOnBranchChange,
                                 )

        assert self.mode in ['incremental', 'full']

        if repourl and baseURL:
            raise ValueError("you must provide exactly one of repourl and"
                             " baseURL")

        if repourl is None and baseURL is None:
            raise ValueError("you must privide at least one of repourl and"
                             " baseURL")

        self.repourl = self.repourl and _ComputeRepositoryURL(self.repourl)
        self.baseURL = self.baseURL and _ComputeRepositoryURL(self.baseURL)
        
    def startVC(self, branch, revision, patch):
        
        slavever = self.slaveVersion('hg')
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about hg")
        self.revision = revision
        self.method = self._getMethod()

        if self.branchType == 'dirname':
            assert self.repourl is None
            self.repourl = self.baseURL + (branch or '')
            self.branch = self.defaultBranch
            self.update_branch = branch
        elif self.branchType == 'inrepo':
            assert self.baseURL is None
            self.update_branch = (branch or 'default')
        else:
            raise ValueError("Invalid branch type")
        
        self.stdio_log = self.addLog("stdio")

        if self.mode == 'full':
            d = self.full()
        elif self.mode == 'incremental':
            d = self.incremental()
        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        d.addErrback(self.failed)

    @defer.deferredGenerator
    def full(self):
        if self.method == 'clobber':
            d = self.clobber(None)
            wfd = defer.waitForDeferred(d)
            yield wfd
            return

        wfd = defer.waitForDeferred(self._sourcedirIsUpdatable())
        yield wfd
        updatable = wfd.getResult()
        if not updatable:
            d = self._dovccmd(['clone', self.repourl, '.'])
        elif self.method == 'clean':
            d = self.clean(None)
        elif self.method == 'fresh':
            d = self.fresh(None)
        else:
            raise ValueError("Unknow method, check your configuration")
        wfd = defer.waitForDeferred(d)
        yield wfd

    def incremental(self):
        if self.method is not None:
            raise ValueError(self.method)

        d = self._sourcedirIsUpdatable()
        def _cmd(updatable):
            if updatable:
                command = ['pull', self.repourl, '--update']
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
        cmd = buildstep.LoggedRemoteCommand('rmdir', {'dir': self.workdir})
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
        d = self._dovccmd(['identify', '--id', '--debug'])
        def _setrev(res):
            revision = self.getLog('stdio').readlines()[-1].strip()
            if len(revision) != 40:
                raise ValueError("Incorrect revision id")
            log.msg("Got Mercurial revision %s" % (revision, ))
            self.setProperty('got_revision', revision, 'Source')
            return res
        d.addCallback(_setrev)
        return d

    @defer.deferredGenerator
    def _checkBranchChange(self, _):
        d = self._getCurrentBranch()
        wfd = defer.waitForDeferred(d)
        yield wfd
        current_branch = wfd.getResult()
        msg = "Working dir is on in-repo branch '%s' and build needs '%s'." % \
              (current_branch, self.update_branch)
        if current_branch != self.update_branch:
            if self.clobberOnBranchChange:
                msg += ' Clobbering.'
                log.msg(msg)
                d = self.clobber(None)
            else:
                msg += ' Updating.'
                log.msg(msg)
                d = self._update(None)
        else:
            msg += ' Updating.'
            log.msg(msg)
            d = self._update(None)

        wfd = defer.waitForDeferred(d)
        yield wfd

    def _pullUpdate(self, res):
        command = ['pull' , self.repourl]
        if self.revision:
            command.extend(['--rev', self.revision])
        d = self._dovccmd(command)
        d.addCallback(self._checkBranchChange)
        return d

    def _dovccmd(self, command):
        if not command:
            raise ValueError("No command specified")
        cmd = buildstep.RemoteShellCommand(self.workdir, ['hg', '--verbose'] + command)
        cmd.useLog(self.stdio_log, False)
        log.msg("Starting mercurial command : hg %s" % (" ".join(command), ))
        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if cmd.rc != 0:
                log.msg("Source step failed while running command %s" % cmd)
                raise failure.Failure(cmd.rc)
            return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

    def _getCurrentBranch(self):
        if self.branchType == 'dirname':
            return defer.succeed(self.branch)
        else:
            d = self._dovccmd(['identify', '--branch'])
            def _getbranch(res):
                branch = self.getLog('stdio').readlines()[-1].strip()
                return branch
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
        cmd = buildstep.LoggedRemoteCommand('stat', {'file': self.workdir + '/.hg'})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def _fail(tmp):
            if cmd.rc != 0:
                return False
            return True
        d.addCallback(_fail)
        return d

    def _update(self, _):
        command = ['update', '--clean']
        if self.revision:
            command += ['--rev', self.revision]
        d = self._dovccmd(command)
        return d
