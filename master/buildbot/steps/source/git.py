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

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot import config as bbconfig
from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.steps.source.base import Source
from buildbot.steps.worker import CompositeStepMixin
from buildbot.util.git import RC_SUCCESS
from buildbot.util.git import GitStepMixin

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
    ('abbrev', lambda v: [f'--abbrev={v}']
     if isTrueOrIsExactlyZero(v) else None),
    ('candidates', lambda v: [f'--candidates={v}'] if isTrueOrIsExactlyZero(v) else None),
    # optional string parameter
    ('dirty', lambda v: ['--dirty'] if (v is True or v == '') else None),
    ('dirty', lambda v: [f'--dirty={v}'] if (v and v is not True) else None),
]


class Git(Source, GitStepMixin):

    name = 'git'
    renderables = ["repourl", "reference", "branch",
                   "codebase", "mode", "method", "origin"]

    def __init__(self, repourl=None, branch='HEAD', mode='incremental', method=None,
                 reference=None, submodules=False, remoteSubmodules=False, shallow=False,
                 filters=None, progress=True, retryFetch=False, clobberOnFailure=False,
                 getDescription=False, config=None, origin=None, sshPrivateKey=None,
                 sshHostKey=None, sshKnownHosts=None, **kwargs):

        if not getDescription and not isinstance(getDescription, dict):
            getDescription = False

        self.branch = branch
        self.method = method
        self.repourl = repourl
        self.reference = reference
        self.retryFetch = retryFetch
        self.submodules = submodules
        self.remoteSubmodules = remoteSubmodules
        self.shallow = shallow
        self.filters = filters
        self.clobberOnFailure = clobberOnFailure
        self.mode = mode
        self.prog = progress
        self.getDescription = getDescription
        self.sshPrivateKey = sshPrivateKey
        self.sshHostKey = sshHostKey
        self.sshKnownHosts = sshKnownHosts
        self.config = config
        self.srcdir = 'source'
        self.origin = origin

        super().__init__(**kwargs)

        self.setupGitStep()

        if isinstance(self.mode, str):
            if not self._hasAttrGroupMember('mode', self.mode):
                bbconfig.error(
                    f"Git: mode must be {' or '.join(self._listAttrGroupMembers('mode'))}")
            if isinstance(self.method, str):
                if self.mode == 'full' and \
                        self.method not in ['clean', 'fresh', 'clobber', 'copy', None]:
                    bbconfig.error("Git: invalid method for mode 'full'.")
                if self.shallow and (self.mode != 'full' or self.method != 'clobber'):
                    bbconfig.error(
                        "Git: shallow only possible with mode 'full' and method 'clobber'.")
        if not isinstance(self.getDescription, (bool, dict)):
            bbconfig.error("Git: getDescription must be a boolean or a dict.")

    @defer.inlineCallbacks
    def run_vc(self, branch, revision, patch):
        self.branch = branch or 'HEAD'
        self.revision = revision

        self.method = self._getMethod()
        self.stdio_log = yield self.addLogForRemoteCommands("stdio")

        try:
            gitInstalled = yield self.checkFeatureSupport()

            if not gitInstalled:
                raise WorkerSetupError("git is not installed on worker")

            patched = yield self.sourcedirIsPatched()

            if patched:
                yield self._dovccmd(['clean', '-f', '-f', '-d', '-x'])

            yield self._downloadSshPrivateKeyIfNeeded()
            yield self._getAttrGroupMember('mode', self.mode)()
            if patch:
                yield self.patch(patch)
            yield self.parseGotRevision()
            res = yield self.parseCommitDescription()
            yield self._removeSshPrivateKeyIfNeeded()
            return res
        except Exception:
            yield self._removeSshPrivateKeyIfNeeded()
            raise

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
        clean_command = ['clean', '-f', '-f', '-d']
        rc = yield self._dovccmd(clean_command)
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

        if self.submodules:
            rc = yield self._dovccmd(clean_command)
            if rc != RC_SUCCESS:
                raise buildstep.BuildStepFailed
        return RC_SUCCESS

    @defer.inlineCallbacks
    def clobber(self):
        yield self._doClobber()
        res = yield self._fullClone(shallowClone=self.shallow)
        if res != RC_SUCCESS:
            raise buildstep.BuildStepFailed

    @defer.inlineCallbacks
    def fresh(self):
        clean_command = ['clean', '-f', '-f', '-d', '-x']
        res = yield self._dovccmd(clean_command,
                                  abandonOnFailure=False)
        if res == RC_SUCCESS:
            yield self._fetchOrFallback()
        else:
            yield self._doClobber()
            yield self._fullCloneOrFallback()
        yield self._syncSubmodule()
        yield self._updateSubmodule()
        yield self._cleanSubmodule()
        if self.submodules:
            yield self._dovccmd(clean_command)

    @defer.inlineCallbacks
    def copy(self):
        yield self.runRmdir(self.workdir, abandonOnFailure=False,
                            timeout=self.timeout)

        old_workdir = self.workdir
        self.workdir = self.srcdir

        try:
            yield self.mode_incremental()
            cmd = remotecommand.RemoteCommand('cpdir',
                                              {'fromdir': self.srcdir,
                                               'todir': old_workdir,
                                               'logEnviron': self.logEnviron,
                                               'timeout': self.timeout, })
            cmd.useLog(self.stdio_log, False)
            yield self.runCommand(cmd)
            if cmd.didFail():
                raise buildstep.BuildStepFailed()
            return RC_SUCCESS
        finally:
            self.workdir = old_workdir

    @defer.inlineCallbacks
    def parseGotRevision(self, _=None):
        stdout = yield self._dovccmd(['rev-parse', 'HEAD'], collectStdout=True)
        revision = stdout.strip()
        if len(revision) != GIT_HASH_LENGTH:
            raise buildstep.BuildStepFailed()
        log.msg(f"Got Git revision {revision}")
        self.updateSourceProperty('got_revision', revision)

        return RC_SUCCESS

    @defer.inlineCallbacks
    def parseCommitDescription(self, _=None):
        # dict() should not return here
        if isinstance(self.getDescription, bool) and not self.getDescription:
            return RC_SUCCESS

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

        return RC_SUCCESS

    def _getSshDataWorkDir(self):
        if self.method == 'copy' and self.mode == 'full':
            return self.srcdir
        return self.workdir

    @defer.inlineCallbacks
    def _fetch(self, _, abandonOnFailure=True):
        fetch_required = True

        # If the revision already exists in the repo, we don't need to fetch.
        if self.revision:
            rc = yield self._dovccmd(['cat-file', '-e', self.revision],
                                     abandonOnFailure=False)
            if rc == RC_SUCCESS:
                fetch_required = False

        if fetch_required:
            command = ['fetch', '-f', '-t', self.repourl, self.branch]
            # If the 'progress' option is set, tell git fetch to output
            # progress information to the log. This can solve issues with
            # long fetches killed due to lack of output, but only works
            # with Git 1.7.2 or later.
            if self.prog:
                if self.supportsProgress:
                    command.append('--progress')
                else:
                    log.msg("Git versions < 1.7.2 don't support progress")

            res = yield self._dovccmd(command, abandonOnFailure=abandonOnFailure)
            if res != RC_SUCCESS:
                return res

        if self.revision:
            rev = self.revision
        else:
            rev = 'FETCH_HEAD'
        command = ['checkout', '-f', rev]
        res = yield self._dovccmd(command, abandonOnFailure=abandonOnFailure)

        # Rename the branch if needed.
        if res == RC_SUCCESS and self.branch != 'HEAD':
            # Ignore errors
            yield self._dovccmd(['checkout', '-B', self.branch], abandonOnFailure=False)

        return res

    @defer.inlineCallbacks
    def _fetchOrFallback(self, _=None):
        """
        Handles fallbacks for failure of fetch,
        wrapper for self._fetch
        """

        abandonOnFailure = not self.retryFetch and not self.clobberOnFailure

        res = yield self._fetch(None, abandonOnFailure=abandonOnFailure)
        if res == RC_SUCCESS:
            return res
        elif self.retryFetch:
            yield self._fetch(None)
        elif self.clobberOnFailure:
            yield self.clobber()
        else:
            raise buildstep.BuildStepFailed()
        return None

    @defer.inlineCallbacks
    def _clone(self, shallowClone):
        """Retry if clone failed"""

        command = ['clone']
        switchToBranch = self.branch != 'HEAD'
        if self.supportsBranch and self.branch != 'HEAD':
            if self.branch.startswith('refs/'):
                # we can't choose this branch from 'git clone' directly; we
                # must do so after the clone
                command += ['--no-checkout']
            else:
                switchToBranch = False
                command += ['--branch', self.branch]
        if shallowClone:
            command += ['--depth', str(int(shallowClone))]
        if self.reference:
            command += ['--reference', self.reference]
        if self.origin:
            command += ['--origin', self.origin]
        if self.filters:
            if self.supportsFilters:
                for filter in self.filters:
                    command += ['--filter', filter]
            else:
                log.msg("Git versions < 2.27.0 don't support filters on clone")
        command += [self.repourl, '.']

        if self.prog:
            if self.supportsProgress:
                command.append('--progress')
            else:
                log.msg("Git versions < 1.7.2 don't support progress")
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
                log.msg(f"Checkout failed, trying {repeats} more times after {delay} seconds")
                self.retry = (delay, repeats - 1)

                df = defer.Deferred()
                df.addCallback(lambda _: self._doClobber())
                df.addCallback(lambda _: self._clone(shallowClone))
                reactor.callLater(delay, df.callback, None)
                res = yield df

        return res

    @defer.inlineCallbacks
    def _fullClone(self, shallowClone=False):
        """Perform full clone and checkout to the revision if specified
           In the case of shallow clones if any of the step fail abort whole build step.
        """
        res = yield self._clone(shallowClone)
        if res != RC_SUCCESS:
            return res

        # If revision specified checkout that revision
        if self.revision:
            res = yield self._dovccmd(['checkout', '-f', self.revision], shallowClone)

        # init and update submodules, recursively. If there's not recursion
        # it will not do it.
        if self.submodules:
            cmdArgs = ["submodule", "update", "--init", "--recursive"]
            if self.remoteSubmodules:
                cmdArgs.append("--remote")
            res = yield self._dovccmd(cmdArgs, shallowClone)

        return res

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
        return res

    @defer.inlineCallbacks
    def _doClobber(self):
        """Remove the work directory"""
        rc = yield self.runRmdir(self.workdir, timeout=self.timeout)
        if rc != RC_SUCCESS:
            raise RuntimeError("Failed to delete directory")
        return rc

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return changes[-1].revision

    @defer.inlineCallbacks
    def _syncSubmodule(self, _=None):
        rc = RC_SUCCESS
        if self.submodules:
            rc = yield self._dovccmd(['submodule', 'sync'])
        return rc

    @defer.inlineCallbacks
    def _updateSubmodule(self, _=None):
        rc = RC_SUCCESS
        if self.submodules:
            vccmd = ['submodule', 'update', '--init', '--recursive']
            if self.supportsSubmoduleForce:
                vccmd.extend(['--force'])
            if self.supportsSubmoduleCheckout:
                vccmd.extend(["--checkout"])
            if self.remoteSubmodules:
                vccmd.extend(["--remote"])

            rc = yield self._dovccmd(vccmd)
        return rc

    @defer.inlineCallbacks
    def _cleanSubmodule(self, _=None):
        rc = RC_SUCCESS
        if self.submodules:
            subcommand = 'git clean -f -f -d'
            if self.mode == 'full' and self.method == 'fresh':
                subcommand += ' -x'
            command = ['submodule', 'foreach', '--recursive', subcommand]
            rc = yield self._dovccmd(command)
        return rc

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'
        return None

    @defer.inlineCallbacks
    def applyPatch(self, patch):
        yield self._dovccmd(['update-index', '--refresh'])

        res = yield self._dovccmd(['apply', '--index', '-p', str(patch[0])], initialStdin=patch[1])
        return res

    @defer.inlineCallbacks
    def _sourcedirIsUpdatable(self):
        if self.workerVersionIsOlderThan('listdir', '2.16'):
            git_path = self.build.path_module.join(self.workdir, '.git')
            exists = yield self.pathExists(git_path)

            if exists:
                return "update"

            return "clone"

        cmd = remotecommand.RemoteCommand('listdir',
                                          {'dir': self.workdir})
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if 'files' not in cmd.updates:
            # no files - directory doesn't exist
            return "clone"
        files = cmd.updates['files'][0]
        if '.git' in files:
            return "update"
        elif files:
            return "clobber"
        else:
            return "clone"


class GitPush(buildstep.BuildStep, GitStepMixin, CompositeStepMixin):

    description = None
    descriptionDone = None
    descriptionSuffix = None

    name = 'gitpush'
    renderables = ['repourl', 'branch']

    def __init__(self, workdir=None, repourl=None, branch=None, force=False,
                 env=None, timeout=20 * 60, logEnviron=True,
                 sshPrivateKey=None, sshHostKey=None, sshKnownHosts=None,
                 config=None, **kwargs):

        self.workdir = workdir
        self.repourl = repourl
        self.branch = branch
        self.force = force
        self.env = env
        self.timeout = timeout
        self.logEnviron = logEnviron
        self.sshPrivateKey = sshPrivateKey
        self.sshHostKey = sshHostKey
        self.sshKnownHosts = sshKnownHosts
        self.config = config

        super().__init__(**kwargs)

        self.setupGitStep()

        if not self.branch:
            bbconfig.error('GitPush: must provide branch')

    def _getSshDataWorkDir(self):
        return self.workdir

    @defer.inlineCallbacks
    def run(self):
        self.stdio_log = yield self.addLog("stdio")
        try:
            gitInstalled = yield self.checkFeatureSupport()

            if not gitInstalled:
                raise WorkerSetupError("git is not installed on worker")

            yield self._downloadSshPrivateKeyIfNeeded()
            ret = yield self._doPush()
            yield self._removeSshPrivateKeyIfNeeded()
            return ret

        except Exception as e:
            yield self._removeSshPrivateKeyIfNeeded()
            raise e

    @defer.inlineCallbacks
    def _doPush(self):
        cmd = ['push', self.repourl, self.branch]
        if self.force:
            cmd.append('--force')

        ret = yield self._dovccmd(cmd)
        return ret


class GitTag(buildstep.BuildStep, GitStepMixin, CompositeStepMixin):

    description = None
    descriptionDone = None
    descriptionSuffix = None

    name = 'gittag'
    renderables = ['repourl', 'tagName', 'messages']

    def __init__(self, workdir=None, tagName=None,
                 annotated=False, messages=None, force=False, env=None,
                 timeout=20 * 60, logEnviron=True, config=None, **kwargs):

        self.workdir = workdir
        self.tagName = tagName
        self.annotated = annotated
        self.messages = messages
        self.force = force
        self.env = env
        self.timeout = timeout
        self.logEnviron = logEnviron
        self.config = config

        # These attributes are required for GitStepMixin but not useful to tag
        self.repourl = " "
        self.sshHostKey = None
        self.sshPrivateKey = None
        self.sshKnownHosts = None

        super().__init__(**kwargs)

        self.setupGitStep()

        if not self.tagName:
            bbconfig.error('GitTag: must provide tagName')

        if self.annotated and not self.messages:
            bbconfig.error('GitTag: must provide messages in case of annotated tag')

        if not self.annotated and self.messages:
            bbconfig.error('GitTag: messages are required only in case of annotated tag')

        if self.messages and not isinstance(self.messages, list):
            bbconfig.error('GitTag: messages should be a list')

    @defer.inlineCallbacks
    def run(self):
        self.stdio_log = yield self.addLog("stdio")
        gitInstalled = yield self.checkFeatureSupport()

        if not gitInstalled:
            raise WorkerSetupError("git is not installed on worker")

        ret = yield self._doTag()
        return ret

    @defer.inlineCallbacks
    def _doTag(self):
        cmd = ['tag']

        if self.annotated:
            cmd.append('-a')
            cmd.append(self.tagName)

            for msg in self.messages:
                cmd.extend(['-m', msg])
        else:
            cmd.append(self.tagName)

        if self.force:
            cmd.append('--force')

        ret = yield self._dovccmd(cmd)
        return ret


class GitCommit(buildstep.BuildStep, GitStepMixin, CompositeStepMixin):

    description = None
    descriptionDone = None
    descriptionSuffix = None

    name = 'gitcommit'
    renderables = ['paths', 'messages']

    def __init__(self, workdir=None, paths=None, messages=None, env=None,
                 timeout=20 * 60, logEnviron=True, emptyCommits='disallow',
                 config=None, no_verify=False, **kwargs):

        self.workdir = workdir
        self.messages = messages
        self.paths = paths
        self.env = env
        self.timeout = timeout
        self.logEnviron = logEnviron
        self.config = config
        self.emptyCommits = emptyCommits
        self.no_verify = no_verify
        # The repourl, sshPrivateKey and sshHostKey attributes are required by
        # GitStepMixin, but aren't needed by git add and commit operations
        self.repourl = " "
        self.sshPrivateKey = None
        self.sshHostKey = None
        self.sshKnownHosts = None

        super().__init__(**kwargs)

        self.setupGitStep()

        if not self.messages:
            bbconfig.error('GitCommit: must provide messages')

        if not isinstance(self.messages, list):
            bbconfig.error('GitCommit: messages must be a list')

        if not self.paths:
            bbconfig.error('GitCommit: must provide paths')

        if not isinstance(self.paths, list):
            bbconfig.error('GitCommit: paths must be a list')

        if self.emptyCommits not in ('disallow', 'create-empty-commit', 'ignore'):
            bbconfig.error('GitCommit: emptyCommits must be one of "disallow", '
                           '"create-empty-commit" and "ignore"')

    @defer.inlineCallbacks
    def run(self):
        self.stdio_log = yield self.addLog("stdio")
        gitInstalled = yield self.checkFeatureSupport()

        if not gitInstalled:
            raise WorkerSetupError("git is not installed on worker")

        yield self._checkDetachedHead()
        yield self._doAdd()
        yield self._doCommit()

        return RC_SUCCESS

    @defer.inlineCallbacks
    def _checkDetachedHead(self):
        cmd = ['symbolic-ref', 'HEAD']
        rc = yield self._dovccmd(cmd, abandonOnFailure=False)

        if rc != RC_SUCCESS:
            yield self.stdio_log.addStderr("You are in detached HEAD")
            raise buildstep.BuildStepFailed

    @defer.inlineCallbacks
    def _checkHasSomethingToCommit(self):
        cmd = ['status', '--porcelain=v1']
        stdout = yield self._dovccmd(cmd, collectStdout=True)

        for line in stdout.splitlines(False):
            if line[0] in 'MADRCU':
                return True
        return False

    @defer.inlineCallbacks
    def _doCommit(self):
        if self.emptyCommits == 'ignore':
            has_commit = yield self._checkHasSomethingToCommit()
            if not has_commit:
                return 0

        cmd = ['commit']

        for message in self.messages:
            cmd.extend(['-m', message])

        if self.emptyCommits == 'create-empty-commit':
            cmd.extend(['--allow-empty'])

        if self.no_verify:
            cmd.extend(['--no-verify'])

        ret = yield self._dovccmd(cmd)
        return ret

    @defer.inlineCallbacks
    def _doAdd(self):
        cmd = ['add']

        cmd.extend(self.paths)

        ret = yield self._dovccmd(cmd)
        return ret
