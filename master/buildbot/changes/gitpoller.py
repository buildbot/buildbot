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
import urllib
from twisted.python import log
from twisted.internet import defer, utils

from buildbot.changes import base
from buildbot.util import ascii2unicode
from buildbot.util.state import StateMixin
from buildbot import config

class GitPoller(base.PollingChangeSource, StateMixin):
    """This source will poll a remote git repo for changes and submit
    them to the change master."""
    
    compare_attrs = ("repourl", "branches", "workdir",
                     "pollInterval", "gitbin", "usetimestamps",
                     "category", "project")

    def __init__(self, repourl, branches=None, branch=None,
                 workdir=None, pollInterval=10*60, 
                 gitbin='git', usetimestamps=True,
                 category=None, project=None,
                 pollinterval=-2, fetch_refspec=None,
                 encoding='utf-8', name=None):

        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval

        if name is None:
            name = repourl

        base.PollingChangeSource.__init__(self, name=name,
                pollInterval=pollInterval)

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
        self.category = ascii2unicode(category)
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
        def setLastRev(lastRev):
            self.lastRev = lastRev
        d.addCallback(setLastRev)

        d.addErrback(log.err, 'while initializing GitPoller repository')

        return d

    def describe(self):
        status = ""
        if not self.master:
            status = "[STOPPED - check log]"
        str = ('GitPoller watching the remote git repository %s, branches: %s %s'
                % (self.repourl, ', '.join(self.branches), status))
        return str

    @defer.inlineCallbacks
    def poll(self):
        yield self._dovccmd('init', ['--bare', self.workdir])

        refspecs = [
                '+%s:%s'% (branch, self._localBranch(branch))
                for branch in self.branches
                ]
        yield self._dovccmd('fetch',
                [self.repourl] + refspecs, path=self.workdir)

        revs = {}
        for branch in self.branches:
            try:
                revs[branch] = rev = yield self._dovccmd('rev-parse',
                        [self._localBranch(branch)], path=self.workdir)
                yield self._process_changes(rev, branch)
            except:
                log.err(_why="trying to poll branch %s of %s"
                                % (branch, self.repourl))

        self.lastRev.update(revs)
        yield self.setState('lastRev', self.lastRev)

    def _get_commit_comments(self, rev):
        args = ['--no-walk', r'--format=%s%n%b', rev, '--']
        d = self._dovccmd('log',  args, path=self.workdir)
        def process(git_output):
            git_output = git_output.decode(self.encoding)
            if len(git_output) == 0:
                raise EnvironmentError('could not get commit comment for rev')
            return git_output
        d.addCallback(process)
        return d

    def _get_commit_timestamp(self, rev):
        # unix timestamp
        args = ['--no-walk', r'--format=%ct', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)
        def process(git_output):
            if self.usetimestamps:
                try:
                    stamp = int(git_output)
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
        def process(git_output):
            fileList = git_output.split()

            # filenames in git are presumably just like POSIX filenames -
            # encoding-free bytestrings.  In most cases, they'll UTF-8 and
            # mostly ASCII, so that's a safe assumption here.
            return [ f.decode('utf-8', 'replace') for f in fileList ]
        d.addCallback(process)
        return d
            
    def _get_commit_author(self, rev):
        args = ['--no-walk', r'--format=%aN <%aE>', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)
        def process(git_output):
            git_output = git_output.decode(self.encoding)
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
                % (self.changeCount, revList, self.repourl) )

        for rev in revList:
            dl = defer.DeferredList([
                self._get_commit_timestamp(rev),
                self._get_commit_author(rev),
                self._get_commit_files(rev),
                self._get_commit_comments(rev),
            ], consumeErrors=True)

            results = yield dl

            # check for failures
            failures = [ r[1] for r in results if not r[0] ]
            if failures:
                # just fail on the first error; they're probably all related!
                raise failures[0]

            timestamp, author, files, comments = [ r[1] for r in results ]
            yield self.master.data.updates.addChange(
                   author=author,
                   revision=unicode(rev),
                   files=files,
                   comments=comments,
                   when_timestamp=timestamp,
                   branch=ascii2unicode(branch),
                   category=self.category,
                   project=self.project,
                   repository=ascii2unicode(self.repourl),
                   src=u'git')

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

    def _localBranch(self, branch):
        return "refs/buildbot/%s/%s" % (urllib.quote(self.repourl, ''), branch)
