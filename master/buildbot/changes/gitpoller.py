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

import itertools
import os
import re
import urllib

from twisted.internet import defer
from twisted.internet import utils
from twisted.python import log

from buildbot import config
from buildbot.changes import base
from buildbot.util import epoch2datetime
from buildbot.util.state import StateMixin


class GitPoller(base.PollingChangeSource, StateMixin):

    """This source will poll a remote git repo for changes and submit
    them to the change master."""

    compare_attrs = ["repourl", "branches", "workdir",
                     "pollInterval", "gitbin", "usetimestamps",
                     "category", "project", "pollAtLaunch"]

    def __init__(self, repourl, branches=None, branch=None,
                 workdir=None, pollInterval=10 * 60,
                 gitbin='git', usetimestamps=True,
                 category=None, project=None,
                 pollinterval=-2, fetch_refspec=None,
                 encoding='utf-8', pollAtLaunch=False):

        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval

        base.PollingChangeSource.__init__(self, name=repourl,
                                          pollInterval=pollInterval,
                                          pollAtLaunch=pollAtLaunch)

        if project is None:
            project = ''

        if branch and branches:
            config.error("GitPoller: can't specify both branch and branches")
        elif branch:
            branches = [branch]
        elif not branches:
            branches = ['master']

        self.repourl = repourl
        self.branches = branches
        self.encoding = encoding
        self.gitbin = gitbin
        self.workdir = workdir
        self.usetimestamps = usetimestamps
        self.category = category
        self.project = project
        self.changeCount = 0
        self.lastRev = {}

        if fetch_refspec is not None:
            config.error("GitPoller: fetch_refspec is no longer supported. "
                         "Instead, only the given branches are downloaded.")

        if self.workdir is None:
            self.workdir = 'gitpoller-work'

    def startService(self):
        # make our workdir absolute, relative to the master's basedir
        if not os.path.isabs(self.workdir):
            self.workdir = os.path.join(self.master.basedir, self.workdir)
            log.msg("gitpoller: using workdir '%s'" % self.workdir)

        d = self.getState('lastRev', {})

        def setLastRev(lastRev):
            self.lastRev = lastRev
        d.addCallback(setLastRev)

        d.addCallback(lambda _:
                      base.PollingChangeSource.startService(self))
        d.addErrback(log.err, 'while initializing GitPoller repository')

        return d

    def describe(self):
        str = ('GitPoller watching the remote git repository ' +
               self.repourl)

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
                if not '\t' in row:
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
        return "refs/buildbot/%s/%s" % (urllib.quote(self.repourl, ''),
                                        self._removeHeads(branch))

    @defer.inlineCallbacks
    def poll(self):
        yield self._dovccmd('init', ['--bare', self.workdir])

        branches = self.branches
        if branches is True or callable(branches):
            branches = yield self._getBranches()
            if callable(self.branches):
                branches = filter(self.branches, branches)
            else:
                branches = filter(self._headsFilter, branches)

        refspecs = [
            '+%s:%s' % (self._removeHeads(branch), self._trackerBranch(branch))
            for branch in branches
        ]
        yield self._dovccmd('fetch',
                            [self.repourl] + refspecs, path=self.workdir)

        revs = {}
        for branch in branches:
            try:
                revs[branch] = rev = yield self._dovccmd(
                    'rev-parse', [self._trackerBranch(branch)], path=self.workdir)
                yield self._process_changes(rev, branch)
            except:
                log.err(_why="trying to poll branch %s of %s"
                        % (branch, self.repourl))

        self.lastRev.update(revs)
        yield self.setState('lastRev', self.lastRev)

    def _decode(self, git_output):
        return git_output.decode(self.encoding)

    def _get_commit_comments(self, rev):
        args = ['--no-walk', r'--format=%s%n%b', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)
        d.addCallback(self._decode)
        return d

    def _get_commit_timestamp(self, rev):
        # unix timestamp
        args = ['--no-walk', r'--format=%ct', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)

        def process(git_output):
            if self.usetimestamps:
                try:
                    stamp = float(git_output)
                except Exception, e:
                        log.msg('gitpoller: caught exception converting output \'%s\' to timestamp' % git_output)
                        raise e
                return stamp
            else:
                return None
        d.addCallback(process)
        return d

    def _get_commit_files(self, rev):
        args = ['--name-only', '--no-walk', r'--format=%n', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)

        def decode_file(file):
            # git use octal char sequences in quotes when non ASCII
            match = re.match('^"(.*)"$', file)
            if match:
                file = match.groups()[0].decode('string_escape')
            return self._decode(file)

        def process(git_output):
            fileList = [decode_file(file) for file in itertools.ifilter(lambda s: len(s), git_output.splitlines())]
            return fileList
        d.addCallback(process)
        return d

    def _get_commit_author(self, rev):
        args = ['--no-walk', r'--format=%aN <%aE>', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)

        def process(git_output):
            git_output = self._decode(git_output)
            if len(git_output) == 0:
                raise EnvironmentError('could not get commit author for rev')
            return git_output
        d.addCallback(process)
        return d

    @defer.inlineCallbacks
    def _process_changes(self, newRev, branch):
        """
        Read changes since last change.

        - Read list of commit hashes.
        - Extract details from each commit.
        - Add changes to database.
        """

        lastRev = self.lastRev.get(branch)
        self.lastRev[branch] = newRev
        if not lastRev:
            return

        # get the change list
        revListArgs = [r'--format=%H', '%s..%s' % (lastRev, newRev), '--']
        self.changeCount = 0
        results = yield self._dovccmd('log', revListArgs, path=self.workdir)

        # process oldest change first
        revList = results.split()
        revList.reverse()
        self.changeCount = len(revList)

        log.msg('gitpoller: processing %d changes: %s from "%s"'
                % (self.changeCount, revList, self.repourl))

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
                # just fail on the first error; they're probably all related!
                raise failures[0]

            timestamp, author, files, comments = [r[1] for r in results]
            yield self.master.addChange(
                author=author,
                revision=rev,
                files=files,
                comments=comments,
                when_timestamp=epoch2datetime(timestamp),
                branch=self._removeHeads(branch),
                category=self.category,
                project=self.project,
                repository=self.repourl,
                src='git')

    def _dovccmd(self, command, args, path=None):
        d = utils.getProcessOutputAndValue(self.gitbin,
                                           [command] + args, path=path, env=os.environ)

        def _convert_nonzero_to_failure(res):
            "utility to handle the result of getProcessOutputAndValue"
            (stdout, stderr, code) = res
            if code != 0:
                raise EnvironmentError('command on repourl %s failed with exit code %d: %s'
                                       % (self.repourl, code, stderr))
            return stdout.strip()
        d.addCallback(_convert_nonzero_to_failure)
        return d
