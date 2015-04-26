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

from distutils.version import LooseVersion
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot import config as bbconfig
from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.steps.source.base import Source


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
    ('all', lambda v: ['--all'] if v else None),
    ('always', lambda v: ['--always'] if v else None),
    ('contains', lambda v: ['--contains'] if v else None),
    ('debug', lambda v: ['--debug'] if v else None),
    ('long', lambda v: ['--long'] if v else None),
    ('exact-match', lambda v: ['--exact-match'] if v else None),
    ('tags', lambda v: ['--tags'] if v else None),
    # string parameter
    ('match', lambda v: ['--match', v] if v else None),
    # numeric parameter
    ('abbrev', lambda v: ['--abbrev=%s' % v] if isTrueOrIsExactlyZero(v) else None),
    ('candidates', lambda v: ['--candidates=%s' % v] if isTrueOrIsExactlyZero(v) else None),
    # optional string parameter
    ('dirty', lambda v: ['--dirty'] if (v is True or v == '') else None),
    ('dirty', lambda v: ['--dirty=%s' % v] if (v and v is not True) else None),
]


class Git(Source):

    """ Class for Git with all the smarts """
    name = 'git'
    renderables = ["repourl", "reference", "branch", "codebase", "mode", "method"]

    def __init__(self, repourl=None, branch='HEAD', mode='incremental', method=None,
                 reference=None, submodules=False, shallow=False, progress=False, retryFetch=False,
                 clobberOnFailure=False, getDescription=False, config=None, **kwargs):
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

        @type reference: string
        @param reference: If available use a reference repo.
                          Uses `--reference` in git command. Refer `git clone --help`
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

        @type  config: dict
        @param config: Git configuration options to enable when running git
        """
        if not getDescription and not isinstance(getDescription, dict):
            getDescription = False

        self.branch = branch
        self.method = method
        self.prog = progress
        self.repourl = repourl
        self.reference = reference
        self.retryFetch = retryFetch
        self.submodules = submodules
        self.shallow = shallow
        self.fetchcount = 0
        self.clobberOnFailure = clobberOnFailure
        self.mode = mode
        self.getDescription = getDescription
        self.config = config
        self.supportsBranch = True
        self.supportsSubmoduleCheckout = True
        self.srcdir = 'source'
        Source.__init__(self, **kwargs)

        if not self.repourl:
            bbconfig.error("Git: must provide repourl.")
        if isinstance(self.mode, basestring):
            if not self._hasAttrGroupMember('mode', self.mode):
                bbconfig.error("Git: mode must be %s" %
                               (' or '.join(self._listAttrGroupMembers('mode'))))
            if isinstance(self.method, basestring):
                if (self.mode == 'full' and self.method not in ['clean', 'fresh', 'clobber', 'copy', None]):
                    bbconfig.error("Git: invalid method for mode 'full'.")
                if self.shallow and (self.mode != 'full' or self.method != 'clobber'):
                    bbconfig.error("Git: shallow only possible with mode 'full' and method 'clobber'.")
        if not isinstance(self.getDescription, (bool, dict)):
            bbconfig.error("Git: getDescription must be a boolean or a dict.")

    def startVC(self, branch, revision, patch):
        self.branch = branch or 'HEAD'
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = self.addLogForRemoteCommands("stdio")

        d = self.checkBranchSupport()

        @d.addCallback
        def checkInstall(gitInstalled):
            if not gitInstalled:
                raise BuildSlaveTooOldError("git is not installed on slave")
            return 0

        d.addCallback(lambda _: self.sourcedirIsPatched())

        @d.addCallback
        def checkPatched(patched):
            if patched:
                return self._dovccmd(['clean', '-f', '-f', '-d', '-x'])
            else:
                return 0

        d.addCallback(self._getAttrGroupMember('mode', self.mode))
        if patch:
            d.addCallback(self.patch, patch)
        d.addCallback(self.parseGotRevision)
        d.addCallback(self.parseCommitDescription)
        d.addCallback(self.finish)
        d.addErrback(self.failed)
        return d

    @defer.inlineCallbacks
    def mode_full(self, _):
        if self.method == 'clobber':
            yield self.clobber()
            return
        elif self.method == 'copy':
            yield self.copy()
            return

        action = yield self._sourcedirIsUpdatable()
        if action == "clobber":
            yield self.clobber()
            return
        elif action == "clone":
            log.msg("No git repo present, making full clone")
            yield self._fullCloneOrFallback()
        elif self.method == 'clean':
            yield self.clean()
        elif self.method == 'fresh':
            yield self.fresh()
        else:
            raise ValueError("Unknown method, check your configuration")

    @defer.inlineCallbacks
    def mode_incremental(self, _):
        action = yield self._sourcedirIsUpdatable()
        # if not updateable, do a full checkout
        if action == "clobber":
            yield self.clobber()
            return
        elif action == "clone":
            log.msg("No git repo present, making full clone")
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
            yield self._fetchOrFallback()

        yield self._syncSubmodule(None)
        yield self._updateSubmodule(None)

    def clean(self):
        command = ['clean', '-f', '-f', '-d']
        d = self._dovccmd(command)
        d.addCallback(self._fetchOrFallback)
        d.addCallback(self._syncSubmodule)
        d.addCallback(self._updateSubmodule)
        d.addCallback(self._cleanSubmodule)
        return d

    @defer.inlineCallbacks
    def clobber(self):
        yield self._doClobber()
        res = yield self._fullClone(shallowClone=self.shallow)
        if res != 0:
            raise buildstep.BuildStepFailed

    @defer.inlineCallbacks
    def fresh(self):
        res = yield self._dovccmd(['clean', '-f', '-f', '-d', '-x'],
                                  abandonOnFailure=False)
        if res == 0:
            yield self._fetchOrFallback()
        else:
            yield self._doClobber()
            yield self._fullCloneOrFallback()
        yield self._syncSubmodule()
        yield self._updateSubmodule()
        yield self._cleanSubmodule()

    def copy(self):
        cmd = remotecommand.RemoteCommand('rmdir', {'dir': self.workdir,
                                                    'logEnviron': self.logEnviron,
                                                    'timeout': self.timeout, })
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)

        old_workdir = self.workdir
        self.workdir = self.srcdir
        d.addCallback(self.mode_incremental)

        @d.addCallback
        def copy(_):
            cmd = remotecommand.RemoteCommand('cpdir',
                                              {'fromdir': self.srcdir,
                                               'todir': old_workdir,
                                               'logEnviron': self.logEnviron,
                                               'timeout': self.timeout, })
            cmd.useLog(self.stdio_log, False)
            d = self.runCommand(cmd)
            return d

        @d.addCallback
        def resetWorkdir(_):
            self.workdir = old_workdir
            return 0
        return d

    def finish(self, res):
        d = defer.succeed(res)

        @d.addCallback
        def _gotResults(results):
            self.setStatus(self.cmd, results)
            log.msg("Closing log, sending result of the command %s " %
                    (self.cmd))
            return results
        d.addCallback(self.finished)
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
        if self.getDescription == False:  # dict() should not return here
            defer.returnValue(0)
            return

        cmd = ['describe']
        if isinstance(self.getDescription, dict):
            for opt, arg in git_describe_flags:
                opt = self.getDescription.get(opt, None)
                arg = arg(opt)
                if arg:
                    cmd.extend(arg)
        # 'git describe' takes a commitish as an argument for all options
        # *except* --dirty
        if not any(arg.startswith('--dirty') for arg in cmd):
            cmd.append('HEAD')

        try:
            stdout = yield self._dovccmd(cmd, collectStdout=True)
            desc = stdout.strip()
            self.updateSourceProperty('commit-description', desc)
        except Exception:
            pass

        defer.returnValue(0)

    def _dovccmd(self, command, abandonOnFailure=True, collectStdout=False, initialStdin=None):
        full_command = ['git']
        if self.config is not None:
            for name, value in self.config.iteritems():
                full_command.append('-c')
                full_command.append('%s=%s' % (name, value))
        full_command.extend(command)
        cmd = remotecommand.RemoteShellCommand(self.workdir,
                                               full_command,
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout,
                                               collectStdout=collectStdout,
                                               initialStdin=initialStdin)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)

        @d.addCallback
        def evaluateCommand(_):
            if abandonOnFailure and cmd.didFail():
                log.msg("Source step failed while running command %s" % cmd)
                raise buildstep.BuildStepFailed()
            if collectStdout:
                return cmd.stdout
            else:
                return cmd.rc
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

        @d.addCallback
        def checkout(_):
            if self.revision:
                rev = self.revision
            else:
                rev = 'FETCH_HEAD'
            command = ['reset', '--hard', rev, '--']
            abandonOnFailure = not self.retryFetch and not self.clobberOnFailure
            return self._dovccmd(command, abandonOnFailure)

        if self.branch != 'HEAD':
            @d.addCallback
            def renameBranch(res):
                if res:
                    return res
                d = self._dovccmd(['branch', '-M', self.branch], abandonOnFailure=False)
                # Ignore errors
                d.addCallback(lambda _: res)
                return d
        return d

    @defer.inlineCallbacks
    def _fetchOrFallback(self, _=None):
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
            yield self.clobber()
        else:
            raise buildstep.BuildStepFailed()

    def _clone(self, shallowClone):
        """Retry if clone failed"""

        args = []
        switchToBranch = False
        if self.supportsBranch and self.branch != 'HEAD':
            if self.branch.startswith('refs/'):
                # we can't choose this branch from 'git clone' directly; we
                # must do so after the clone
                switchToBranch = True
                args += ['--no-checkout']
            else:
                args += ['--branch', self.branch]
        if shallowClone:
            args += ['--depth', '1']
        if self.reference:
            args += ['--reference', self.reference]
        command = ['clone'] + args + [self.repourl, '.']

        if self.prog:
            command.append('--progress')
        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True
        # If it's a shallow clone abort build step
        d = self._dovccmd(command, abandonOnFailure=(abandonOnFailure and shallowClone))

        if switchToBranch:
            d.addCallback(lambda _: self._fetch(None))

        def _retry(res):
            if self.stopped or res == 0:  # or shallow clone??
                return res
            delay, repeats = self.retry
            if repeats > 0:
                log.msg("Checkout failed, trying %d more times after %d seconds"
                        % (repeats, delay))
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self._doClobber())
                df.addCallback(lambda _: self._clone(shallowClone))
                reactor.callLater(delay, df.callback, None)
                return df
            return res

        if self.retry:
            d.addCallback(_retry)
        return d

    @defer.inlineCallbacks
    def _fullClone(self, shallowClone=False):
        """Perform full clone and checkout to the revision if specified
           In the case of shallow clones if any of the step fail abort whole build step.
        """
        res = yield self._clone(shallowClone)
        if res != 0:
            defer.returnValue(res)
            return

        # If revision specified checkout that revision
        if self.revision:
            res = yield self._dovccmd(['reset', '--hard',
                                       self.revision, '--'],
                                      shallowClone)
        # init and update submodules, recurisively. If there's not recursion
        # it will not do it.
        if self.submodules:
            res = yield self._dovccmd(['submodule', 'update',
                                       '--init', '--recursive'],
                                      shallowClone)

        defer.returnValue(res)

    def _fullCloneOrFallback(self):
        """Wrapper for _fullClone(). In the case of failure, if clobberOnFailure
           is set to True remove the build directory and try a full clone again.
        """

        d = self._fullClone()

        @d.addCallback
        def clobber(res):
            if res != 0:
                if self.clobberOnFailure:
                    return self.clobber()
                else:
                    raise buildstep.BuildStepFailed()
            else:
                return res
        return d

    def _doClobber(self):
        """Remove the work directory"""
        cmd = remotecommand.RemoteCommand('rmdir', {'dir': self.workdir,
                                                    'logEnviron': self.logEnviron,
                                                    'timeout': self.timeout, })
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)

        @d.addCallback
        def checkRemoval(_):
            if cmd.rc != 0:
                raise RuntimeError("Failed to delete directory")
            return cmd.rc
        return d

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return changes[-1].revision

    def _syncSubmodule(self, _=None):
        if self.submodules:
            return self._dovccmd(['submodule', 'sync'])
        else:
            return defer.succeed(0)

    def _updateSubmodule(self, _=None):
        if self.submodules:
            vccmd = ['submodule', 'update', '--init', '--recursive', '--force']
            if self.supportsSubmoduleCheckout:
                vccmd.extend(['--checkout'])
            return self._dovccmd(vccmd)
        else:
            return defer.succeed(0)

    def _cleanSubmodule(self, _=None):
        if self.submodules:
            command = ['submodule', 'foreach', '--recursive', 'git', 'clean', '-f', '-f', '-d']
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

    def checkBranchSupport(self):
        d = self._dovccmd(['--version'], collectStdout=True)

        @d.addCallback
        def checkSupport(stdout):
            gitInstalled = False
            if 'git' in stdout:
                gitInstalled = True
            version = stdout.strip().split(' ')[2]
            if LooseVersion(version) < LooseVersion("1.6.5"):
                self.supportsBranch = False
            if LooseVersion(version) < LooseVersion("1.7.8"):
                self.supportsSubmoduleCheckout = False
            return gitInstalled
        return d

    def applyPatch(self, patch):
        d = self._dovccmd(['update-index', '--refresh'])

        @d.addCallback
        def applyAlready(res):
            return self._dovccmd(['apply', '--index', '-p', str(patch[0])], initialStdin=patch[1])
        return d

    def _sourcedirIsUpdatable(self):
        if self.slaveVersionIsOlderThan('listdir', '2.16'):
            d = self.pathExists(self.build.path_module.join(self.workdir, '.git'))

            @d.addCallback
            def checkWithPathExists(exists):
                if(exists):
                    return "update"
                else:
                    return "clone"
        else:
            cmd = buildstep.RemoteCommand('listdir',
                                          {'dir': self.workdir,
                                           'logEnviron': self.logEnviron,
                                           'timeout': self.timeout, })
            cmd.useLog(self.stdio_log, False)
            d = self.runCommand(cmd)

            @d.addCallback
            def checkWithListdir(_):
                if 'files' not in cmd.updates:
                    # no files - directory doesn't exist
                    return "clone"
                files = cmd.updates['files'][0]
                if '.git' in files:
                    return "update"
                elif len(files) > 0:
                    return "clobber"
                else:
                    return "clone"
        return d
