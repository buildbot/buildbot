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

import os
import re
from typing import TYPE_CHECKING
from urllib.parse import quote as urlquote

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.changes import base
from buildbot.util import bytes2unicode
from buildbot.util import giturlparse
from buildbot.util import private_tempdir
from buildbot.util import runprocess
from buildbot.util.git import GitMixin
from buildbot.util.git import GitServiceAuth
from buildbot.util.git import check_ssh_config
from buildbot.util.state import StateMixin
from buildbot.util.twisted import async_to_deferred
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    from typing import Callable
    from typing import Literal


class GitError(Exception):
    """Raised when git exits with code 128."""


class GitPoller(base.ReconfigurablePollingChangeSource, StateMixin, GitMixin):
    """This source will poll a remote git repo for changes and submit
    them to the change master."""

    compare_attrs = (
        "repourl",
        "branches",
        "workdir",
        "pollInterval",
        "gitbin",
        "usetimestamps",
        "category",
        "project",
        "pollAtLaunch",
        "buildPushesWithNoCommits",
        "pollRandomDelayMin",
        "pollRandomDelayMax",
        "_git_auth",
    )

    def __init__(self, repourl, **kwargs) -> None:
        self._git_auth = GitServiceAuth(self)

        self.lastRev: dict[str, str] | None = None

        name = kwargs.get("name", None)
        if name is None:
            kwargs["name"] = repourl
        super().__init__(repourl, **kwargs)

    def checkConfig(  # type: ignore[override]
        self,
        repourl,
        branches: list[str] | Literal[True] | Callable[[str], bool] | None = None,
        branch: str | None = None,
        workdir=None,
        pollInterval=10 * 60,
        gitbin="git",
        usetimestamps=True,
        category=None,
        project=None,
        pollinterval=-2,
        fetch_refspec=None,
        encoding="utf-8",
        name=None,
        pollAtLaunch=False,
        buildPushesWithNoCommits=False,
        only_tags=False,
        sshPrivateKey=None,
        sshHostKey=None,
        sshKnownHosts=None,
        pollRandomDelayMin=0,
        pollRandomDelayMax=0,
    ):
        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval
            warn_deprecated('3.11.2', 'pollinterval has been deprecated: please use pollInterval')

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

        super().checkConfig(
            name=name,
            pollInterval=pollInterval,
            pollAtLaunch=pollAtLaunch,
            pollRandomDelayMin=pollRandomDelayMin,
            pollRandomDelayMax=pollRandomDelayMax,
        )

    @defer.inlineCallbacks
    def reconfigService(
        self,
        repourl,
        branches=None,
        branch=None,
        workdir=None,
        pollInterval=10 * 60,
        gitbin="git",
        usetimestamps=True,
        category=None,
        project=None,
        pollinterval=-2,
        fetch_refspec=None,
        encoding="utf-8",
        name=None,
        pollAtLaunch=False,
        buildPushesWithNoCommits=False,
        only_tags=False,
        sshPrivateKey=None,
        sshHostKey=None,
        sshKnownHosts=None,
        pollRandomDelayMin=0,
        pollRandomDelayMax=0,
    ):
        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval
            warn_deprecated('3.11.2', 'pollinterval has been deprecated: please use pollInterval')

        if name is None:
            name = repourl

        if project is None:
            project = ''

        if branch:
            branches = [branch]
        elif not branches:
            if only_tags:
                branches = lambda ref: ref.startswith('refs/tags/')  # noqa: E731
            else:
                branches = ['master']

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
        self.project = bytes2unicode(project, encoding=self.encoding)
        self.changeCount = 0
        self.lastRev = None

        self.setupGit()
        self._git_auth = GitServiceAuth(self, sshPrivateKey, sshHostKey, sshKnownHosts)

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
    def _checkGitFeatures(self):
        stdout = yield self._dovccmd('--version', [])

        self.parseGitFeatures(stdout)
        if not self.gitInstalled:
            raise EnvironmentError('Git is not installed')

        if not self.supportsSshPrivateKeyAsEnvOption:
            has_ssh_private_key = (
                yield self.renderSecrets(self._git_auth.ssh_private_key)
            ) is not None
            if has_ssh_private_key:
                raise EnvironmentError('SSH private keys require Git 2.3.0 or newer')

    def activate(self):
        try:
            self.lastRev = None

            super().activate()
        except Exception as e:
            log.err(e, 'while initializing GitPoller repository')

    def describe(self):
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
    async def _get_refs(self, refs: list[str] | None = None) -> list[str]:
        rows: str = await self._dovccmd(
            'ls-remote', ['--refs', self.repourl] + (refs if refs is not None else [])
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

    def _removeHeads(self, branch):
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
                url_identifier += f":{git_url.port}"

            if git_url.owner is not None:
                url_identifier += f"/{_sanitize(git_url.owner)}"
            url_identifier += f"/{_sanitize(git_url.repo)}"

        return f"{tracker_prefix}/{url_identifier}/{GitPoller._trim_prefix(ref, 'refs/')}"

    def poll_should_exit(self):
        # A single gitpoller loop may take a while on a loaded master, which would block
        # reconfiguration, so we try to exit early.
        return not self.doPoll.running

    @defer.inlineCallbacks
    def poll(self):
        yield self._checkGitFeatures()

        try:
            yield self._dovccmd('init', ['--bare', self.workdir])
        except GitError as e:
            log.msg(e.args[0])
            return

        refs: list[str] = []
        trim_ref_head = False
        if callable(self.branches):
            # Get all refs and let callback filter them
            remote_refs = yield self._get_refs()
            refs = [b for b in remote_refs if self.branches(b)]
        elif self.branches is True:
            # Get all branch refs
            refs = yield self._get_refs(["refs/heads/*"])
        elif self.branches:
            refs = yield self._get_refs([f"refs/heads/{b}" for b in self.branches])
            trim_ref_head = True

        # Nothing to fetch and process.
        if not refs:
            return

        if self.poll_should_exit():
            return

        refspecs = [f'+{ref}:{self._tracker_ref(self.repourl, ref)}' for ref in refs]

        try:
            yield self._dovccmd(
                'fetch', ['--progress', self.repourl] + refspecs + ['--'], path=self.workdir
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
                    'rev-parse', [self._tracker_ref(self.repourl, ref), '--'], path=self.workdir
                )
                revs[branch] = rev
                yield self._process_changes(rev, branch)
            except Exception:
                log.err(_why=f"trying to poll branch {branch} of {self.repourl}")

        self.lastRev = revs
        yield self.setState('lastRev', self.lastRev)

    def _get_commit_comments(self, rev):
        args = ['--no-walk', r'--format=%s%n%b', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)
        return d

    def _get_commit_timestamp(self, rev):
        # unix timestamp
        args = ['--no-walk', r'--format=%ct', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)

        @d.addCallback
        def process(git_output):
            if self.usetimestamps:
                try:
                    stamp = int(git_output)
                except Exception as e:
                    log.msg(
                        f'gitpoller: caught exception converting output \'{git_output}\' to '
                        'timestamp'
                    )
                    raise e
                return stamp
            return None

        return d

    def _get_commit_files(self, rev):
        args = ['--name-only', '--no-walk', r'--format=%n', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)

        def decode_file(file):
            # git use octal char sequences in quotes when non ASCII
            match = re.match('^"(.*)"$', file)
            if match:
                file = bytes2unicode(
                    match.groups()[0], encoding=self.encoding, errors='unicode_escape'
                )
            return bytes2unicode(file, encoding=self.encoding)

        @d.addCallback
        def process(git_output):
            fileList = [
                decode_file(file) for file in [s for s in git_output.splitlines() if len(s)]
            ]
            return fileList

        return d

    def _get_commit_author(self, rev):
        args = ['--no-walk', r'--format=%aN <%aE>', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)

        @d.addCallback
        def process(git_output):
            if not git_output:
                raise EnvironmentError('could not get commit author for rev')
            return git_output

        return d

    @defer.inlineCallbacks
    def _get_commit_committer(self, rev):
        args = ['--no-walk', r'--format=%cN <%cE>', rev, '--']
        res = yield self._dovccmd('log', args, path=self.workdir)
        if not res:
            raise EnvironmentError('could not get commit committer for rev')
        return res

    @defer.inlineCallbacks
    def _process_changes(self, newRev, branch):
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
            ['--ignore-missing']
            + ['--format=%H', f'{newRev}']
            + ['^' + rev for rev in sorted(self.lastRev.values())]
            + ['--']
        )
        self.changeCount = 0
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

        self.changeCount = len(revList)
        self.lastRev[branch] = newRev

        if self.changeCount:
            log.msg(
                f'gitpoller: processing {self.changeCount} changes: {revList} from '
                f'"{self.repourl}" branch "{branch}"'
            )

        for rev in revList:
            dl = defer.DeferredList(
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

    @defer.inlineCallbacks
    def _dovccmd(self, command, args, path=None):
        if self._git_auth.is_auth_needed_for_git_command(command):
            with private_tempdir.PrivateTemporaryDirectory(
                dir=self.workdir, prefix='.buildbot-ssh'
            ) as tmp_path:
                stdout = yield self._dovccmdImpl(command, args, path, tmp_path)
        else:
            stdout = yield self._dovccmdImpl(command, args, path, None)
        return stdout

    @defer.inlineCallbacks
    def _dovccmdImpl(self, command: str, args: list[str], path: str, ssh_workdir: str | None):
        full_args: list[str] = []
        full_env = os.environ.copy()

        if ssh_workdir is not None:
            yield self._git_auth.download_auth_files_if_needed(ssh_workdir)
            self._git_auth.adjust_git_command_params_for_auth(
                full_args,
                full_env,
                ssh_workdir,
                self,
            )

        full_args += [command] + args

        res = yield runprocess.run_process(
            self.master.reactor, [self.gitbin] + full_args, path, env=full_env
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
            raise EnvironmentError(
                f'command {full_args} in {path} on repourl {self.repourl} '
                f'failed with exit code {code}: {stderr}'
            )
        return stdout.strip()
