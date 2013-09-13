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
from buildbot.util import epoch2datetime
from buildbot.util.state import StateMixin
from buildbot import config
import re

class GitPoller(base.PollingChangeSource, StateMixin):
    """This source will poll a remote git repo for changes and submit
    them to the change master."""

    compare_attrs = ["repourl", "branches", "workdir",
                     "pollInterval", "gitbin", "usetimestamps",
                     "category", "project"]

    def __init__(self, repourl, branches={},
                 workdir=None, pollInterval=10*60,
                 gitbin='git', usetimestamps=True,
                 category=None, project=None,
                 pollinterval=-2, fetch_refspec=None,
                 encoding='utf-8'):

        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval

        base.PollingChangeSource.__init__(self, name=repourl,
                                          pollInterval=pollInterval)

        if project is None: project = ''

        self.repourl = repourl
        self.branches = branches
        self.currentBranches = []
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

        if self.workdir == None:
            self.workdir = 'gitpoller-work'

        if len(self.branches) == 0:
            config.error("GitPoller:  missing branches configuration, for example branches={'include': [r'.*'], 'exclude': [r'default']}")

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
        status = ""
        if not self.master:
            status = "[STOPPED - check log]"
        str = ('GitPoller watching the remote git repository %s, branches: %s %s'
               % (self.repourl, ', '.join(self.branches), status))
        return str

    def _isRepositoryReady(self):
        return os.path.exists(os.path.join(self._absWorkdir(), '.git'))

    def _initRepository(self):
        if self._isRepositoryReady():
            return defer.succeed(None)
        log.msg('gitpoller: initializing working dir from %s' % self.repourl)
        d = utils.getProcessOutputAndValue(self.gitbin,
                                           ['clone', self.repourl, self.workdir],
                                           env=os.environ)
        d.addCallback(self._convertNonZeroToFailure)
        d.addErrback(self._stopOnFailure)
        d.addCallback(lambda _ : log.msg(
            "gitpoller: finished initializing working dir %r" % self.workdir))
        return d

    def _getRepositoryChanges(self):
        d = self._initRepository()
        d.addCallback(lambda _ : log.msg(
            "gitpoller: polling git repo at %s" % self.repourl))

        args = ['pull', '-p', '--all']

        d.addCallback(lambda _: utils.getProcessOutput(
            self.gitbin, args, path=self._absWorkdir(),
            env=os.environ, errortoo=True))

        return d

    # filter branches by regex
    def trackingBranch(self, branch):
        if 'exclude' in self.branches.keys():
            m = self.findBranchInExp(branch, self.branches['exclude'])
            if m:
                return False
        if 'include' in self.branches.keys():
            m = self.findBranchInExp(branch, self.branches['include'])
            if m:
                return True

    def findBranchInExp(self, branch, expressions):
        for regex in expressions:
            exp = re.compile(regex)
            m = exp.match(branch)
            if m:
                return True
        return False

    @defer.inlineCallbacks
    def _processBranches(self, output):
        args = ['branch', '-r']

        self.currentBranches = []

        results = yield utils.getProcessOutput(self.gitbin, args,
                                               path=self._absWorkdir(), env=os.environ, errortoo=False )

        for branch in results.strip().split('\n'):
            branch = branch.strip()
            if "origin/HEAD ->" in branch:
                branch = branch[14:len(branch)]
            branch = branch.strip()
            if self.trackingBranch(branch):
                self.currentBranches.append(branch)


    @defer.inlineCallbacks
    def _processChangesAllBranches(self, output):
        updated = False
        currentRevs  = {}
        for branch in self.currentBranches:
            current = None
            branchname = branch
            if "origin/" in branchname:
                branchname = branchname[7:len(branchname)]

            if branchname in self.lastRev.keys():
                current = self.lastRev[branchname]

            rev = yield self._processChangesByBranch(branchname, branch=branch, lastRev=current)
            currentRevs[branchname]=rev

            if current != rev:
                updated = True

        if updated:
            # if branches were deleted we need to replace with currentRev
            self.lastRev = currentRevs
            yield self.setState('lastRev', self.lastRev)

    @defer.inlineCallbacks
    def _processChangesByBranch(self,branchname, branch, lastRev):

        args = ['rev-parse', branch]
        rev = (yield utils.getProcessOutput(self.gitbin, args,
                                           path=self._absWorkdir(), env=os.environ, errortoo=False)).strip()

        if lastRev != rev:
            yield self._process_changes(branchname, lastRev, rev)

        defer.returnValue(rev)

    #@defer.inlineCallbacks
    def poll(self):
        d = self._getRepositoryChanges()
        d.addCallback(self._processBranches)
        d.addCallback(self._processChangesAllBranches)
        return d

    def _absWorkdir(self):
        workdir = self.workdir
        if os.path.isabs(workdir):
            return workdir
        return os.path.join(self.master.basedir, workdir)

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
        args = ['-m', '--name-only', '--no-walk', r'--format=%n', rev, '--']
        d = self._dovccmd('log', args, path=self.workdir)
        def process(git_output):
            fileList = git_output.split()
            return fileList
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
    def _process_changes(self,branchname, lastRev, newRev):
        # get the change list
        revListArgs = [r'--format=%H', '--ancestry-path', '%s..%s' % (lastRev, newRev), '--']

        if lastRev is None:
            revListArgs = [r'--format=%H', '%s' % newRev, '-1', '--']

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
                                        self._get_commit_comments(rev),
                                        ], consumeErrors=True)

            results = yield dl

            # check for failures
            failures = [ r[1] for r in results if not r[0] ]
            if failures:
                # just fail on the first error; they're probably all related!
                raise failures[0]

            timestamp, author, comments = [ r[1] for r in results ]
            yield self.master.addChange(
                author=author,
                revision=rev,
                files=None,
                comments=comments,
                when_timestamp=epoch2datetime(timestamp),
                branch=branchname,
                category=self.category,
                project=self.project,
                repository=self.repourl,
                src='git')

        self.lastRev[branchname] = newRev

    def _dovccmd(self, command, args, path=None):
        d = utils.getProcessOutputAndValue(self.gitbin,
                                           [command] + args, path=path, env=os.environ)
        def _convert_nonzero_to_failure(res):
            "utility to handle the result of getProcessOutputAndValue"
            (stdout, stderr, code) = res
            if code != 0:
                raise EnvironmentError('command failed with exit code %d: %s'
                                       % (code, stderr))
            return stdout.strip()
        d.addCallback(_convert_nonzero_to_failure)
        return d

    def _localBranch(self, branch):
        return "refs/buildbot/%s/%s" % (urllib.quote(self.repourl, ''), branch)


    def _convertNonZeroToFailure(self, res):
        "utility method to handle the result of getProcessOutputAndValue"
        (stdout, stderr, code) = res
        if code != 0:
            raise EnvironmentError('command failed with exit code %d: %s' % (code, stderr))
        return (stdout, stderr, code)

    def _stopOnFailure(self, f):
        "utility method to stop the service when a failure occurs"
        if self.running:
            d = defer.maybeDeferred(lambda : self.stopService())
            d.addErrback(log.err, 'while stopping broken GitPoller service')
        return f