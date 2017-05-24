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
from future.moves.urllib.parse import quote as urlquote
from future.utils import itervalues
from future.utils import text_type

import os
import re

from twisted.internet import defer
from twisted.internet import utils
from twisted.python import log

from buildbot import config
from buildbot.changes import base
from buildbot.util import ascii2unicode
from buildbot.util import bytes2NativeString
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.util.state import StateMixin


class GitError(Exception):

    """Raised when git exits with code 128."""


class GitPoller(base.PollingChangeSource, StateMixin):

    """This source will poll a remote git repo for changes and submit
    them to the change master."""

    compare_attrs = ("repourl", "branches", "workdir",
                     "pollInterval", "gitbin", "usetimestamps",
                     "category", "project", "pollAtLaunch",
                     "buildPushesWithNoCommits")

    def __init__(self, repourl, branches=None, branch=None,
                 workdir=None, pollInterval=10 * 60,
                 gitbin='git', usetimestamps=True,
                 category=None, project=None,
                 pollinterval=-2, fetch_refspec=None,
                 encoding='utf-8', name=None, pollAtLaunch=False,
                 buildPushesWithNoCommits=False, only_tags=False):

        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval

        if name is None:
            name = repourl

        base.PollingChangeSource.__init__(self, name=name,
                                          pollInterval=pollInterval,
                                          pollAtLaunch=pollAtLaunch)

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
            category) else ascii2unicode(category)
        self.project = ascii2unicode(project)
        self.changeCount = 0
        self.lastRev = {}

        if fetch_refspec is not None:
            config.error("GitPoller: fetch_refspec is no longer supported. "
                         "Instead, only the given branches are downloaded.")

        if self.workdir is None:
            self.workdir = 'gitpoller-work'

    def activate(self):
        # make our workdir absolute, relative to the master's basedir
        if not os.path.isabs(self.workdir):
            self.workdir = os.path.join(self.master.basedir, self.workdir)
            log.msg("gitpoller: using workdir '%s'" % self.workdir)

        d = self.getState('lastRev', {})

        @d.addCallback
        def setLastRev(lastRev):
            self.lastRev = lastRev
        d.addCallback(lambda _: base.PollingChangeSource.activate(self))
        d.addErrback(log.err, 'while initializing GitPoller repository')

        return d

    def describe(self):
        str = ('GitPoller watching the remote git repository ' +
               bytes2NativeString(self.repourl, self.encoding))

        if self.branches:
            if self.branches is True:
                str += ', branches: ALL'
            elif not callable(self.branches):
                str += ', branches: ' + ', '.join(self.branches)

        if not self.master:
            str += " [STOPPED - check log]"

        return str

    def _getBranches(self):
        d = self._dovccmd('ls-remote', [self.repourl])

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
        return "refs/buildbot/%s/%s" % (urlquote(self.repourl, ''),
                                        self._removeHeads(branch))

    @defer.inlineCallbacks
    def poll(self):
        try:
            yield self._dovccmd('init', ['--bare', self.workdir])
        except GitError as e:
            log.msg(e.args[0])
            return

        branches = self.branches
        if branches is True or callable(branches):
            branches = yield self._getBranches()
            if callable(self.branches):
                branches = [b for b in branches if self.branches(b)]
            else:
                branches = [b for b in branches if self._headsFilter(b)]

        refspecs = [
            '+%s:%s' % (self._removeHeads(branch), self._trackerBranch(branch))
            for branch in branches
        ]

        try:
            yield self._dovccmd('fetch', [self.repourl] + refspecs,
                                path=self.workdir)
        except GitError as e:
            log.msg(e.args[0])
            return

        revs = {}
        log.msg('gitpoller: processing changes from "%s"' % (self.repourl,))
        for branch in branches:
            try:
                rev = yield self._dovccmd(
                    'rev-parse', [self._trackerBranch(branch)], path=self.workdir)
                revs[branch] = bytes2NativeString(rev, self.encoding)
                yield self._process_changes(revs[branch], branch)
            except Exception:
                log.err(_why="trying to poll branch %s of %s"
                        % (branch, self.repourl))

        self.lastRev.update(revs)
        yield self.setState('lastRev', self.lastRev)

    def _decode(self, git_output):
        return bytes2unicode(git_output, self.encoding)

    def _get_commit_comments(self, rev):
        args = ['--no-walk', r'--format=%s%n%b', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)
        d.addCallback(self._decode)
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
                        'gitpoller: caught exception converting output \'%s\' to timestamp' % git_output)
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
                file = bytes2unicode(match.groups()[0], 'unicode_escape')
            return self._decode(file)

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
            git_output = self._decode(git_output)
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
        if newRev in itervalues(self.lastRev):
            if self.buildPushesWithNoCommits:
                existingRev = self.lastRev.get(branch)
                if existingRev is None:
                    # This branch was completely unknown, rebuild
                    log.msg('gitpoller: rebuilding %s for new branch "%s"' %
                            (newRev, branch))
                    rebuild = True
                elif existingRev != newRev:
                    # This branch is known, but it now points to a different
                    # commit than last time we saw it, rebuild.
                    log.msg('gitpoller: rebuilding %s for updated branch "%s"' %
                            (newRev, branch))
                    rebuild = True

        # get the change list
        revListArgs = ([b'--format=%H', r'%s' % newRev] +
                       [b'^' + unicode2bytes(rev, 'ascii', 'ignore')
                        for rev in sorted(itervalues(self.lastRev))] +
                       [b'--'])
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
            log.msg('gitpoller: processing %d changes: %s from "%s" branch "%s"'
                    % (self.changeCount, revList, self.repourl, branch))

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
                author=author, revision=ascii2unicode(rev), files=files,
                comments=comments, when_timestamp=timestamp,
                branch=ascii2unicode(self._removeHeads(branch)),
                project=self.project, repository=ascii2unicode(self.repourl),
                category=self.category, src=u'git')

    def _dovccmd(self, command, args, path=None):
        def encodeArg(arg):
            if isinstance(arg, list):
                return [encodeArg(a) for a in arg]
            elif isinstance(arg, text_type):
                return arg.encode("ascii")
            return arg
        d = utils.getProcessOutputAndValue(encodeArg(self.gitbin),
                                           encodeArg([command] + args),
                                           path=encodeArg(path), env=os.environ)

        def _convert_nonzero_to_failure(res,
                                        command,
                                        args,
                                        path):
            "utility to handle the result of getProcessOutputAndValue"
            (stdout, stderr, code) = res
            stdout = bytes2NativeString(stdout, self.encoding)
            stderr = bytes2NativeString(stderr, self.encoding)
            args = bytes2NativeString(args, self.encoding)
            if code != 0:
                if code == 128:
                    raise GitError('command %s %s in %s on repourl %s failed with exit code %d: %s'
                                   % (command, args, path, self.repourl, code, stderr))
                raise EnvironmentError('command %s %s in %s on repourl %s failed with exit code %d: %s'
                                       % (command, args, path, self.repourl, code, stderr))
            return stdout.strip()
        d.addCallback(_convert_nonzero_to_failure,
                      command,
                      args,
                      path)
        return d
