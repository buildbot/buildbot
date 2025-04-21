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

import contextlib
import os
import re
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import Sequence
from typing import cast
from urllib.parse import quote as urlquote

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.changes import base
from buildbot.process.codebase import Codebase
from buildbot.util import bytes2unicode
from buildbot.util import giturlparse
from buildbot.util import private_tempdir
from buildbot.util import runprocess
from buildbot.util import unicode2bytes
from buildbot.util.git import GitMixin
from buildbot.util.git import GitServiceAuth
from buildbot.util.git import check_ssh_config
from buildbot.util.git_credential import GitCredentialOptions
from buildbot.util.git_credential import add_user_password_to_credentials
from buildbot.util.state import StateMixin
from buildbot.util.twisted import InlineCallbacksType
from buildbot.util.twisted import async_to_deferred

if TYPE_CHECKING:
    from typing import Callable
    from typing import Literal

    from buildbot.interfaces import IRenderable


class GitError(Exception):
    """Raised when git exits with code 128."""


class GitPoller(base.ReconfigurablePollingChangeSource, StateMixin, GitMixin):
    """This source will poll a remote git repo for changes and submit
    them to the change master."""

    compare_attrs: ClassVar[Sequence[str]] = (
        "repourl",
        "branches",
        "workdir",
        "pollInterval",
        "gitbin",
        "usetimestamps",
        "category",
        'codebase',
        "project",
        "pollAtLaunch",
        "buildPushesWithNoCommits",
        "pollRandomDelayMin",
        "pollRandomDelayMax",
        "_git_auth",
    )

    def __init__(self, repourl: str, **kwargs: Any) -> None:
        self._git_auth = GitServiceAuth(self)

        self.lastRev: dict[str, str] | None = None

        name = kwargs.get("name", None)
        if name is None:
            kwargs["name"] = repourl
        super().__init__(repourl, **kwargs)

    def checkConfig(  # type: ignore[override]
        self,
        repourl: str,
        branches: list[str] | Literal[True] | Callable[[str], bool] | None = None,
        branch: str | None = None,
        workdir: str | None = None,
        pollInterval: int = 10 * 60,
        gitbin: str = "git",
        usetimestamps: bool = True,
        category: str | Callable[[str], str] | None = None,
        codebase: Codebase | None = None,
        project: str | None = None,
        fetch_refspec: str | None = None,
        encoding: str = "utf-8",
        name: str | None = None,
        pollAtLaunch: bool = False,
        buildPushesWithNoCommits: bool = False,
        only_tags: bool = False,
        sshPrivateKey: str | None = None,
        sshHostKey: str | None = None,
        sshKnownHosts: str | None = None,
        pollRandomDelayMin: int = 0,
        pollRandomDelayMax: int = 0,
        auth_credentials: tuple[IRenderable | str, IRenderable | str] | None = None,
        git_credentials: GitCredentialOptions | None = None,
    ) -> None:
        if only_tags and (branch or branches):
            config.error("GitPoller: can't specify only_tags and branch/branches")
        if branch and branches:
            config.error("GitPoller: can't specify both branch and branches")
        if branch and not isinstance(branch, str):
            config.error("GitPoller: 'branch' argument must be a str")
        if branches is not None and not (
            (isinstance(branches, list) and all(isinstance(e, str) for e in branches))
            or branches is True
            or callable(branches)
        ):
            config.error(
                "GitPoller: 'branches' argument must be one of "
                "list of str, True, or Callable[[str], bool]"
            )

        check_ssh_config('GitPoller', sshPrivateKey, sshHostKey, sshKnownHosts)

        if fetch_refspec is not None:
            config.error(
                "GitPoller: fetch_refspec is no longer supported. "
                "Instead, only the given branches are downloaded."
            )

        if name is None:
            name = repourl

        if not isinstance(codebase, (Codebase, type(None))):
            config.error(
                f'{self.__class__.__name__}: codebase must be None or instance of Codebase'
            )

        super().checkConfig(
            name=name,
            pollInterval=pollInterval,
            pollAtLaunch=pollAtLaunch,
            pollRandomDelayMin=pollRandomDelayMin,
            pollRandomDelayMax=pollRandomDelayMax,
        )

    @defer.inlineCallbacks
    def reconfigService(  # type: ignore[override]
        self,
        repourl: str,
        branches: list[str] | Literal[True] | Callable[[str], bool] | None = None,
        branch: str | None = None,
        workdir: str | None = None,
        pollInterval: int = 10 * 60,
        gitbin: str = "git",
        usetimestamps: bool = True,
        category: str | Callable[[str], str] | None = None,
        codebase: Codebase | None = None,
        project: str | None = None,
        fetch_refspec: str | None = None,
        encoding: str = "utf-8",
        name: str | None = None,
        pollAtLaunch: bool = False,
        buildPushesWithNoCommits: bool = False,
        only_tags: bool = False,
        sshPrivateKey: str | None = None,
        sshHostKey: str | None = None,
        sshKnownHosts: str | None = None,
        pollRandomDelayMin: int = 0,
        pollRandomDelayMax: int = 0,
        auth_credentials: tuple[IRenderable | str, IRenderable | str] | None = None,
        git_credentials: GitCredentialOptions | None = None,
    ) -> InlineCallbacksType[None]:
        if name is None:
            name = repourl

        if project is None:
            project = ''

        if branch:
            branches = [branch]
        elif not branches:
            if only_tags:
                branches = lambda ref: ref.startswith('refs/tags/')
            else:
                branches = None

        self.repourl = repourl
        self.branches = branches
        self.encoding = encoding
        self.buildPushesWithNoCommits = buildPushesWithNoCommits
        self.gitbin = gitbin
        self.workdir = workdir
        self.usetimestamps = usetimestamps
        self.category = (
            category if callable(category) else bytes2unicode(category, encoding=self.encoding)
        )
        self.codebase = codebase

        if codebase is not None:
            projectid = yield self.master.data.updates.find_project_id(
                codebase.project, auto_create=False
            )
            if projectid is None:
                raise RuntimeError(f'Project {codebase.project} is not configured')

            self._codebase_id = yield self.master.data.updates.find_codebase_id(
                projectid=projectid, name=codebase.name
            )
        else:
            self._codebase_id = None

        self.project = bytes2unicode(project, encoding=self.encoding)
        self.lastRev = None

        self.setupGit()

        if auth_credentials is not None:
            git_credentials = add_user_password_to_credentials(
                auth_credentials,
                repourl,
                git_credentials,
            )

        self._git_auth = GitServiceAuth(
            self, sshPrivateKey, sshHostKey, sshKnownHosts, git_credentials
        )

        if self.workdir is None:
            self.workdir = 'gitpoller-work'

        # make our workdir absolute, relative to the master's basedir

        if not os.path.isabs(self.workdir):
            self.workdir = os.path.join(self.master.basedir, self.workdir)
            log.msg(f"gitpoller: using workdir '{self.workdir}'")

        yield super().reconfigService(
            name=name,
            pollInterval=pollInterval,
            pollAtLaunch=pollAtLaunch,
            pollRandomDelayMin=pollRandomDelayMin,
            pollRandomDelayMax=pollRandomDelayMax,
        )

    @defer.inlineCallbacks
    def _checkGitFeatures(self) -> InlineCallbacksType[None]:
        stdout = yield self._dovccmd('--version', [])

        self.parseGitFeatures(stdout)
        if not self.gitInstalled:
            raise OSError('Git is not installed')

        if not self.supportsSshPrivateKeyAsEnvOption:
            has_ssh_private_key = (
                yield self.renderSecrets(self._git_auth.ssh_private_key)
            ) is not None
            if has_ssh_private_key:
                raise OSError('SSH private keys require Git 2.3.0 or newer')

    def activate(self) -> defer.Deferred[None]:  # type: ignore[override]
        try:
            self.lastRev = None

            super().activate()
        except Exception as e:
            log.err(e, 'while initializing GitPoller repository')
        return defer.succeed(None)

    def describe(self) -> str:
        str = 'GitPoller watching the remote git repository ' + bytes2unicode(
            self.repourl, self.encoding
        )

        if self.branches:
            if self.branches is True:
                str += ', branches: ALL'
            elif not callable(self.branches):
                str += ', branches: ' + ', '.join(self.branches)

        if not self.master:
            str += " [STOPPED - check log]"

        return str

    @async_to_deferred
    async def _resolve_head_ref(self, git_auth_files_path: str | None = None) -> str | None:
        if self.supports_lsremote_symref:
            rows: str = await self._dovccmd(
                'ls-remote',
                ['--symref', self.repourl, 'HEAD'],
                auth_files_path=git_auth_files_path,
            )
            # simple parse of output which should have format:
            # ref: refs/heads/{branch}	HEAD
            # {hash}	HEAD
            parts = rows.split(maxsplit=3)
            # sanity just in case
            if len(parts) >= 3 and parts[0] == 'ref:' and parts[2] == 'HEAD':
                return parts[1]
            return None

        # naive fallback if git version does not support --symref
        rows = await self._dovccmd('ls-remote', [self.repourl, 'HEAD', 'refs/heads/*'])
        refs = [row.split('\t') for row in rows.splitlines() if '\t' in row]
        # retrieve hash that HEAD points to
        head_hash = next((hash for hash, ref in refs if ref == 'HEAD'), None)
        if head_hash is None:
            return None

        # get refs that points to the same hash as HEAD
        candidates = [ref for hash, ref in refs if ref != 'HEAD' and hash == head_hash]
        # Found default branch
        if len(candidates) == 1:
            return candidates[0]

        # If multiple ref points to the same hash as HEAD,
        # we have no way to know which one is the default
        return None

    @async_to_deferred
    async def _list_remote_refs(
        self, refs: list[str] | None = None, git_auth_files_path: str | None = None
    ) -> list[str]:
        rows: str = await self._dovccmd(
            'ls-remote',
            ['--refs', self.repourl] + (refs if refs is not None else []),
            auth_files_path=git_auth_files_path,
        )

        branches: list[str] = []
        for row in rows.splitlines():
            if '\t' not in row:
                # Not a useful line
                continue
            _, ref = row.split("\t")
            branches.append(ref)

        return branches

    @staticmethod
    def _trim_prefix(value: str, prefix: str) -> str:
        """Remove prefix from value."""
        if value.startswith(prefix):
            return value[len(prefix) :]
        return value

    def _removeHeads(self, branch: str) -> str:
        """Remove 'refs/heads/' prefix from remote references."""
        if branch.startswith("refs/heads/"):
            branch = branch[11:]
        return branch

    @staticmethod
    def _tracker_ref(repourl: str, ref: str) -> str:
        def _sanitize(value: str) -> str:
            return urlquote(value, '').replace('~', '%7E')

        tracker_prefix = "refs/buildbot"
        # if ref is not a Git ref, store under a different path to avoid collision
        if not ref.startswith('refs/'):
            tracker_prefix += "/raw"

        git_url = giturlparse(repourl)
        if git_url is None:
            # fallback to using the whole repourl
            url_identifier = _sanitize(repourl)
        else:
            url_identifier = f"{git_url.proto}/{_sanitize(git_url.domain)}"
            if git_url.port is not None:
                # replace `:` with url encode `%3A`
                url_identifier += f"%3A{git_url.port}"

            if git_url.owner is not None:
                url_identifier += f"/{_sanitize(git_url.owner)}"
            url_identifier += f"/{_sanitize(git_url.repo)}"

        return f"{tracker_prefix}/{url_identifier}/{GitPoller._trim_prefix(ref, 'refs/')}"

    def poll_should_exit(self) -> bool:
        # A single gitpoller loop may take a while on a loaded master, which would block
        # reconfiguration, so we try to exit early.
        return not self.doPoll.running

    @defer.inlineCallbacks
    def poll(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self._checkGitFeatures()

        try:
            assert self.workdir is not None
            yield self._dovccmd('init', ['--bare', self.workdir])
        except GitError as e:
            log.msg(e.args[0])
            return

        tmp_dir = (
            private_tempdir.PrivateTemporaryDirectory(dir=self.workdir, prefix='.buildbot-ssh')
            if self._git_auth.is_auth_needed
            else contextlib.nullcontext()
        )
        # retrieve auth files
        with tmp_dir as tmp_path:
            yield self._git_auth.download_auth_files_if_needed(cast(str, tmp_path))

            refs, trim_ref_head = yield self._get_refs(cast(str, tmp_path))

            # Nothing to fetch and process.
            if not refs:
                return

            if self.poll_should_exit():
                return

            refspecs = [f'+{ref}:{self._tracker_ref(self.repourl, ref)}' for ref in refs]

            try:
                yield self._dovccmd(
                    'fetch',
                    ["--progress", self.repourl, *refspecs, "--"],
                    path=self.workdir,
                    auth_files_path=tmp_path,
                )
            except GitError as e:
                log.msg(e.args[0])
                return

        if self.lastRev is None:
            self.lastRev = yield self.getState('lastRev', {})

        revs = {}
        log.msg(f'gitpoller: processing changes from "{self.repourl}"')
        for ref in refs:
            branch = ref if not trim_ref_head else self._trim_prefix(ref, 'refs/heads/')
            try:
                if self.poll_should_exit():  # pragma: no cover
                    # Note that we still want to update the last known revisions for the branches
                    # we did process
                    break

                rev = yield self._dovccmd(
                    'rev-parse', [self._tracker_ref(self.repourl, ref)], path=self.workdir
                )
                revs[branch] = rev
                yield self._process_changes(rev, branch)
            except Exception:
                log.err(_why=f"trying to poll branch {branch} of {self.repourl}")

        self.lastRev = revs
        yield self.setState('lastRev', self.lastRev)

    @async_to_deferred
    async def _get_refs(self, git_auth_files_path: str) -> tuple[list[str], bool]:
        if callable(self.branches):
            # Get all refs and let callback filter them
            remote_refs = await self._list_remote_refs(git_auth_files_path=git_auth_files_path)
            refs = [b for b in remote_refs if self.branches(b)]
            return (refs, False)

        if self.branches is True:
            # Get all branch refs
            refs = await self._list_remote_refs(
                refs=["refs/heads/*"],
                git_auth_files_path=git_auth_files_path,
            )
            return (refs, False)

        if self.branches:
            refs = await self._list_remote_refs(
                refs=[f"refs/heads/{b}" for b in self.branches],
                git_auth_files_path=git_auth_files_path,
            )
            return (refs, True)

        head_ref = await self._resolve_head_ref(git_auth_files_path=git_auth_files_path)
        if head_ref is not None:
            return ([head_ref], False)

        # unlikely, but if we can't find HEAD here, something weird happen,
        # but not a critical error. Just use HEAD as the ref to use
        return (['HEAD'], False)

    def _get_commit_comments(self, rev: str) -> defer.Deferred[str]:
        args = ['--no-walk', r'--format=%s%n%b', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)
        return d  # type: ignore[return-value]

    @defer.inlineCallbacks
    def _get_commit_timestamp(self, rev: str) -> InlineCallbacksType[int | None]:
        # unix timestamp
        args = ['--no-walk', r'--format=%ct', rev, '--']
        git_output = yield self._dovccmd('log', args, path=self.workdir)
        if self.usetimestamps:
            try:
                stamp = int(git_output)
            except Exception as e:
                log.msg(
                    f'gitpoller: caught exception converting output \'{git_output}\' to timestamp'
                )
                raise e
            return stamp
        return None

    @defer.inlineCallbacks
    def _get_commit_files(self, rev: str) -> InlineCallbacksType[list[str]]:
        args = ['--name-only', '--no-walk', r'--format=%n', '-m', '--first-parent', rev, '--']
        git_output = yield self._dovccmd('log', args, path=self.workdir)

        def decode_file(file: str) -> str:
            # git use octal char sequences in quotes when non ASCII
            match = re.match('^"(.*)"$', file)
            if match:
                file = bytes2unicode(
                    match.groups()[0], encoding=self.encoding, errors='unicode_escape'
                )
            return bytes2unicode(file, encoding=self.encoding)

        fileList = [decode_file(file) for file in [s for s in git_output.splitlines() if len(s)]]
        return fileList

    @defer.inlineCallbacks
    def _get_commit_author(self, rev: str) -> InlineCallbacksType[str]:
        args = ['--no-walk', r'--format=%aN <%aE>', rev, '--']
        git_output = yield self._dovccmd('log', args, path=self.workdir)
        if not git_output:
            raise OSError('could not get commit author for rev')
        return git_output

    @defer.inlineCallbacks
    def _get_commit_committer(self, rev: str) -> InlineCallbacksType[str]:
        args = ['--no-walk', r'--format=%cN <%cE>', rev, '--']
        res = yield self._dovccmd('log', args, path=self.workdir)
        if not res:
            raise OSError('could not get commit committer for rev')
        return res

    def _get_commit_parent_hashes(self, rev: str) -> defer.Deferred[str]:
        args = ['--no-walk', r'--format=%P', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)
        return d

    @defer.inlineCallbacks
    def _process_changes(self, newRev: str, branch: str) -> InlineCallbacksType[None]:
        """
        Read changes since last change.

        - Read list of commit hashes.
        - Extract details from each commit.
        - Add changes to database.
        """

        # initial run, don't parse all history
        if not self.lastRev:
            return

        # get the change list
        revListArgs = (
            ['--ignore-missing', '--first-parent']
            + ['--format=%H', f'{newRev}']
            + ['^' + rev for rev in sorted(self.lastRev.values())]
            + ['--']
        )
        results = yield self._dovccmd('log', revListArgs, path=self.workdir)

        # process oldest change first
        revList = results.split()
        revList.reverse()

        if self.buildPushesWithNoCommits and not revList:
            existingRev = self.lastRev.get(branch)
            if existingRev != newRev:
                revList = [newRev]
                if existingRev is None:
                    # This branch was completely unknown, rebuild
                    log.msg(f'gitpoller: rebuilding {newRev} for new branch "{branch}"')
                else:
                    # This branch is known, but it now points to a different
                    # commit than last time we saw it, rebuild.
                    log.msg(f'gitpoller: rebuilding {newRev} for updated branch "{branch}"')

        change_count = len(revList)
        self.lastRev[branch] = newRev

        if change_count:
            log.msg(
                f'gitpoller: processing {change_count} changes: {revList} from '
                f'"{self.repourl}" branch "{branch}"'
            )

        last_commit_id = None
        if self._codebase_id is not None and change_count:
            rev = revList[0]
            parent_hashes = yield self._get_commit_parent_hashes(rev)
            parent_hash = parent_hashes.split()[0]
            last_commit = yield self.master.data.get((
                'codebases',
                self._codebase_id,
                'commits_by_revision',
                parent_hash,
            ))
            if last_commit is not None:
                last_commit_id = last_commit['commitid']

        for rev in revList:
            dl: defer.Deferred[Any] = defer.DeferredList(
                [
                    self._get_commit_timestamp(rev),
                    self._get_commit_author(rev),
                    self._get_commit_committer(rev),
                    self._get_commit_files(rev),
                    self._get_commit_comments(rev),
                ],
                consumeErrors=True,
            )

            results = yield dl

            # check for failures
            failures = [r[1] for r in results if not r[0]]
            if failures:
                for failure in failures:
                    log.err(failure, f"while processing changes for {rev} {branch}")
                # just fail on the first error; they're probably all related!
                failures[0].raiseException()

            timestamp, author, committer, files, comments = [r[1] for r in results]

            yield self.master.data.updates.addChange(
                author=author,
                committer=committer,
                revision=bytes2unicode(rev, encoding=self.encoding),
                files=files,
                comments=comments,
                when_timestamp=timestamp,
                branch=bytes2unicode(self._removeHeads(branch)),
                project=self.project,
                repository=bytes2unicode(self.repourl, encoding=self.encoding),
                category=self.category,
                src='git',
            )

            if self._codebase_id is not None:
                last_commit_id = yield self.master.data.updates.add_commit(
                    codebaseid=self._codebase_id,
                    author=author,
                    committer=committer,
                    comments=comments,
                    when_timestamp=timestamp,
                    revision=bytes2unicode(rev, encoding=self.encoding),
                    parent_commitid=last_commit_id,
                )

        if self._codebase_id is not None and last_commit_id is not None:
            yield self.master.data.updates.update_branch(
                codebaseid=self._codebase_id,
                name=branch,
                commitid=last_commit_id,
                last_timestamp=int(self.master.reactor.seconds()),
            )

    @async_to_deferred
    async def _dovccmd(
        self,
        command: str,
        args: list[str],
        path: str | None = None,
        auth_files_path: str | None = None,
        initial_stdin: str | None = None,
    ) -> str:
        full_args: list[str] = []
        full_env = os.environ.copy()

        if self._git_auth.is_auth_needed_for_git_command(command):
            if auth_files_path is None:
                raise RuntimeError(
                    f"Git command {command} requires auth, but no auth information was provided"
                )
            self._git_auth.adjust_git_command_params_for_auth(
                full_args,
                full_env,
                auth_files_path,
                self,
            )

        full_args += [command, *args]

        res = await runprocess.run_process(
            self.master.reactor,
            [self.gitbin, *full_args],
            path,
            env=full_env,
            initial_stdin=unicode2bytes(initial_stdin) if initial_stdin is not None else None,
        )
        (code, stdout, stderr) = res
        stdout = bytes2unicode(stdout, self.encoding)
        stderr = bytes2unicode(stderr, self.encoding)
        if code != 0:
            if code == 128:
                raise GitError(
                    f'command {full_args} in {path} on repourl {self.repourl} failed '
                    f'with exit code {code}: {stderr}'
                )
            raise OSError(
                f'command {full_args} in {path} on repourl {self.repourl} '
                f'failed with exit code {code}: {stderr}'
            )
        return stdout.strip()
