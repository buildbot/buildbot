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

import os
import re
import stat
from urllib.parse import quote as urlquote

from twisted.internet import defer
from twisted.internet import utils
from twisted.python import log

from buildbot import config
from buildbot.changes import base
from buildbot.util import bytes2unicode
from buildbot.util import private_tempdir
from buildbot.util.git import GitMixin
from buildbot.util.git import getSshKnownHostsContents
from buildbot.util.misc import writeLocalFile
from buildbot.util.state import StateMixin


class GitError(Exception):

    """Raised when git exits with code 128."""


class GitPoller(base.PollingChangeSource, StateMixin, GitMixin):

    """This source will poll a remote git repo for changes and submit
    them to the change master."""

    compare_attrs = ("repourl", "branches", "workdir",
                     "pollInterval", "gitbin", "usetimestamps",
                     "category", "project", "pollAtLaunch",
                     "buildPushesWithNoCommits", "sshPrivateKey", "sshHostKey",
                     "sshKnownHosts")

    secrets = ("sshPrivateKey", "sshHostKey", "sshKnownHosts")

    def __init__(self, repourl, branches=None, branch=None,
                 workdir=None, pollInterval=10 * 60,
                 gitbin='git', usetimestamps=True,
                 category=None, project=None,
                 pollinterval=-2, fetch_refspec=None,
                 encoding='utf-8', name=None, pollAtLaunch=False,
                 buildPushesWithNoCommits=False, only_tags=False,
                 sshPrivateKey=None, sshHostKey=None, sshKnownHosts=None):

        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval

        if name is None:
            name = repourl

        super().__init__(name=name,
                         pollInterval=pollInterval,
                         pollAtLaunch=pollAtLaunch,
                         sshPrivateKey=sshPrivateKey,
                         sshHostKey=sshHostKey,
                         sshKnownHosts=sshKnownHosts)

        if project is None:
            project = ''

        if only_tags and (branch or branches):
            config.error("GitPoller: can't specify only_tags and branch/branches")
        if branch and branches:
            config.error("GitPoller: can't specify both branch and branches")
        elif branch:
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
        self.category = category if callable(
            category) else bytes2unicode(category, encoding=self.encoding)
        self.project = bytes2unicode(project, encoding=self.encoding)
        self.changeCount = 0
        self.lastRev = {}
        self.sshPrivateKey = sshPrivateKey
        self.sshHostKey = sshHostKey
        self.sshKnownHosts = sshKnownHosts
        self.setupGit(logname='GitPoller')

        if fetch_refspec is not None:
            config.error("GitPoller: fetch_refspec is no longer supported. "
                         "Instead, only the given branches are downloaded.")

        if self.workdir is None:
            self.workdir = 'gitpoller-work'

    @defer.inlineCallbacks
    def _checkGitFeatures(self):
        stdout = yield self._dovccmd('--version', [])

        self.parseGitFeatures(stdout)
        if not self.gitInstalled:
            raise EnvironmentError('Git is not installed')

        if (self.sshPrivateKey is not None and
                not self.supportsSshPrivateKeyAsEnvOption):
            raise EnvironmentError('SSH private keys require Git 2.3.0 or newer')

    @defer.inlineCallbacks
    def activate(self):
        # make our workdir absolute, relative to the master's basedir
        if not os.path.isabs(self.workdir):
            self.workdir = os.path.join(self.master.basedir, self.workdir)
            log.msg("gitpoller: using workdir '{}'".format(self.workdir))

        try:
            self.lastRev = yield self.getState('lastRev', {})

            super().activate()
        except Exception as e:
            log.err(e, 'while initializing GitPoller repository')

    def describe(self):
        str = ('GitPoller watching the remote git repository ' +
               bytes2unicode(self.repourl, self.encoding))

        if self.branches:
            if self.branches is True:
                str += ', branches: ALL'
            elif not callable(self.branches):
                str += ', branches: ' + ', '.join(self.branches)

        if not self.master:
            str += " [STOPPED - check log]"

        return str

    def _getBranches(self):
        d = self._dovccmd('ls-remote', ['--refs', self.repourl])

        @d.addCallback
        def parseRemote(rows):
            branches = []
            for row in rows.splitlines():
                if '\t' not in row:
                    # Not a useful line
                    continue
                sha, ref = row.split("\t")
                branches.append(ref)
            return branches
        return d

    def _headsFilter(self, branch):
        """Filter out remote references that don't begin with 'refs/heads'."""
        return branch.startswith("refs/heads/")

    def _removeHeads(self, branch):
        """Remove 'refs/heads/' prefix from remote references."""
        if branch.startswith("refs/heads/"):
            branch = branch[11:]
        return branch

    def _trackerBranch(self, branch):
        # manually quote tilde for Python 3.7
        url = urlquote(self.repourl, '').replace('~', '%7E')
        return "refs/buildbot/{}/{}".format(url, self._removeHeads(branch))

    @defer.inlineCallbacks
    def poll(self):
        yield self._checkGitFeatures()

        try:
            yield self._dovccmd('init', ['--bare', self.workdir])
        except GitError as e:
            log.msg(e.args[0])
            return

        branches = self.branches if self.branches else []
        remote_refs = yield self._getBranches()
        if branches is True or callable(branches):
            if callable(self.branches):
                branches = [b for b in remote_refs if self.branches(b)]
            else:
                branches = [b for b in remote_refs if self._headsFilter(b)]
        elif branches and remote_refs:
            remote_branches = [self._removeHeads(b) for b in remote_refs]
            branches = sorted(list(set(branches) & set(remote_branches)))

        refspecs = [
            '+{}:{}'.format(self._removeHeads(branch), self._trackerBranch(branch))
            for branch in branches
        ]

        try:
            yield self._dovccmd('fetch', [self.repourl] + refspecs,
                                path=self.workdir)
        except GitError as e:
            log.msg(e.args[0])
            return

        revs = {}
        log.msg('gitpoller: processing changes from "{}"'.format(self.repourl))
        for branch in branches:
            try:
                rev = yield self._dovccmd(
                    'rev-parse', [self._trackerBranch(branch)], path=self.workdir)
                revs[branch] = bytes2unicode(rev, self.encoding)
                yield self._process_changes(revs[branch], branch)
            except Exception:
                log.err(_why="trying to poll branch {} of {}".format(
                        branch, self.repourl))

        self.lastRev.update(revs)
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
                        'gitpoller: caught exception converting output \'{}\' to timestamp'.format(git_output))
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
                file = bytes2unicode(match.groups()[0], encoding=self.encoding,
                                     errors='unicode_escape')
            return bytes2unicode(file, encoding=self.encoding)

        @d.addCallback
        def process(git_output):
            fileList = [decode_file(file)
                        for file in
                        [s for s in git_output.splitlines() if len(s)]]
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
        rebuild = False
        if newRev in self.lastRev.values():
            if self.buildPushesWithNoCommits:
                existingRev = self.lastRev.get(branch)
                if existingRev is None:
                    # This branch was completely unknown, rebuild
                    log.msg('gitpoller: rebuilding {} for new branch "{}"'.format(
                            newRev, branch))
                    rebuild = True
                elif existingRev != newRev:
                    # This branch is known, but it now points to a different
                    # commit than last time we saw it, rebuild.
                    log.msg('gitpoller: rebuilding {} for updated branch "{}"'.format(
                            newRev, branch))
                    rebuild = True

        # get the change list
        revListArgs = (['--format=%H', '{}'.format(newRev)] +
                       ['^' + rev
                        for rev in sorted(self.lastRev.values())] +
                       ['--'])
        self.changeCount = 0
        results = yield self._dovccmd('log', revListArgs, path=self.workdir)

        # process oldest change first
        revList = results.split()
        revList.reverse()

        if rebuild and not revList:
            revList = [newRev]

        self.changeCount = len(revList)
        self.lastRev[branch] = newRev

        if self.changeCount:
            log.msg('gitpoller: processing {} changes: {} from "{}" branch "{}"'.format(
                    self.changeCount, revList, self.repourl, branch))

        for rev in revList:
            dl = defer.DeferredList([
                self._get_commit_timestamp(rev),
                self._get_commit_author(rev),
                self._get_commit_files(rev),
                self._get_commit_comments(rev),
            ], consumeErrors=True)

            results = yield dl

            # check for failures
            failures = [r[1] for r in results if not r[0]]
            if failures:
                for failure in failures:
                    log.err(
                        failure, "while processing changes for {} {}".format(newRev, branch))
                # just fail on the first error; they're probably all related!
                failures[0].raiseException()

            timestamp, author, files, comments = [r[1] for r in results]

            yield self.master.data.updates.addChange(
                author=author,
                revision=bytes2unicode(rev, encoding=self.encoding),
                files=files, comments=comments, when_timestamp=timestamp,
                branch=bytes2unicode(self._removeHeads(branch)),
                project=self.project,
                repository=bytes2unicode(self.repourl, encoding=self.encoding),
                category=self.category, src='git')

    def _isSshPrivateKeyNeededForCommand(self, command):
        commandsThatNeedKey = [
            'fetch',
            'ls-remote',
        ]
        if self.sshPrivateKey is not None and command in commandsThatNeedKey:
            return True
        return False

    def _downloadSshPrivateKey(self, keyPath):
        # We change the permissions of the key file to be user-readable only so
        # that ssh does not complain. This is not used for security because the
        # parent directory will have proper permissions.
        writeLocalFile(keyPath, self.sshPrivateKey, mode=stat.S_IRUSR)

    def _downloadSshKnownHosts(self, path):
        if self.sshKnownHosts is not None:
            contents = self.sshKnownHosts
        else:
            contents = getSshKnownHostsContents(self.sshHostKey)
        writeLocalFile(path, contents)

    def _getSshPrivateKeyPath(self, ssh_data_path):
        return os.path.join(ssh_data_path, 'ssh-key')

    def _getSshKnownHostsPath(self, ssh_data_path):
        return os.path.join(ssh_data_path, 'ssh-known-hosts')

    @defer.inlineCallbacks
    def _dovccmd(self, command, args, path=None):
        if self._isSshPrivateKeyNeededForCommand(command):
            with private_tempdir.PrivateTemporaryDirectory(
                    dir=self.workdir, prefix='.buildbot-ssh') as tmp_path:
                stdout = yield self._dovccmdImpl(command, args, path, tmp_path)
        else:
            stdout = yield self._dovccmdImpl(command, args, path, None)
        return stdout

    @defer.inlineCallbacks
    def _dovccmdImpl(self, command, args, path, ssh_workdir):
        full_args = []
        full_env = os.environ.copy()

        if self._isSshPrivateKeyNeededForCommand(command):
            key_path = self._getSshPrivateKeyPath(ssh_workdir)
            self._downloadSshPrivateKey(key_path)

            known_hosts_path = None
            if self.sshHostKey is not None or self.sshKnownHosts is not None:
                known_hosts_path = self._getSshKnownHostsPath(ssh_workdir)
                self._downloadSshKnownHosts(known_hosts_path)

            self.adjustCommandParamsForSshPrivateKey(full_args, full_env,
                                                     key_path, None,
                                                     known_hosts_path)

        full_args += [command] + args

        res = yield utils.getProcessOutputAndValue(self.gitbin,
            full_args, path=path, env=full_env)
        (stdout, stderr, code) = res
        stdout = bytes2unicode(stdout, self.encoding)
        stderr = bytes2unicode(stderr, self.encoding)
        if code != 0:
            if code == 128:
                raise GitError('command {} in {} on repourl {} failed with exit code {}: {}'.format(
                               full_args, path, self.repourl, code, stderr))
            raise EnvironmentError('command {} in {} on repourl {} failed with exit code {}: {}'.format(
                                   full_args, path, self.repourl, code, stderr))
        return stdout.strip()
