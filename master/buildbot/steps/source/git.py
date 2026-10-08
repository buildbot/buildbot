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

from __future__ import annotations

import hashlib
import ipaddress
import urllib.parse
import weakref
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot import config as bbconfig
from buildbot import interfaces
from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.steps.source.base import Source
from buildbot.steps.worker import CompositeStepMixin
from buildbot.util.git import RC_SUCCESS
from buildbot.util.git import SHARED_CACHE_MINIMUM_GIT_VERSION
from buildbot.util.git import GitStepMixin
from buildbot.util.git_credential import GitCredentialOptions
from buildbot.util.git_credential import add_user_password_to_credentials

if TYPE_CHECKING:
    from buildbot.interfaces import IMaybeRenderableType
    from buildbot.interfaces import IRenderable
    from buildbot.process.buildrequest import TempChange
    from buildbot.util.twisted import InlineCallbacksType


GIT_HASH_LENGTH = 40
COMBINE_FILTER_RESERVED_CHARS = frozenset('~!@#$^&*()[]{}\\;",<>?\'+%')
SHARED_CACHE_DIR = '.git-cache'
SHARED_CACHE_HASH_LENGTH = 16
SHARED_CACHE_ALTERNATES_MARKER = 'buildbot-shared-cache'
SHARED_CACHE_OWNER_CONFIG = 'buildbot.sharedCacheOwner'
SHARED_CACHE_LAST_FSCK_CONFIG = 'buildbot.sharedCacheLastFsck'
SHARED_CACHE_FSCK_FAILED_CONFIG = 'buildbot.sharedCacheFsckFailed'
SHARED_CACHE_FSCK_INTERVAL = 24 * 60 * 60
SHARED_CACHE_METADATA_MAX_SIZE = 256 * 1024
SHARED_CACHE_DEFAULT_PORTS = {'ssh': 22, 'git': 9418, 'http': 80, 'https': 443}
_shared_cache_locks: weakref.WeakKeyDictionary[Any, dict[str, defer.DeferredLock]] = (
    weakref.WeakKeyDictionary()
)


class _SharedCacheMetadataReadError(Exception):
    pass


def isTrueOrIsExactlyZero(v: Any) -> bool:
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
    ('first-parent', lambda v: ['--first-parent'] if v else None),
    # string parameter
    ('match', lambda v: ['--match', v] if v else None),
    ('exclude', lambda v: ['--exclude', v] if v else None),
    # numeric parameter
    ('abbrev', lambda v: [f'--abbrev={v}'] if isTrueOrIsExactlyZero(v) else None),
    ('candidates', lambda v: [f'--candidates={v}'] if isTrueOrIsExactlyZero(v) else None),
    # optional string parameter
    ('dirty', lambda v: ['--dirty'] if (v is True or v == '') else None),
    ('dirty', lambda v: [f'--dirty={v}'] if (v and v is not True) else None),
]


class Git(Source, GitStepMixin):
    name = 'git'
    renderables = [
        "repourl",
        "reference",
        "branch",
        "codebase",
        "mode",
        "method",
        "origin",
        "shared_cache",
    ]

    def __init__(
        self,
        repourl: IMaybeRenderableType[str] | None = None,
        port: int = 22,
        branch: str = 'HEAD',
        mode: str = 'incremental',
        method: str | None = None,
        reference: str | None = None,
        submodules: bool = False,
        remoteSubmodules: bool = False,
        tags: bool = False,
        shallow: bool | int = False,
        filters: list[str] | None = None,
        progress: bool = True,
        retryFetch: bool = False,
        clobberOnFailure: bool = False,
        getDescription: bool | dict[str, Any] = False,
        config: dict[str, Any] | None = None,
        origin: str | None = None,
        sshPrivateKey: Any = None,
        sshHostKey: Any = None,
        sshKnownHosts: Any = None,
        auth_credentials: tuple[IRenderable | str, IRenderable | str] | None = None,
        git_credentials: GitCredentialOptions | None = None,
        shared_cache: IMaybeRenderableType[bool | str] = False,
        **kwargs: Any,
    ) -> None:
        if not getDescription and not isinstance(getDescription, dict):
            getDescription = False

        self.branch = branch
        self.method = method
        self.repourl = repourl  # type: ignore[assignment]
        self.port = port
        self.reference = reference
        self.shared_cache = shared_cache
        self._shared_cache_path: str | None = None
        self._shared_cache_active = False
        self._shared_cache_lock: defer.DeferredLock | None = None
        self.retryFetch = retryFetch
        self.submodules = submodules
        self.remoteSubmodules = remoteSubmodules
        self.tags = tags
        self.shallow = shallow
        self.filters = filters
        self.clobberOnFailure = clobberOnFailure
        self.mode = mode
        self.prog = progress
        self.getDescription = getDescription
        self.config = config
        self.srcdir = 'source'
        self.origin = origin

        super().__init__(**kwargs)

        self.setupGitStep()
        if auth_credentials is not None:
            git_credentials = add_user_password_to_credentials(
                auth_credentials,
                repourl,
                git_credentials,
            )

        self.setup_git_auth(
            sshPrivateKey,
            sshHostKey,
            sshKnownHosts,
            git_credentials,
        )

        if isinstance(self.mode, str):
            if not self._hasAttrGroupMember('mode', self.mode):
                bbconfig.error(
                    f"Git: mode must be {' or '.join(self._listAttrGroupMembers('mode'))}"
                )
            if isinstance(self.method, str):
                if self.mode == 'full' and self.method not in [
                    'clean',
                    'fresh',
                    'clobber',
                    'copy',
                    None,
                ]:
                    bbconfig.error("Git: invalid method for mode 'full'.")
                if self.shallow and (self.mode != 'full' or self.method != 'clobber'):
                    bbconfig.error(
                        "Git: in mode 'full' shallow only possible with method 'clobber'."
                    )
        if not isinstance(self.getDescription, (bool, dict)):
            bbconfig.error("Git: getDescription must be a boolean or a dict.")
        if not (
            isinstance(self.shared_cache, (bool, str))
            or interfaces.IRenderable.providedBy(self.shared_cache)
        ):
            bbconfig.error("Git: shared_cache must be a boolean, string, or renderable.")
        if (
            not interfaces.IRenderable.providedBy(self.shared_cache)
            and self.shared_cache
            and not interfaces.IRenderable.providedBy(self.reference)
            and self.reference
        ):
            bbconfig.error(
                "Git: shared_cache and reference cannot both be set. "
                "shared_cache manages the reference automatically."
            )

    def _validateRenderedSharedCache(self) -> None:
        if not isinstance(self.shared_cache, (bool, str)):
            raise buildstep.BuildStepFailed(
                "Git: rendered shared_cache must be a boolean or string"
            )
        if isinstance(self.shared_cache, str) and any(
            character in self.shared_cache for character in '\0\r\n'
        ):
            raise buildstep.BuildStepFailed(
                "Git: rendered shared_cache path must not contain NUL or newline characters"
            )
        if (
            isinstance(self.shared_cache, str)
            and self.worker is not None
            and self.worker.worker_system == 'nt'
            and self._isPartiallyQualifiedWindowsPath(self.shared_cache)
        ):
            raise buildstep.BuildStepFailed(
                "Git: Windows shared_cache paths must be fully qualified or relative"
            )
        if self.shared_cache and self.reference:
            raise buildstep.BuildStepFailed("Git: shared_cache and reference cannot both be set")
        if self.shared_cache:
            try:
                parsed_repourl = urllib.parse.urlsplit(self.repourl)
            except ValueError:
                parsed_repourl = None
            if (
                parsed_repourl is not None
                and parsed_repourl.scheme.lower() in ('http', 'https')
                and (parsed_repourl.query or parsed_repourl.fragment)
            ):
                raise buildstep.BuildStepFailed(
                    "Git: shared_cache does not support HTTP(S) repository URLs "
                    "with a query or fragment"
                )
        if self.shared_cache and self._isRelativeLocalRepository():
            raise buildstep.BuildStepFailed(
                "Git: shared_cache does not support relative local repository paths"
            )

    def _isRelativeLocalRepository(self) -> bool:
        assert self.build is not None
        path_module = self.build.path_module
        if '://' in self.repourl:
            return False

        if self.worker is not None and self.worker.worker_system == 'nt':
            windows_path = self.build.path_cls(self.repourl)
            if self._isPartiallyQualifiedWindowsPath(self.repourl):
                return True
            if windows_path.is_absolute():
                return False
        elif path_module.isabs(self.repourl):
            return False

        drive, _ = path_module.splitdrive(self.repourl)
        if drive:
            return True

        return ':' not in self.repourl or self.repourl.startswith(('./', '../', '.\\', '..\\'))

    def _isPartiallyQualifiedWindowsPath(self, path: str) -> bool:
        assert self.build is not None and self.build.path_cls is not None
        windows_path = self.build.path_cls(path)
        incomplete_unc = windows_path.drive.startswith('\\\\') and not windows_path.root
        return bool(windows_path.drive or windows_path.root) and (
            not windows_path.is_absolute() or incomplete_unc
        )

    @defer.inlineCallbacks
    def run_vc(
        self, branch: str | None, revision: str | None, patch: Any
    ) -> InlineCallbacksType[int]:
        self.stdio_log = yield self.addLogForRemoteCommands("stdio")

        try:
            self._validateRenderedSharedCache()
        except buildstep.BuildStepFailed as e:
            self._reportSharedCache(str(e))
            raise

        self.setup_repourl()
        self.branch = branch or 'HEAD'
        self.revision = revision

        self.method = self._getMethod()

        auth_workdir = self._get_auth_data_workdir()

        try:
            gitInstalled = yield self.checkFeatureSupport()

            if not gitInstalled:
                raise WorkerSetupError("git is not installed on worker")

            patched = yield self.sourcedirIsPatched()

            if patched:
                yield self._dovccmd(['clean', '-f', '-f', '-d', '-x'])

            yield self._git_auth.download_auth_files_if_needed(auth_workdir)

            yield self._ensureSharedCache()

            yield self._getAttrGroupMember('mode', self.mode)()
            if patch:
                yield self.patch(patch)
            yield self.parseGotRevision()
            res = yield self.parseCommitDescription()
            return res
        finally:
            self._releaseSharedCacheLock()
            yield self._git_auth.remove_auth_files_if_needed(auth_workdir)

    @defer.inlineCallbacks
    def mode_full(self) -> InlineCallbacksType[None]:
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
            yield self._fullCloneOrFallback(self.shallow)
        elif self.method == 'clean':
            yield self.clean()
        elif self.method == 'fresh':
            yield self.fresh()
        else:
            raise ValueError("Unknown method, check your configuration")

    @defer.inlineCallbacks
    def mode_incremental(self) -> InlineCallbacksType[None]:
        action = yield self._sourcedirIsUpdatable()
        # if not updatable, do a full checkout
        if action == "clobber":
            yield self.clobber()
            return
        elif action == "clone":
            log.msg("No git repo present, making full clone")
            yield self._fullCloneOrFallback(shallowClone=self.shallow)
            return

        yield self._fetchOrFallback()

        yield self._syncSubmodule(None)
        yield self._updateSubmodule(None)

    @defer.inlineCallbacks
    def clean(self) -> InlineCallbacksType[int]:
        clean_command = ['clean', '-f', '-f', '-d']
        rc = yield self._dovccmd(
            clean_command,
            abandonOnFailure=not self.clobberOnFailure,
        )
        if rc != RC_SUCCESS:
            if self.clobberOnFailure:
                # clobber's full clone initializes submodules itself
                yield self.clobber()
                return RC_SUCCESS
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
    def clobber(self) -> InlineCallbacksType[None]:
        yield self._doClobber()
        res = yield self._fullCloneCacheAware(shallowClone=self.shallow)
        if res != RC_SUCCESS and self._shared_cache_active:
            self._disableSharedCache()
            yield self._doClobber()
            res = yield self._fullClone(shallowClone=self.shallow)
        if res != RC_SUCCESS:
            raise buildstep.BuildStepFailed

    @defer.inlineCallbacks
    def fresh(self) -> InlineCallbacksType[None]:
        clean_command = ['clean', '-f', '-f', '-d', '-x']
        res = yield self._dovccmd(clean_command, abandonOnFailure=False)
        if res == RC_SUCCESS:
            yield self._fetchOrFallback()
        else:
            yield self._doClobber()
            yield self._fullCloneOrFallback(shallowClone=self.shallow)
        yield self._syncSubmodule()
        yield self._updateSubmodule()
        yield self._cleanSubmodule()
        if self.submodules:
            yield self._dovccmd(clean_command)

    @defer.inlineCallbacks
    def copy(self) -> InlineCallbacksType[int]:
        yield self.runRmdir(self.workdir, abandonOnFailure=False, timeout=self.timeout)

        old_workdir = self.workdir
        self.workdir = self.srcdir

        try:
            yield self.mode_incremental()
            cmd = remotecommand.RemoteCommand(
                'cpdir',
                {
                    'fromdir': self.srcdir,
                    'todir': old_workdir,
                    'logEnviron': self.logEnviron,
                    'timeout': self.timeout,
                },
            )
            cmd.useLog(self.stdio_log, False)
            yield self.runCommand(cmd)
            if cmd.didFail():
                raise buildstep.BuildStepFailed()
            return RC_SUCCESS
        finally:
            self.workdir = old_workdir

    @defer.inlineCallbacks
    def parseGotRevision(self, _: Any = None) -> InlineCallbacksType[int]:
        stdout = yield self._dovccmd(['rev-parse', 'HEAD'], collectStdout=True)
        revision = stdout.strip()
        if len(revision) != GIT_HASH_LENGTH:
            raise buildstep.BuildStepFailed()
        log.msg(f"Got Git revision {revision}")
        self.updateSourceProperty('got_revision', revision)

        return RC_SUCCESS

    @defer.inlineCallbacks
    def parseCommitDescription(self, _: Any = None) -> InlineCallbacksType[int]:
        # dict() should not return here
        if isinstance(self.getDescription, bool) and not self.getDescription:
            return RC_SUCCESS

        cmd = ['describe']
        if isinstance(self.getDescription, dict):
            for flag_name, flag_func in git_describe_flags:
                flag_val = self.getDescription.get(flag_name, None)
                flag_args = flag_func(flag_val)
                if flag_args:
                    cmd.extend(flag_args)
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

    def _get_auth_data_workdir(self) -> str:
        if self.method == 'copy' and self.mode == 'full':
            return self.srcdir
        return self.workdir

    def _computeCachePath(self) -> str:
        assert self.worker is not None
        worker_basedir = self.worker.worker_basedir
        if self.worker.worker_system == 'nt':
            basedir_is_absolute = self.build.path_cls(
                worker_basedir
            ).is_absolute() and not self._isPartiallyQualifiedWindowsPath(worker_basedir)
        else:
            basedir_is_absolute = self.build.path_module.isabs(worker_basedir)
        if not worker_basedir or not basedir_is_absolute:
            raise ValueError("shared_cache requires an absolute worker basedir")

        if isinstance(self.shared_cache, str):
            cache_path = self.shared_cache
            if self.worker.worker_system == 'nt':
                if self._isPartiallyQualifiedWindowsPath(cache_path):
                    raise ValueError(
                        "Windows shared_cache paths must be fully qualified or relative"
                    )
                cache_path_is_absolute = self.build.path_cls(cache_path).is_absolute()
            else:
                cache_path_is_absolute = self.build.path_module.isabs(cache_path)
            if not cache_path_is_absolute:
                cache_path = self.build.path_module.join(worker_basedir, cache_path)
            return self.build.path_module.normpath(cache_path)

        repo_hash = hashlib.sha256(self._getSharedCacheIdentity().encode('utf-8')).hexdigest()[
            :SHARED_CACHE_HASH_LENGTH
        ]
        return self.build.path_module.join(worker_basedir, SHARED_CACHE_DIR, f'{repo_hash}.git')

    def _getSharedCacheIdentity(self, url: str | None = None) -> str:
        if url is None:
            url = self.repourl
        try:
            parsed = urllib.parse.urlsplit(url)
        except ValueError:
            return url
        if not parsed.scheme or parsed.hostname is None:
            return url
        if '[' in parsed.netloc:
            try:
                ipaddress.IPv6Address(parsed.hostname)
            except ValueError:
                return url

        scheme = parsed.scheme.lower()
        try:
            port = parsed.port
        except ValueError:
            netloc = parsed.netloc.rsplit('@', 1)[-1]
        else:
            hostname = parsed.hostname
            if ':' in hostname:
                hostname = f'[{hostname}]'
            netloc = hostname
            if port is not None and port != SHARED_CACHE_DEFAULT_PORTS.get(scheme):
                netloc += f':{port}'
        if scheme not in ('http', 'https') and parsed.username:
            netloc = f'{urllib.parse.quote(parsed.username, safe="")}@{netloc}'
        return urllib.parse.urlunsplit((
            scheme,
            netloc,
            parsed.path,
            parsed.query,
            parsed.fragment,
        ))

    def _getSharedCacheLock(self, cache_path: str) -> defer.DeferredLock:
        assert self.worker is not None
        worker_locks = _shared_cache_locks.setdefault(self.worker, {})
        lock_path = self.build.path_module.normcase(cache_path)
        return worker_locks.setdefault(lock_path, defer.DeferredLock())

    def _acquireSharedCacheLock(
        self, lock: defer.DeferredLock
    ) -> defer.Deferred[defer.DeferredLock]:
        assert self.master is not None
        d = lock.acquire()
        if self.timeout is not None:
            d.addTimeout(self.timeout, self.master.reactor)
        return d

    def _dovccmd(
        self,
        command: list[str],
        abandonOnFailure: str | bool = True,
        collectStdout: bool = False,
        initialStdin: str | None = None,
        workdir: str | None = None,
        config_overrides: dict[str, Any] | None = None,
        sanitize_repository_environment: bool = False,
        use_step_config: bool = True,
        auth_command: str | None = None,
    ) -> defer.Deferred[str | int | None]:
        if self.shared_cache and self.worker is not None and self.worker.worker_system == 'nt':
            config_overrides = dict(config_overrides or {})
            step_config = self.config if use_step_config else None
            if not step_config or 'core.longpaths' not in step_config:
                config_overrides['core.longpaths'] = 'true'
            source_safe_directory = self._getWindowsSourceSafeDirectory()
            if source_safe_directory is not None:
                config_overrides.setdefault('safe.directory', source_safe_directory)

        return super()._dovccmd(
            command,
            abandonOnFailure=abandonOnFailure,
            collectStdout=collectStdout,
            initialStdin=initialStdin,
            workdir=workdir,
            config_overrides=config_overrides,
            sanitize_repository_environment=sanitize_repository_environment,
            use_step_config=use_step_config,
            auth_command=auth_command,
        )

    def _getWindowsSafeDirectory(self, path: str) -> str:
        normalized_path = path.replace('\\', '/')
        if normalized_path.startswith('//') and not normalized_path.startswith('//?/'):
            return f'%(prefix)/{normalized_path}'
        return path

    def _getWindowsSourceSafeDirectory(self) -> list[str] | None:
        if (
            self.worker is None
            or self.worker.worker_system != 'nt'
            or not self.build.path_cls(self.repourl).is_absolute()
        ):
            return None
        # Git checks the git directory, which is <path>/.git when non-bare
        return [
            self._getWindowsSafeDirectory(self.repourl),
            self._getWindowsSafeDirectory(self.build.path_module.join(self.repourl, '.git')),
        ]

    def _getSharedCacheGitConfig(self, cache_path: str) -> dict[str, str]:
        assert self.build is not None
        config = {
            'core.hooksPath': self.build.path_module.join(cache_path, 'buildbot-hooks'),
            'fetch.writeCommitGraph': 'false',
            'gc.auto': '0',
            'maintenance.auto': 'false',
            'protocol.ext.allow': 'never',
        }
        if self.worker is not None and self.worker.worker_system == 'nt':
            config['core.longpaths'] = 'true'
            config['safe.directory'] = self._getWindowsSafeDirectory(cache_path)
        return config

    def _dovccache(
        self,
        cache_path: str,
        command: list[str],
        *,
        abandonOnFailure: bool = True,
        collectStdout: bool = False,
        initialStdin: str | None = None,
        use_cache_repository: bool = True,
    ) -> defer.Deferred[Any]:
        assert self.worker is not None
        cache_command = command
        workdir = cache_path
        auth_kwargs: dict[str, str] = {}
        if self.worker.worker_system == 'nt':
            workdir = self.worker.worker_basedir
            if use_cache_repository:
                subcommand = next((arg for arg in command if not arg.startswith('-')), None)
                if subcommand is not None:
                    auth_kwargs['auth_command'] = subcommand
                cache_command = ['-C', cache_path, *command]
                source_safe_directory = self._getWindowsSourceSafeDirectory()
                cache_safe_directory = self._getWindowsSafeDirectory(cache_path)
                if source_safe_directory is not None:
                    trust_arguments: list[str] = []
                    for entry in source_safe_directory:
                        if entry != cache_safe_directory:
                            trust_arguments += ['-c', f'safe.directory={entry}']
                    cache_command = [*trust_arguments, *cache_command]
        elif not use_cache_repository:
            workdir = self.worker.worker_basedir

        return self._dovccmd(
            cache_command,
            abandonOnFailure=abandonOnFailure,
            collectStdout=collectStdout,
            initialStdin=initialStdin,
            workdir=workdir,
            config_overrides=self._getSharedCacheGitConfig(cache_path),
            sanitize_repository_environment=True,
            use_step_config=False,
            **auth_kwargs,
        )

    @defer.inlineCallbacks
    def _isBareRepository(self, cache_path: str) -> InlineCallbacksType[bool]:
        stdout = yield self._dovccache(
            cache_path,
            [f'--git-dir={cache_path}', 'rev-parse', '--is-bare-repository'],
            abandonOnFailure=False,
            collectStdout=True,
        )
        return isinstance(stdout, str) and stdout.strip() == 'true'

    @defer.inlineCallbacks
    def _isPartialCloneRepository(self, cache_path: str) -> InlineCallbacksType[bool]:
        partial_config = yield self._dovccache(
            cache_path,
            [
                'config',
                '--local',
                '--get-regexp',
                r'^(extensions\.partialclone|remote\..*\.(promisor|partialclonefilter))$',
            ],
            abandonOnFailure=False,
            collectStdout=True,
        )
        for line in partial_config.splitlines():
            key, separator, value = line.partition(' ')
            key = key.lower()
            if key.endswith('.partialclonefilter') or key == 'extensions.partialclone':
                return True
            if key.endswith('.promisor'):
                if not separator:
                    return True
                if value.strip().lower() not in ('0', 'off', 'false', 'no', ''):
                    return True
        return False

    @defer.inlineCallbacks
    def _findSharedCacheAlternate(self, cache_path: str) -> InlineCallbacksType[str | None]:
        assert self.build is not None
        info_path = self.build.path_module.join(cache_path, 'objects', 'info')
        for filename in ('alternates', 'http-alternates'):
            alternate_path = self.build.path_module.join(info_path, filename)
            if (yield self.pathExists(alternate_path)):
                return alternate_path
        return None

    @defer.inlineCallbacks
    def _getSharedCacheRecordedIdentity(self, cache_path: str) -> InlineCallbacksType[str]:
        identity = yield self._dovccache(
            cache_path,
            ['config', '--local', '--get', 'buildbot.sharedCacheIdentity'],
            abandonOnFailure=False,
            collectStdout=True,
        )
        if not isinstance(identity, str):
            return ''
        return identity.rstrip('\r\n')

    @defer.inlineCallbacks
    def _getSharedCacheOwner(self, cache_path: str) -> InlineCallbacksType[str]:
        owner = yield self._dovccache(
            cache_path,
            ['config', '--local', '--get', SHARED_CACHE_OWNER_CONFIG],
            abandonOnFailure=False,
            collectStdout=True,
        )
        return owner.rstrip('\r\n')

    @defer.inlineCallbacks
    def _markSharedCacheOwned(self, cache_path: str) -> InlineCallbacksType[bool]:
        rc = yield self._dovccache(
            cache_path,
            [
                'config',
                '--local',
                SHARED_CACHE_OWNER_CONFIG,
                self._getSharedCacheIdentity(),
            ],
            abandonOnFailure=False,
        )
        return rc == RC_SUCCESS

    @defer.inlineCallbacks
    def _initializeSharedCache(self, cache_path: str) -> InlineCallbacksType[bool]:
        assert self.worker is not None
        parent_path = self.build.path_module.dirname(cache_path)
        rc = yield self.runMkdir(parent_path, abandonOnFailure=False)
        if rc != RC_SUCCESS:
            return False

        rc = yield self._dovccache(
            cache_path,
            ['init', '--bare', cache_path],
            use_cache_repository=False,
            abandonOnFailure=False,
        )
        if rc != RC_SUCCESS:
            yield self._removeSharedCache(cache_path)
        return rc == RC_SUCCESS

    @defer.inlineCallbacks
    def _removeSharedCache(self, cache_path: str) -> InlineCallbacksType[bool]:
        rc = yield self.runRmdir(cache_path, abandonOnFailure=False, timeout=self.timeout)
        return rc == RC_SUCCESS

    @defer.inlineCallbacks
    def _prepareSharedCacheRepository(
        self, cache_path: str, managed_cache: bool
    ) -> InlineCallbacksType[bool]:
        assert self.build is not None
        cache_exists = yield self.pathExists(cache_path)
        created_cache = False
        if cache_exists and not (yield self._isBareRepository(cache_path)):
            self._reportSharedCache(f"Git shared cache at {cache_path!r} is not a bare repository")
            return False

        if not cache_exists:
            if not (yield self._initializeSharedCache(cache_path)):
                return False
            created_cache = True

        alternate_path = yield self._findSharedCacheAlternate(cache_path)
        if alternate_path is not None:
            self._reportSharedCache(
                f"Git shared cache at {cache_path!r} uses alternate object database "
                f"file {alternate_path!r}"
            )
            if created_cache:
                yield self._removeSharedCache(cache_path)
            return False

        identity = self._getSharedCacheIdentity()
        if cache_exists and not managed_cache:
            owner = yield self._getSharedCacheOwner(cache_path)
            if owner != identity:
                self._reportSharedCache(
                    f"Git shared cache at {cache_path!r} is not marked as a "
                    "Buildbot-owned cache for this repository"
                )
                return False

        if cache_exists and managed_cache and not created_cache:
            recorded = yield self._getSharedCacheRecordedIdentity(cache_path)
            if recorded and recorded != identity:
                self._reportSharedCache(
                    f"Git shared cache at {cache_path!r} records a different repository"
                )
                return False

        if (yield self._isPartialCloneRepository(cache_path)):
            self._reportSharedCache(f"Git shared cache at {cache_path!r} is a partial clone")
            if created_cache:
                yield self._removeSharedCache(cache_path)
            return False

        if created_cache and not managed_cache:
            if not (yield self._markSharedCacheOwned(cache_path)):
                yield self._removeSharedCache(cache_path)
                return False

        remote_url = yield self._dovccache(
            cache_path,
            ['config', '--local', '--get', 'remote.origin.url'],
            abandonOnFailure=False,
            collectStdout=True,
        )
        remote_url = remote_url.rstrip('\r\n') if isinstance(remote_url, str) else ''
        if remote_url:
            if not managed_cache and self._getSharedCacheIdentity(remote_url) != identity:
                self._reportSharedCache(
                    f"Git shared cache at {cache_path!r} belongs to a different repository"
                )
                if created_cache:
                    yield self._removeSharedCache(cache_path)
                return False
            rc = yield self._dovccache(
                cache_path,
                ['remote', 'set-url', 'origin', identity],
                abandonOnFailure=False,
            )
        else:
            rc = yield self._dovccache(
                cache_path,
                ['remote', 'add', 'origin', identity],
                abandonOnFailure=False,
            )
            if rc != RC_SUCCESS:
                rc = yield self._dovccache(
                    cache_path,
                    ['remote', 'set-url', 'origin', identity],
                    abandonOnFailure=False,
                )
        if rc != RC_SUCCESS:
            if created_cache:
                yield self._removeSharedCache(cache_path)
            return False

        hooks_path = self.build.path_module.join(cache_path, 'buildbot-hooks')
        rc = yield self.runRmdir(hooks_path, abandonOnFailure=False, timeout=self.timeout)
        if rc != RC_SUCCESS:
            self._reportSharedCache(
                f"Failed to clear Git shared cache hooks directory at {hooks_path!r}"
            )
            if created_cache:
                yield self._removeSharedCache(cache_path)
            return False
        rc = yield self.runMkdir(hooks_path, abandonOnFailure=False)
        if rc != RC_SUCCESS:
            if created_cache:
                yield self._removeSharedCache(cache_path)
            return False

        for name, value in [
            ('gc.auto', '0'),
            ('maintenance.auto', 'false'),
            ('fetch.writeCommitGraph', 'false'),
            ('core.hooksPath', hooks_path),
        ]:
            rc = yield self._dovccache(
                cache_path,
                ['config', '--local', name, value],
                abandonOnFailure=False,
            )
            if rc != RC_SUCCESS:
                if created_cache:
                    yield self._removeSharedCache(cache_path)
                return False
        return True

    @defer.inlineCallbacks
    def _isSharedCacheHealthy(self, cache_path: str) -> InlineCallbacksType[bool]:
        assert self.master is not None
        identity = yield self._getSharedCacheRecordedIdentity(cache_path)
        if identity != self._getSharedCacheIdentity():
            return False

        now = int(self.master.reactor.seconds())
        last_fsck = yield self._getSharedCacheTimestamp(cache_path, SHARED_CACHE_LAST_FSCK_CONFIG)
        if last_fsck is not None and 0 <= now - last_fsck < SHARED_CACHE_FSCK_INTERVAL:
            return True

        last_failure = yield self._getSharedCacheTimestamp(
            cache_path, SHARED_CACHE_FSCK_FAILED_CONFIG
        )
        if last_failure is not None and 0 <= now - last_failure < SHARED_CACHE_FSCK_INTERVAL:
            self._reportSharedCache(
                f"Git shared cache at {cache_path!r} failed its last integrity check; "
                "not re-checking it yet"
            )
            return False

        rc = yield self._dovccache(cache_path, ['fsck', '--no-dangling'], abandonOnFailure=False)
        if rc != RC_SUCCESS:
            yield self._recordSharedCacheFsckTime(cache_path, SHARED_CACHE_FSCK_FAILED_CONFIG)
            return False

        yield self._recordSharedCacheFsckTime(cache_path, SHARED_CACHE_LAST_FSCK_CONFIG)
        yield self._dovccache(
            cache_path,
            ['config', '--local', '--unset', SHARED_CACHE_FSCK_FAILED_CONFIG],
            abandonOnFailure=False,
        )
        return True

    @defer.inlineCallbacks
    def _getSharedCacheTimestamp(
        self, cache_path: str, key: str
    ) -> InlineCallbacksType[int | None]:
        output = yield self._dovccache(
            cache_path,
            ['config', '--local', '--get', key],
            abandonOnFailure=False,
            collectStdout=True,
        )
        if not isinstance(output, str):
            return None
        try:
            return int(output.strip())
        except ValueError:
            return None

    @defer.inlineCallbacks
    def _recordSharedCacheFsckTime(self, cache_path: str, key: str) -> InlineCallbacksType[None]:
        assert self.master is not None
        rc = yield self._dovccache(
            cache_path,
            ['config', '--local', key, str(int(self.master.reactor.seconds()))],
            abandonOnFailure=False,
        )
        if rc != RC_SUCCESS:
            log.msg(f"Failed to record the Git shared cache check time at {cache_path!r}")

    @defer.inlineCallbacks
    def _markSharedCachePopulated(self, cache_path: str) -> InlineCallbacksType[bool]:
        rc = yield self._dovccache(
            cache_path,
            ['config', '--local', 'buildbot.sharedCacheIdentity', self._getSharedCacheIdentity()],
            abandonOnFailure=False,
        )
        return rc == RC_SUCCESS

    @defer.inlineCallbacks
    def _updateSharedCache(self, cache_path: str) -> InlineCallbacksType[bool]:
        if getattr(self, 'revision', None) and not self.tags:
            rc = yield self._dovccache(
                cache_path,
                ['cat-file', '-e', f'{self.revision}^0'],
                abandonOnFailure=False,
            )
            if rc == RC_SUCCESS:
                return (yield self._markSharedCachePopulated(cache_path))

        fetch_cmd = [
            'fetch',
            '--prune',
            '--no-tags',
        ]
        if self.prog and self.supportsProgress:
            fetch_cmd.append('--progress')
        fetch_cmd += [
            # not origin, which is deliberately credential-free
            self.repourl,
            '+refs/heads/*:refs/heads/*',
            # With no destination, Git records this ref only in FETCH_HEAD.
            self.branch,  # type: ignore[list-item]
        ]
        if self.tags:
            fetch_cmd.append('+refs/tags/*:refs/tags/*')

        rc = yield self._dovccache(
            cache_path,
            fetch_cmd,
            abandonOnFailure=False,
        )
        if rc != RC_SUCCESS:
            self._reportSharedCache(f"Failed to update Git shared cache at {cache_path!r}")
            return False
        return (yield self._markSharedCachePopulated(cache_path))

    def _isCacheInDeletedBasedir(self, cache_path: str) -> bool:
        assert self.build is not None
        if not getattr(self.worker, 'worker_deletes_leftover_dirs', False):
            return False
        basedir = getattr(self.worker, 'worker_basedir', None)
        if not basedir:
            return False
        path_module = self.build.path_module
        normalized_base = path_module.normcase(path_module.normpath(basedir))
        normalized_cache = path_module.normcase(path_module.normpath(cache_path))
        normalized_base = normalized_base.rstrip(path_module.sep) + path_module.sep
        return normalized_cache.startswith(normalized_base)

    @defer.inlineCallbacks
    def _ensureSharedCache(self) -> InlineCallbacksType[None]:
        self._shared_cache_path = None
        self._shared_cache_active = False
        if not self.shared_cache:
            return
        if not self.supportsSharedCache:
            self._reportSharedCache(
                f"shared_cache requires Git {SHARED_CACHE_MINIMUM_GIT_VERSION} or later"
            )
            return

        try:
            cache_path = self._computeCachePath()
        except ValueError as e:
            self._reportSharedCache(str(e))
            return

        if self._isCacheInDeletedBasedir(cache_path):
            self._reportSharedCache(
                f"The worker deletes leftover directories, which would remove the Git shared "
                f"cache at {cache_path!r} on every reconnect; configure shared_cache with an "
                "absolute path outside the worker base directory to use it"
            )
            return

        managed_cache = not isinstance(self.shared_cache, str)
        lock = self._getSharedCacheLock(cache_path)
        try:
            yield self._acquireSharedCacheLock(lock)
        except defer.TimeoutError:
            self._reportSharedCache(
                f"Timed out waiting for the Git shared cache lock for {cache_path!r}; "
                "continuing without the cache"
            )
            return
        self._shared_cache_lock = lock
        try:
            cache_ready = yield self._prepareSharedCacheRepository(cache_path, managed_cache)
            if not cache_ready:
                self._reportSharedCache(
                    f"Continuing without the Git shared cache at {cache_path!r}"
                )
                self._disableSharedCache()
                return
            cache_updated = yield self._updateSharedCache(cache_path)
            if not cache_updated:
                self._reportSharedCache(
                    f"Retaining Git shared cache at {cache_path!r} after an update failure"
                )
                self._disableSharedCache()
                return
            if not (yield self._isSharedCacheHealthy(cache_path)):
                self._reportSharedCache(f"Preserving unusable Git shared cache at {cache_path!r}")
                self._disableSharedCache()
                return
            self._shared_cache_path = cache_path
            self._shared_cache_active = True
            log.msg(f"Using Git shared cache at {cache_path!r}")
        finally:
            self._releaseSharedCacheLock()

    def _reportSharedCache(self, message: str) -> None:
        if self.build is not None:
            message = self.build.properties.cleanupTextFromSecrets(message)
        log.msg(message)
        stdio_log = getattr(self, 'stdio_log', None)
        if stdio_log is not None:
            stdio_log.addHeader(message + '\n')

    def _disableSharedCache(self) -> None:
        self._shared_cache_path = None
        self._shared_cache_active = False
        self._releaseSharedCacheLock()

    def _releaseSharedCacheLock(self) -> None:
        lock = self._shared_cache_lock
        if lock is not None:
            self._shared_cache_lock = None
            lock.release()

    @defer.inlineCallbacks
    def _getAlternatesPaths(self) -> InlineCallbacksType[tuple[str, str] | None]:
        assert self.build is not None
        info_dir = yield self._dovccmd(
            ['rev-parse', '--git-path', 'objects/info'],
            abandonOnFailure=False,
            collectStdout=True,
        )
        if not isinstance(info_dir, str):
            return None
        info_dir = info_dir.rstrip('\r\n')
        if not info_dir or '\0' in info_dir or '\r' in info_dir or '\n' in info_dir:
            log.msg("Could not determine the Git object info directory")
            return None
        return (
            self.build.path_module.join(info_dir, 'alternates'),
            self.build.path_module.join(info_dir, SHARED_CACHE_ALTERNATES_MARKER),
        )

    def _getWorkerFilePath(self, path: str) -> str:
        assert self.build is not None
        if self.build.path_module.isabs(path):
            return path
        return self.build.path_module.join(self.workdir, path)

    @defer.inlineCallbacks
    def _writeWorkerFileAtomically(self, path: str, content: str) -> InlineCallbacksType[bool]:
        assert self.worker is not None
        temporary_path = path + '.buildbot-tmp'
        result = yield self.downloadFileContentToWorker(
            temporary_path,
            content,
            workdir=self.workdir,
            abandonOnFailure=False,
        )
        if result is None:
            return False

        if self.worker.worker_system == 'nt':
            command = ['cmd.exe', '/c', 'move', '/Y', temporary_path, path]
        else:
            command = ['mv', '-f', temporary_path, path]
        cmd = remotecommand.RemoteShellCommand(
            self.workdir,
            command,
            env=self.env,
            logEnviron=self.logEnviron,
            timeout=self.timeout,
        )
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        if cmd.didFail():
            yield self.runRmFile(
                self._getWorkerFilePath(temporary_path),
                abandonOnFailure=False,
            )
            return False
        return True

    @defer.inlineCallbacks
    def _readWorkerFile(self, path: str) -> InlineCallbacksType[str | None]:
        try:
            content = yield self.getFileContentFromWorker(
                path,
                abandonOnFailure=False,
                maxsize=SHARED_CACHE_METADATA_MAX_SIZE,
            )
        except UnicodeDecodeError:
            raise _SharedCacheMetadataReadError(
                f"Git shared-cache metadata file {path!r} is not valid UTF-8"
            ) from None

        if content is None:
            if (yield self.pathExists(self._getWorkerFilePath(path))):
                raise _SharedCacheMetadataReadError(
                    f"Git shared-cache metadata file {path!r} could not be read safely"
                )
            return None
        return content

    @defer.inlineCallbacks
    def _ensureAlternates(self) -> InlineCallbacksType[None]:
        assert self.build is not None
        if not self.shared_cache:
            return
        if not self._shared_cache_active or not self._shared_cache_path:
            # Existing checkouts may still depend on their configured alternate.
            return

        alternates_paths = yield self._getAlternatesPaths()
        if alternates_paths is None:
            return
        alternates_path, marker_path = alternates_paths
        try:
            marker_content = yield self._readWorkerFile(marker_path)
            alternates_content = yield self._readWorkerFile(alternates_path)
        except _SharedCacheMetadataReadError as e:
            log.msg(str(e))
            return

        lines = alternates_content.splitlines() if alternates_content is not None else []
        old_managed_path = marker_content.strip() if marker_content else None

        new_managed_path = self.build.path_module.join(self._shared_cache_path, 'objects')
        new_managed_path = new_managed_path.replace('\\', '/')
        if old_managed_path and old_managed_path != new_managed_path:
            log.msg(
                "Not replacing the existing Git shared-cache alternate "
                f"{old_managed_path!r} with {new_managed_path!r}; "
                "clobber or recreate the checkout to migrate it"
            )
            return

        if new_managed_path not in lines:
            lines.append(new_managed_path)

        desired_alternates = '\n'.join(lines) + '\n'
        alternates_changed = alternates_content != desired_alternates
        if alternates_changed and not (
            yield self._writeWorkerFileAtomically(alternates_path, desired_alternates)
        ):
            return

        desired_marker = new_managed_path + '\n'
        if marker_content != desired_marker and not (
            yield self._writeWorkerFileAtomically(marker_path, desired_marker)
        ):
            if alternates_changed:
                if alternates_content is None:
                    yield self.runRmFile(
                        self._getWorkerFilePath(alternates_path),
                        abandonOnFailure=False,
                    )
                else:
                    yield self._writeWorkerFileAtomically(alternates_path, alternates_content)

    def _getPartialCloneRemote(self) -> str:
        return self.origin or 'origin'

    def _getPartialCloneFilter(self) -> str:
        assert self.filters is not None

        if len(self.filters) == 1:
            return self.filters[0]

        return (
            f"combine:{'+'.join(self._encodeFilterForCombine(filter) for filter in self.filters)}"
        )

    def _encodeFilterForCombine(self, filter: str) -> str:
        return ''.join(
            f'%{ord(char):02X}'
            if ord(char) <= 0x20 or char in COMBINE_FILTER_RESERVED_CHARS
            else char
            for char in filter
        )

    @defer.inlineCallbacks
    def _ensurePartialCloneConfig(self) -> InlineCallbacksType[None]:
        if not self.filters or not self.supportsFilters:
            return

        remote = self._getPartialCloneRemote()
        promisor_key = f'remote.{remote}.promisor'
        filter_key = f'remote.{remote}.partialclonefilter'
        expected_filter = self._getPartialCloneFilter()

        promisor = yield self._dovccmd(
            ['config', '--get', promisor_key],
            abandonOnFailure=False,
            collectStdout=True,
        )
        actual_filter = yield self._dovccmd(
            ['config', '--get', filter_key],
            abandonOnFailure=False,
            collectStdout=True,
        )

        if promisor.strip() == 'true' and actual_filter.strip() == expected_filter:
            return

        rc = yield self._dovccmd(
            ['config', promisor_key, 'true'],
            abandonOnFailure=False,
        )
        if rc != RC_SUCCESS:
            raise buildstep.BuildStepFailed("Failed to configure Git partial-clone promisor")

        rc = yield self._dovccmd(
            ['config', filter_key, expected_filter],
            abandonOnFailure=False,
        )
        if rc != RC_SUCCESS:
            raise buildstep.BuildStepFailed("Failed to configure Git partial-clone filter")

    @defer.inlineCallbacks
    def _fetch(
        self, _: Any, shallowClone: bool | int, abandonOnFailure: bool = True
    ) -> InlineCallbacksType[int | None]:
        yield self._ensurePartialCloneConfig()
        yield self._ensureAlternates()

        fetch_required = True

        # If the revision already exists in the repo, we don't need to fetch. However, if tags
        # were requested, then fetch still needs to be performed for the tags.
        if not self.tags and self.revision:
            rc = yield self._dovccmd(['cat-file', '-e', self.revision], abandonOnFailure=False)
            if rc == RC_SUCCESS:
                fetch_required = False

        if fetch_required:
            command = ['fetch', '-f']
            if shallowClone:
                command += ['--depth', str(int(shallowClone))]
            if self.filters and self.supportsFilters:
                for filter in self.filters:
                    command += ['--filter', filter]
            if self.tags:
                command.append("--tags")

            # If the 'progress' option is set, tell git fetch to output
            # progress information to the log. This can solve issues with
            # long fetches killed due to lack of output, but only works
            # with Git 1.7.2 or later.
            if self.prog:
                if self.supportsProgress:
                    command.append('--progress')
                else:
                    log.msg("Git versions < 1.7.2 don't support progress")

            command += [self.repourl, self.branch]  # type: ignore[list-item]
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
            yield self._dovccmd(['checkout', '-B', self.branch], abandonOnFailure=False)  # type: ignore[list-item]

        return res

    @defer.inlineCallbacks
    def _fetchOrFallback(self, _: Any = None) -> InlineCallbacksType[int | None]:
        """
        Handles fallbacks for failure of fetch,
        wrapper for self._fetch
        """

        abandonOnFailure = not self.retryFetch and not self.clobberOnFailure

        res = yield self._fetch(None, shallowClone=self.shallow, abandonOnFailure=abandonOnFailure)
        if res == RC_SUCCESS:
            return res
        if self.retryFetch:
            res = yield self._fetch(
                None,
                shallowClone=self.shallow,
                abandonOnFailure=not self.clobberOnFailure,
            )
            if res == RC_SUCCESS:
                return res
        if self.clobberOnFailure:
            yield self.clobber()
            return RC_SUCCESS
        raise buildstep.BuildStepFailed()

    @defer.inlineCallbacks
    def _clone(self, shallowClone: bool | int) -> InlineCallbacksType[int | None]:
        """Retry if clone failed"""

        command = ['clone']
        switchToBranch = self.branch != 'HEAD'
        if self.supportsBranch and self.branch != 'HEAD':
            if self.branch.startswith('refs/'):  # type: ignore[union-attr]
                # we can't choose this branch from 'git clone' directly; we
                # must do so after the clone
                command += ['--no-checkout']
            else:
                switchToBranch = False
                command += ['--branch', self.branch]  # type: ignore[list-item]
        if shallowClone:
            command += ['--depth', str(int(shallowClone))]
        reference = self._shared_cache_path if self._shared_cache_active else self.reference
        if reference:
            command += ['--reference', reference]
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
            abandonOnFailure = self.retry[1] <= 0
        else:
            abandonOnFailure = True
        # If it's a shallow clone abort build step
        res = yield self._dovccmd(
            command,
            abandonOnFailure=bool(
                abandonOnFailure and shallowClone and not self._shared_cache_active
            ),
        )

        if switchToBranch:
            res = yield self._fetch(None, shallowClone=shallowClone)

        if res != RC_SUCCESS and self._shared_cache_active:
            return res

        done = self.stopped or res == RC_SUCCESS  # or shallow clone??
        if self.retry and not done:
            delay, repeats = self.retry
            if repeats > 0:
                log.msg(f"Checkout failed, trying {repeats} more times after {delay} seconds")
                self.retry = (delay, repeats - 1)

                df: defer.Deferred[Any] = defer.Deferred()
                df.addCallback(lambda _: self._doClobber())
                df.addCallback(lambda _: self._clone(shallowClone))
                reactor.callLater(delay, df.callback, None)  # type: ignore[attr-defined]
                res = yield df

        return res

    @defer.inlineCallbacks
    def _fullClone(self, shallowClone: bool | int = False) -> InlineCallbacksType[int | None]:
        """Perform full clone and checkout to the revision if specified
        In the case of shallow clones if any of the step fail abort whole build step.
        """
        res = yield self._clone(shallowClone)
        if res != RC_SUCCESS:
            return res

        yield self._ensureAlternates()

        # If revision specified checkout that revision
        if self.revision:
            res = yield self._dovccmd(['checkout', '-f', self.revision], shallowClone)  # type: ignore[arg-type]

        # init and update submodules, recursively. If there's not recursion
        # it will not do it.
        if self.submodules:
            cmdArgs = ["submodule", "update", "--init", "--recursive"]
            if self.remoteSubmodules:
                cmdArgs.append("--remote")
            if shallowClone:
                cmdArgs.extend(["--depth", str(int(shallowClone))])
            res = yield self._dovccmd(cmdArgs, shallowClone)  # type: ignore[arg-type]

        return res

    @defer.inlineCallbacks
    def _fullCloneCacheAware(self, shallowClone: bool | int) -> InlineCallbacksType[int | None]:
        try:
            res = yield self._fullClone(shallowClone)
        except buildstep.BuildStepFailed:
            if not self._shared_cache_active:
                raise
            res = 1
        return res

    @defer.inlineCallbacks
    def _fullCloneOrFallback(self, shallowClone: bool | int) -> InlineCallbacksType[int | None]:
        """Wrapper for _fullClone(). In the case of failure, if clobberOnFailure
        is set to True remove the build directory and try a full clone again.
        """

        res = yield self._fullCloneCacheAware(shallowClone)
        if res != RC_SUCCESS and self._shared_cache_active:
            self._disableSharedCache()
            yield self._doClobber()
            res = yield self._fullClone(shallowClone)
        if res != RC_SUCCESS:
            if not self.clobberOnFailure:
                raise buildstep.BuildStepFailed()
            res = yield self.clobber()
        return res

    @defer.inlineCallbacks
    def _doClobber(self) -> InlineCallbacksType[int]:
        rc = yield self.runRmdir(self.workdir, timeout=self.timeout)
        if rc != RC_SUCCESS:
            raise RuntimeError("Failed to delete directory")
        return rc

    def computeSourceRevision(self, changes: list[TempChange] | None) -> Any:
        if not changes:
            return None
        return changes[-1].revision

    @defer.inlineCallbacks
    def _syncSubmodule(self, _: Any = None) -> InlineCallbacksType[int]:
        rc = RC_SUCCESS
        if self.submodules:
            rc = yield self._dovccmd(['submodule', 'sync'])
        return rc

    @defer.inlineCallbacks
    def _updateSubmodule(self, _: Any = None) -> InlineCallbacksType[int]:
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
    def _cleanSubmodule(self, _: Any = None) -> InlineCallbacksType[int]:
        rc = RC_SUCCESS
        if self.submodules:
            subcommand = 'git clean -f -f -d'
            if self.mode == 'full' and self.method == 'fresh':
                subcommand += ' -x'
            command = ['submodule', 'foreach', '--recursive', subcommand]
            rc = yield self._dovccmd(command)
        return rc

    def _getMethod(self) -> str | None:
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'
        return None

    @defer.inlineCallbacks
    def applyPatch(self, patch: Any) -> InlineCallbacksType[int]:
        yield self._dovccmd(['update-index', '--refresh'])

        res = yield self._dovccmd(['apply', '--index', '-p', str(patch[0])], initialStdin=patch[1])
        return res

    @defer.inlineCallbacks
    def _sourcedirIsUpdatable(self) -> InlineCallbacksType[str]:
        if self.workerVersionIsOlderThan('listdir', '2.16'):
            git_path = self.build.path_module.join(self.workdir, '.git')  # type: ignore[union-attr]
            exists = yield self.pathExists(git_path)

            if exists:
                return "update"

            return "clone"

        cmd = remotecommand.RemoteCommand('listdir', {'dir': self.workdir})
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

    def __init__(
        self,
        workdir: str | None = None,
        repourl: IMaybeRenderableType[str] | None = None,
        port: int = 22,
        branch: str | None = None,
        force: bool = False,
        env: dict[str, Any] | None = None,
        timeout: int = 20 * 60,
        logEnviron: bool = True,
        sshPrivateKey: Any = None,
        sshHostKey: Any = None,
        sshKnownHosts: Any = None,
        auth_credentials: tuple[IRenderable | str, IRenderable | str] | None = None,
        git_credentials: GitCredentialOptions | None = None,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.workdir = workdir  # type: ignore[assignment]
        self.repourl = repourl  # type: ignore[assignment]
        self.port = port
        self.branch = branch
        self.force = force
        self.env = env
        self.timeout = timeout
        self.logEnviron = logEnviron
        self.config = config

        super().__init__(**kwargs)

        self.setupGitStep()
        if auth_credentials is not None:
            git_credentials = add_user_password_to_credentials(
                auth_credentials,
                repourl,
                git_credentials,
            )

        self.setup_git_auth(
            sshPrivateKey,
            sshHostKey,
            sshKnownHosts,
            git_credentials,
        )

        if not self.branch:
            bbconfig.error('GitPush: must provide branch')

    def _get_auth_data_workdir(self) -> str:
        return cast(str, self.workdir)

    @defer.inlineCallbacks
    def run(self) -> InlineCallbacksType[int]:
        self.setup_repourl()
        self.stdio_log = yield self.addLog("stdio")

        auth_workdir = self._get_auth_data_workdir()

        try:
            gitInstalled = yield self.checkFeatureSupport()

            if not gitInstalled:
                raise WorkerSetupError("git is not installed on worker")

            yield self._git_auth.download_auth_files_if_needed(auth_workdir)
            ret = yield self._doPush()
            return ret
        finally:
            yield self._git_auth.remove_auth_files_if_needed(auth_workdir)

    @defer.inlineCallbacks
    def _doPush(self) -> InlineCallbacksType[int | None]:
        cmd: list[str] = ['push', self.repourl, self.branch]  # type: ignore[list-item]
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

    def __init__(
        self,
        workdir: str | None = None,
        tagName: str | None = None,
        annotated: bool = False,
        messages: list[str] | None = None,
        force: bool = False,
        env: dict[str, Any] | None = None,
        timeout: int = 20 * 60,
        logEnviron: bool = True,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.workdir = workdir  # type: ignore[assignment]
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
        self.port = None  # type: ignore[assignment]

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
    def run(self) -> InlineCallbacksType[int]:
        self.stdio_log = yield self.addLog("stdio")
        gitInstalled = yield self.checkFeatureSupport()

        if not gitInstalled:
            raise WorkerSetupError("git is not installed on worker")

        ret = yield self._doTag()
        return ret

    @defer.inlineCallbacks
    def _doTag(self) -> InlineCallbacksType[int | None]:
        cmd = ['tag']

        if self.annotated:
            cmd.append('-a')
            cmd.append(cast(str, self.tagName))

            for msg in cast(list[str], self.messages):
                cmd.extend(['-m', msg])
        else:
            cmd.append(cast(str, self.tagName))

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

    def __init__(
        self,
        workdir: str | None = None,
        paths: list[str] | None = None,
        messages: list[str] | None = None,
        env: dict[str, Any] | None = None,
        timeout: int = 20 * 60,
        logEnviron: bool = True,
        emptyCommits: str = 'disallow',
        config: dict[str, Any] | None = None,
        no_verify: bool = False,
        **kwargs: Any,
    ) -> None:
        self.workdir = workdir  # type: ignore[assignment]
        self.messages = messages
        self.paths = paths
        self.env = env
        self.timeout = timeout
        self.logEnviron = logEnviron
        self.config = config
        self.emptyCommits = emptyCommits
        self.no_verify = no_verify
        # The repourl attribute is required by
        # GitStepMixin, but isn't needed by git add and commit operations
        self.repourl = " "
        self.port = None  # type: ignore[assignment]

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
            bbconfig.error(
                'GitCommit: emptyCommits must be one of "disallow", '
                '"create-empty-commit" and "ignore"'
            )

    @defer.inlineCallbacks
    def run(self) -> InlineCallbacksType[int]:
        self.stdio_log = yield self.addLog("stdio")
        gitInstalled = yield self.checkFeatureSupport()

        if not gitInstalled:
            raise WorkerSetupError("git is not installed on worker")

        yield self._checkDetachedHead()
        yield self._doAdd()
        yield self._doCommit()

        return RC_SUCCESS

    @defer.inlineCallbacks
    def _checkDetachedHead(self) -> InlineCallbacksType[None]:
        cmd = ['symbolic-ref', 'HEAD']
        rc = yield self._dovccmd(cmd, abandonOnFailure=False)

        if rc != RC_SUCCESS:
            yield self.stdio_log.addStderr("You are in detached HEAD")  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            raise buildstep.BuildStepFailed

    @defer.inlineCallbacks
    def _checkHasSomethingToCommit(self) -> InlineCallbacksType[bool]:
        cmd = ['status', '--porcelain=v1']
        stdout = yield self._dovccmd(cmd, collectStdout=True)

        for line in stdout.splitlines(False):
            if line[0] in 'MADRCU':
                return True
        return False

    @defer.inlineCallbacks
    def _doCommit(self) -> InlineCallbacksType[int | None]:
        if self.emptyCommits == 'ignore':
            has_commit = yield self._checkHasSomethingToCommit()
            if not has_commit:
                return 0

        cmd = ['commit']

        for message in self.messages:  # type: ignore[union-attr]
            cmd.extend(['-m', message])

        if self.emptyCommits == 'create-empty-commit':
            cmd.extend(['--allow-empty'])

        if self.no_verify:
            cmd.extend(['--no-verify'])

        ret = yield self._dovccmd(cmd)
        return ret

    @defer.inlineCallbacks
    def _doAdd(self) -> InlineCallbacksType[int | None]:
        cmd = ['add']

        cmd.extend(self.paths)  # type: ignore[arg-type]

        ret = yield self._dovccmd(cmd)
        return ret
