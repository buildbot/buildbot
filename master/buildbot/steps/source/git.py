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

from buildbot import config
from buildbot.process import buildstep
from buildbot.steps.source.base import Source
from buildbot.interfaces import BuildSlaveTooOldError

def isTrueOrIsExactlyZero(v):
    # nonzero values are true...
    if v:
        return True
    
    # ... and True for the number zero, but we have to
    # explicitly guard against v==False, since
    # isinstance(False, int) is surprisingly True
    if isinstance(v, int) and v is not False:
        return True
    
    # all other false-ish values are false
    return False

git_describe_flags = [
    # on or off
    ('all',         lambda v: ['--all'] if v else None),
    ('always',      lambda v: ['--always'] if v else None),
    ('contains',    lambda v: ['--contains'] if v else None),
    ('debug',       lambda v: ['--debug'] if v else None),
    ('long',        lambda v: ['--long'] if v else None),
    ('exact-match', lambda v: ['--exact-match'] if v else None),
    ('tags',        lambda v: ['--tags'] if v else None),
    # string parameter
    ('match',       lambda v: ['--match', v] if v else None),
    # numeric parameter
    ('abbrev',      lambda v: ['--abbrev=%s' % v] if isTrueOrIsExactlyZero(v) else None),
    ('candidates',  lambda v: ['--candidates=%s' % v] if isTrueOrIsExactlyZero(v) else None),
    # optional string parameter
    ('dirty',       lambda v: ['--dirty'] if (v is True or v=='') else None),
    ('dirty',       lambda v: ['--dirty=%s' % v] if (v and v is not True) else None),
]

class Git(Source):
    """ Class for Git with all the smarts """
    name='git'
    renderables = [ "repourl"]

    def __init__(self, repourl=None, branch='HEAD', mode='incremental',
                 method=None, submodules=False, shallow=False, progress=False,
                 retryFetch=False, clobberOnFailure=False, getDescription=False,
                 **kwargs):
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
        
        @type  getDescription: boolean or dict
        @param getDescription: Use 'git describe' to describe the fetched revision
        """
        if not getDescription and not isinstance(getDescription, dict):
            getDescription = False

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
        self.getDescription = getDescription
        Source.__init__(self, **kwargs)

        if self.mode not in ['incremental', 'full']:
            config.error("Git: mode must be 'incremental' or 'full'.")
        if not self.repourl:
            config.error("Git: must provide repourl.")
        if (self.mode == 'full' and
                self.method not in ['clean', 'fresh', 'clobber', 'copy', None]):
            config.error("Git: invalid method for mode 'full'.")
        if self.shallow and (self.mode != 'full' or self.method != 'clobber'):
            config.error("Git: shallow only possible with mode 'full' and method 'clobber'.")
        if not isinstance(self.getDescription, (bool, dict)):
            config.error("Git: getDescription must be a boolean or a dict.")

    def startVC(self, branch, revision, patch):
        self.branch = branch or 'HEAD'
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = self.addLogForRemoteCommands("stdio")

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
        d.addCallback(self.parseCommitDescription)
        d.addCallback(self.finish)
        d.addErrback(self.failed)
        return d

    @defer.inlineCallbacks
    def full(self):
        if self.method == 'clobber':
            yield self.clobber()
            return
        elif self.method == 'copy':
            yield self.copy()
            return

        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            log.msg("No git repo present, making full clone")
            yield self._fullCloneOrFallback()
        elif self.method == 'clean':
            yield self.clean()
        elif self.method == 'fresh':
            yield self.fresh()
        else:
            raise ValueError("Unknown method, check your configuration")

    @defer.inlineCallbacks
    def incremental(self):
        updatable = yield self._sourcedirIsUpdatable()

        # if not updateable, do a full checkout
        if not updatable:
            yield self._fullCloneOrFallback()
            return

        # test for existence of the revision; rc=1 indicates it does not exist
        if self.revision:
            rc = yield self._dovccmd(['cat-file', '-e', self.revision],
                    abandonOnFailure=False)
        else:
            rc = 1

        # if revision exists checkout to that revision
        # else fetch and update
        if rc == 0:
            yield self._dovccmd(['reset', '--hard', self.revision, '--'])

            if self.branch != 'HEAD':
                yield self._dovccmd(['branch', '-M', self.branch],
                        abandonOnFailure=False)
        else:
            yield self._fetchOrFallback(None)

        yield self._updateSubmodule(None)

    def clean(self):
        command = ['clean', '-f', '-d']
        d = self._dovccmd(command)
        d.addCallback(self._fetchOrFallback)
        d.addCallback(self._updateSubmodule)
        d.addCallback(self._cleanSubmodule)
        return d

    def clobber(self):
        d = self._doClobber()
        d.addCallback(lambda _: self._fullClone(shallowClone=self.shallow))
        return d

    def fresh(self):
        command = ['clean', '-f', '-d', '-x']
        d = self._dovccmd(command)
        d.addCallback(self._fetchOrFallback)
        d.addCallback(self._updateSubmodule)
        d.addCallback(self._cleanSubmodule)
        return d

    def copy(self):
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.workdir,
                                                'logEnviron': self.logEnviron,
                                                'timeout': self.timeout,})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)

        self.workdir = 'source'
        d.addCallback(lambda _: self.incremental())
        def copy(_):
            cmd = buildstep.RemoteCommand('cpdir',
                                          {'fromdir': 'source',
                                           'todir':'build',
                                           'logEnviron': self.logEnviron,
                                           'timeout': self.timeout,})
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

    @defer.inlineCallbacks
    def parseGotRevision(self, _=None):
        stdout = yield self._dovccmd(['rev-parse', 'HEAD'], collectStdout=True)
        revision = stdout.strip()
        if len(revision) != 40:
            raise buildstep.BuildStepFailed()
        log.msg("Got Git revision %s" % (revision, ))
        self.updateSourceProperty('got_revision', revision)
    
        defer.returnValue(0)

    @defer.inlineCallbacks
    def parseCommitDescription(self, _=None):
        if self.getDescription==False: # dict() should not return here
            defer.returnValue(0)
            return
        
        cmd = ['describe']
        if isinstance(self.getDescription, dict):
            for opt, arg in git_describe_flags:
                opt = self.getDescription.get(opt, None)
                arg = arg(opt)
                if arg:
                    cmd.extend(arg)            
        cmd.append('HEAD')
        
        try:
            stdout = yield self._dovccmd(cmd, collectStdout=True)
            desc = stdout.strip()
            self.updateSourceProperty('commit-description', desc)
        except:
            pass
            
        defer.returnValue(0)

    def _dovccmd(self, command, abandonOnFailure=True, collectStdout=False, initialStdin=None):
        cmd = buildstep.RemoteShellCommand(self.workdir, ['git'] + command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout,
                                           collectStdout=collectStdout,
                                           initialStdin=initialStdin)
        cmd.useLog(self.stdio_log, False)
        log.msg("Starting git command : git %s" % (" ".join(command), ))
        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if abandonOnFailure and cmd.didFail():
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
            command = ['reset', '--hard', rev, '--']
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

    @defer.inlineCallbacks
    def _fetchOrFallback(self, _):
        """
        Handles fallbacks for failure of fetch,
        wrapper for self._fetch
        """
        res = yield self._fetch(None)
        if res == 0:
            defer.returnValue(res)
            return
        elif self.retryFetch:
            yield self._fetch(None)
        elif self.clobberOnFailure:
            yield self._doClobber()
            yield self._fullClone()
        else:
            raise buildstep.BuildStepFailed()

    def _fullClone(self, shallowClone=False):
        """Perform full clone and checkout to the revision if specified
           In the case of shallow clones if any of the step fail abort whole build step.
        """
        args = []
        if self.branch != 'HEAD':
            args += ['--branch', self.branch]
        if shallowClone:
            args += ['--depth', '1']
        command = ['clone'] + args + [self.repourl, '.']

        #Fix references
        if self.prog:
            command.append('--progress')

        # If it's a shallow clone abort build step
        d = self._dovccmd(command, shallowClone)
        # If revision specified checkout that revision
        if self.revision:
            d.addCallback(lambda _: self._dovccmd(['reset', '--hard',
                                                   self.revision, '--'],
                                                   shallowClone))
        # init and update submodules, recurisively. If there's not recursion
        # it will not do it.
        if self.submodules:
            d.addCallback(lambda _: self._dovccmd(['submodule', 'update',
                                                   '--init', '--recursive'],
                                                  shallowClone))
        return d

    def _fullCloneOrFallback(self):
        """Wrapper for _fullClone(). In the case of failure, if clobberOnFailure 
           is set to True remove the build directory and try a full clone again.
        """

        d = self._fullClone()
        def clobber(res):
            if res != 0:
                if self.clobberOnFailure:
                    d = self._doClobber()
                    d.addCallback(lambda _: self._fullClone())
                    return d
                else:
                    raise buildstep.BuildStepFailed()
            else:
                return res
        d.addCallback(clobber)
        return d

    def _doClobber(self):
        """Remove the work directory"""
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.workdir,
                                                'logEnviron': self.logEnviron,
                                                'timeout': self.timeout,})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def checkRemoval(res):
            if res != 0:
                raise RuntimeError("Failed to delete directory")
            return res
        d.addCallback(lambda _: checkRemoval(cmd.rc))
        return d

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return changes[-1].revision

    def _sourcedirIsUpdatable(self):
        return self.pathExists(self.build.path_module.join(self.workdir, '.git'))

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

    def patch(self, _, patch):
        d = self._dovccmd(['apply', '--index', '-p', str(patch[0])],
                initialStdin=patch[1])
        return d
