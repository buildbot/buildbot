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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems
from future.utils import string_types

from distutils.version import LooseVersion

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot import config as bbconfig
from buildbot.interfaces import WorkerTooOldError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.steps.source.base import Source

RC_SUCCESS = 0
GIT_HASH_LENGTH = 40


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
    ('abbrev', lambda v: ['--abbrev=%s' % v]
     if isTrueOrIsExactlyZero(v) else None),
    ('candidates', lambda v: ['--candidates=%s' %
                              v] if isTrueOrIsExactlyZero(v) else None),
    # optional string parameter
    ('dirty', lambda v: ['--dirty'] if (v is True or v == '') else None),
    ('dirty', lambda v: ['--dirty=%s' % v] if (v and v is not True) else None),
]


class Git(Source):

    """ Class for Git with all the smarts """
    name = 'git'
    renderables = ["repourl", "reference", "branch",
                   "codebase", "mode", "method", "origin"]

    def __init__(self, repourl=None, branch='HEAD', mode='incremental', method=None,
                 reference=None, submodules=False, shallow=False, progress=False, retryFetch=False,
                 clobberOnFailure=False, getDescription=False, config=None, origin=None, **kwargs):
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

        @type  shallow: boolean or integer
        @param shallow: Use a shallow or clone, if possible

        @type  retryFetch: boolean
        @param retryFetch: Retry fetching before failing source checkout.

        @type  getDescription: boolean or dict
        @param getDescription: Use 'git describe' to describe the fetched revision

        @type origin: string
        @param origin: The name to give the remote when cloning (default None)

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
        self.clobberOnFailure = clobberOnFailure
        self.mode = mode
        self.getDescription = getDescription
        self.config = config
        self.supportsBranch = True
        self.supportsSubmoduleCheckout = True
        self.srcdir = 'source'
        self.origin = origin
        Source.__init__(self, **kwargs)
        if not self.repourl:
            bbconfig.error("Git: must provide repourl.")
        if isinstance(self.mode, string_types):
            if not self._hasAttrGroupMember('mode', self.mode):
                bbconfig.error("Git: mode must be %s" %
                               (' or '.join(self._listAttrGroupMembers('mode'))))
            if isinstance(self.method, string_types):
                if (self.mode == 'full' and self.method not in ['clean', 'fresh', 'clobber', 'copy', None]):
                    bbconfig.error("Git: invalid method for mode 'full'.")
                if self.shallow and (self.mode != 'full' or self.method != 'clobber'):
                    bbconfig.error(
                        "Git: shallow only possible with mode 'full' and method 'clobber'.")
        if not isinstance(self.getDescription, (bool, dict)):
            bbconfig.error("Git: getDescription must be a boolean or a dict.")

    @defer.inlineCallbacks
    def startVC(self, branch, revision, patch):
        self.branch = branch or 'HEAD'
        self.revision = revision

        self.method = self._getMethod()
        self.stdio_log = self.addLogForRemoteCommands("stdio")

        try:
            gitInstalled = yield self.checkBranchSupport()

            if not gitInstalled:
                raise WorkerTooOldError("git is not installed on worker")

            patched = yield self.sourcedirIsPatched()

            if patched:
                yield self._dovccmd(['clean', '-f', '-f', '-d', '-x'])

            yield self._getAttrGroupMember('mode', self.mode)()
            if patch:
                yield self.patch(None, patch=patch)
            yield self.parseGotRevision()
            res = yield self.parseCommitDescription()
            yield self.finish(res)
        except Exception as e:
            yield self.failed(e)

    @defer.inlineCallbacks
    def mode_full(self):
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
    def mode_incremental(self):
        action = yield self._sourcedirIsUpdatable()
        # if not updatable, do a full checkout
        if action == "clobber":
            yield self.clobber()
            return
        elif action == "clone":
            log.msg("No git repo present, making full clone")
            yield self._fullCloneOrFallback()
            return

        yield self._fetchOrFallback()

        yield self._syncSubmodule(None)
        yield self._updateSubmodule(None)

    @defer.inlineCallbacks
    def clean(self):
        command = ['clean', '-f', '-f', '-d']
        rc = yield self._dovccmd(command)
        if rc != RC_SUCCESS:
            raise buildstep.BuildStepFailed

        rc = yield self._fetchOrFallback()
        if rc != RC_SUCCESS:
            raise buildstep.BuildStepFailed
        rc = yield self._syncSubmodule()
        if rc != RC_SUCCESS:
            raise buildstep.BuildStepFailed
        rc = yield self._updateSubmodule()
        if rc != RC_SUCCESS:
            raise buildstep.BuildStepFailed
        rc = yield self._cleanSubmodule()
        if rc != RC_SUCCESS:
            raise buildstep.BuildStepFailed
        defer.returnValue(RC_SUCCESS)

    @defer.inlineCallbacks
    def clobber(self):
        yield self._doClobber()
        res = yield self._fullClone(shallowClone=self.shallow)
        if res != RC_SUCCESS:
            raise buildstep.BuildStepFailed

    @defer.inlineCallbacks
    def fresh(self):
        res = yield self._dovccmd(['clean', '-f', '-f', '-d', '-x'],
                                  abandonOnFailure=False)
        if res == RC_SUCCESS:
            yield self._fetchOrFallback()
        else:
            yield self._doClobber()
            yield self._fullCloneOrFallback()
        yield self._syncSubmodule()
        yield self._updateSubmodule()
        yield self._cleanSubmodule()

    @defer.inlineCallbacks
    def copy(self):
        yield self.runRmdir(self.workdir, abandonOnFailure=False,
                            timeout=self.timeout)

        old_workdir = self.workdir
        self.workdir = self.srcdir

        try:
            yield self.mode_incremental()
            cmd = buildstep.RemoteCommand('cpdir',
                                          {'fromdir': self.srcdir,
                                           'todir': old_workdir,
                                           'logEnviron': self.logEnviron,
                                           'timeout': self.timeout, })
            cmd.useLog(self.stdio_log, False)
            yield self.runCommand(cmd)
            if cmd.didFail():
                raise buildstep.BuildStepFailed()
            defer.returnValue(RC_SUCCESS)
        finally:
            self.workdir = old_workdir

    @defer.inlineCallbacks
    def finish(self, res):
        self.setStatus(self.cmd, res)
        log.msg("Closing log, sending result of the command %s " %
                (self.cmd))
        yield self.finished(res)

    @defer.inlineCallbacks
    def parseGotRevision(self, _=None):
        stdout = yield self._dovccmd(['rev-parse', 'HEAD'], collectStdout=True)
        revision = stdout.strip()
        if len(revision) != GIT_HASH_LENGTH:
            raise buildstep.BuildStepFailed()
        log.msg("Got Git revision %s" % (revision, ))
        self.updateSourceProperty('got_revision', revision)

        defer.returnValue(RC_SUCCESS)

    @defer.inlineCallbacks
    def parseCommitDescription(self, _=None):
        # dict() should not return here
        if isinstance(self.getDescription, bool) and not self.getDescription:
            defer.returnValue(RC_SUCCESS)
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

        defer.returnValue(RC_SUCCESS)

    @defer.inlineCallbacks
    def _dovccmd(self, command, abandonOnFailure=True, collectStdout=False, initialStdin=None):
        full_command = ['git']
        if self.config is not None:
            for name, value in iteritems(self.config):
                full_command.append('-c')
                full_command.append('%s=%s' % (name, value))
        full_command.extend(command)

        # check for the interruptSignal flag
        sigtermTime = None
        interruptSignal = None

        # If possible prefer to send a SIGTERM to git before we send a SIGKILL.
        # If we send a SIGKILL, git is prone to leaving around stale lockfiles.
        # By priming it with a SIGTERM first we can ensure that it has a chance to shut-down gracefully
        # before getting terminated
        if not self.workerVersionIsOlderThan("shell", "2.16"):
            # git should shut-down quickly on SIGTERM.  If it doesn't don't let it
            # stick around for too long because this is on top of any timeout
            # we have hit.
            sigtermTime = 1
        else:
            # Since sigtermTime is unavailable try to just use SIGTERM by itself instead of
            # killing.  This should be safe.
            if self.workerVersionIsOlderThan("shell", "2.15"):
                log.msg(
                    "NOTE: worker does not allow master to specify interruptSignal. This may leave a stale lockfile around if the command is interrupted/times out\n")
            else:
                interruptSignal = 'TERM'

        cmd = remotecommand.RemoteShellCommand(self.workdir,
                                               full_command,
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout,
                                               sigtermTime=sigtermTime,
                                               interruptSignal=interruptSignal,
                                               collectStdout=collectStdout,
                                               initialStdin=initialStdin)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if abandonOnFailure and cmd.didFail():
            log.msg("Source step failed while running command %s" % cmd)
            raise buildstep.BuildStepFailed()
        if collectStdout:
            defer.returnValue(cmd.stdout)
            return
        defer.returnValue(cmd.rc)

    @defer.inlineCallbacks
    def _fetch(self, _):
        fetch_required = True

        # If the revision already exists in the repo, we don't need to fetch.
        if self.revision:
            rc = yield self._dovccmd(['cat-file', '-e', self.revision],
                                     abandonOnFailure=False)
            if rc == RC_SUCCESS:
                fetch_required = False

        if fetch_required:
            command = ['fetch', '-t', self.repourl, self.branch]
            # If the 'progress' option is set, tell git fetch to output
            # progress information to the log. This can solve issues with
            # long fetches killed due to lack of output, but only works
            # with Git 1.7.2 or later.
            if self.prog:
                command.append('--progress')

            yield self._dovccmd(command)

        if self.revision:
            rev = self.revision
        else:
            rev = 'FETCH_HEAD'
        command = ['reset', '--hard', rev, '--']
        abandonOnFailure = not self.retryFetch and not self.clobberOnFailure
        res = yield self._dovccmd(command, abandonOnFailure)

        # Rename the branch if needed.
        if res == RC_SUCCESS and self.branch != 'HEAD':
            # Ignore errors
            yield self._dovccmd(['branch', '-M', self.branch], abandonOnFailure=False)

        defer.returnValue(res)

    @defer.inlineCallbacks
    def _fetchOrFallback(self, _=None):
        """
        Handles fallbacks for failure of fetch,
        wrapper for self._fetch
        """
        res = yield self._fetch(None)
        if res == RC_SUCCESS:
            defer.returnValue(res)
            return
        elif self.retryFetch:
            yield self._fetch(None)
        elif self.clobberOnFailure:
            yield self.clobber()
        else:
            raise buildstep.BuildStepFailed()

    @defer.inlineCallbacks
    def _clone(self, shallowClone):
        """Retry if clone failed"""

        command = ['clone']
        switchToBranch = False
        if self.supportsBranch and self.branch != 'HEAD':
            if self.branch.startswith('refs/'):
                # we can't choose this branch from 'git clone' directly; we
                # must do so after the clone
                switchToBranch = True
                command += ['--no-checkout']
            else:
                command += ['--branch', self.branch]
        if shallowClone:
            command += ['--depth', str(int(shallowClone))]
        if self.reference:
            command += ['--reference', self.reference]
        if self.origin:
            command += ['--origin', self.origin]
        command += [self.repourl, '.']

        if self.prog:
            command.append('--progress')
        if self.retry:
            abandonOnFailure = (self.retry[1] <= 0)
        else:
            abandonOnFailure = True
        # If it's a shallow clone abort build step
        res = yield self._dovccmd(command, abandonOnFailure=(abandonOnFailure and shallowClone))

        if switchToBranch:
            res = yield self._fetch(None)

        done = self.stopped or res == RC_SUCCESS  # or shallow clone??
        if self.retry and not done:
            delay, repeats = self.retry
            if repeats > 0:
                log.msg("Checkout failed, trying %d more times after %d seconds"
                        % (repeats, delay))
                self.retry = (delay, repeats - 1)

                df = defer.Deferred()
                df.addCallback(lambda _: self._doClobber())
                df.addCallback(lambda _: self._clone(shallowClone))
                reactor.callLater(delay, df.callback, None)
                res = yield df

        defer.returnValue(res)

    @defer.inlineCallbacks
    def _fullClone(self, shallowClone=False):
        """Perform full clone and checkout to the revision if specified
           In the case of shallow clones if any of the step fail abort whole build step.
        """
        res = yield self._clone(shallowClone)
        if res != RC_SUCCESS:
            defer.returnValue(res)
            return

        # If revision specified checkout that revision
        if self.revision:
            res = yield self._dovccmd(['reset', '--hard',
                                       self.revision, '--'],
                                      shallowClone)
        # init and update submodules, recursively. If there's not recursion
        # it will not do it.
        if self.submodules:
            res = yield self._dovccmd(['submodule', 'update',
                                       '--init', '--recursive'],
                                      shallowClone)

        defer.returnValue(res)

    @defer.inlineCallbacks
    def _fullCloneOrFallback(self):
        """Wrapper for _fullClone(). In the case of failure, if clobberOnFailure
           is set to True remove the build directory and try a full clone again.
        """

        res = yield self._fullClone()
        if res != RC_SUCCESS:
            if not self.clobberOnFailure:
                raise buildstep.BuildStepFailed()
            res = yield self.clobber()
        defer.returnValue(res)

    @defer.inlineCallbacks
    def _doClobber(self):
        """Remove the work directory"""
        rc = yield self.runRmdir(self.workdir, timeout=self.timeout)
        if rc != RC_SUCCESS:
            raise RuntimeError("Failed to delete directory")
        defer.returnValue(rc)

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return changes[-1].revision

    @defer.inlineCallbacks
    def _syncSubmodule(self, _=None):
        rc = RC_SUCCESS
        if self.submodules:
            rc = yield self._dovccmd(['submodule', 'sync'])
        defer.returnValue(rc)

    @defer.inlineCallbacks
    def _updateSubmodule(self, _=None):
        rc = RC_SUCCESS
        if self.submodules:
            vccmd = ['submodule', 'update', '--init', '--recursive', '--force']
            if self.supportsSubmoduleCheckout:
                vccmd.extend(['--checkout'])
            rc = yield self._dovccmd(vccmd)
        defer.returnValue(rc)

    @defer.inlineCallbacks
    def _cleanSubmodule(self, _=None):
        rc = RC_SUCCESS
        if self.submodules:
            command = ['submodule', 'foreach', '--recursive',
                       'git', 'clean', '-f', '-f', '-d']
            if self.mode == 'full' and self.method == 'fresh':
                command.append('-x')
            rc = yield self._dovccmd(command)
        defer.returnValue(rc)

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'

    @defer.inlineCallbacks
    def checkBranchSupport(self):
        stdout = yield self._dovccmd(['--version'], collectStdout=True)

        gitInstalled = False
        if 'git' in stdout:
            gitInstalled = True
        version = stdout.strip().split(' ')[2]
        if LooseVersion(version) < LooseVersion("1.6.5"):
            self.supportsBranch = False
        if LooseVersion(version) < LooseVersion("1.7.8"):
            self.supportsSubmoduleCheckout = False
        defer.returnValue(gitInstalled)

    @defer.inlineCallbacks
    def applyPatch(self, patch):
        yield self._dovccmd(['update-index', '--refresh'])

        res = yield self._dovccmd(['apply', '--index', '-p', str(patch[0])], initialStdin=patch[1])
        defer.returnValue(res)

    @defer.inlineCallbacks
    def _sourcedirIsUpdatable(self):
        if self.workerVersionIsOlderThan('listdir', '2.16'):
            git_path = self.build.path_module.join(self.workdir, '.git')
            exists = yield self.pathExists(git_path)

            if exists:
                defer.returnValue("update")

            defer.returnValue("clone")

        cmd = buildstep.RemoteCommand('listdir',
                                      {'dir': self.workdir,
                                       'logEnviron': self.logEnviron,
                                       'timeout': self.timeout, })
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if 'files' not in cmd.updates:
            # no files - directory doesn't exist
            defer.returnValue("clone")
        files = cmd.updates['files'][0]
        if '.git' in files:
            defer.returnValue("update")
        elif files:
            defer.returnValue("clobber")
        else:
            defer.returnValue("clone")
