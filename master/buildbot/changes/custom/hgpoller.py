
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

import time
import os
import sys
from twisted.python import log
from twisted.internet import defer, utils

from buildbot import config
from buildbot.util import deferredLocked
from buildbot.changes import base
from buildbot.util import epoch2datetime
from buildbot.util.state import StateMixin
import re

class HgPoller(base.PollingChangeSource, StateMixin):
    """This source will poll a remote hg repo for changes and submit
    them to the change master."""

    compare_attrs = ["repourl", 'branches', "workdir",
                     "pollInterval", "hgpoller", "usetimestamps",
                     "category", "project"]

    db_class_name = 'HgPoller'

    def __init__(self, repourl, branches={},
                 workdir=None, pollInterval=10*60,
                 hgbin='hg', usetimestamps=True,
                 category=None, project='',
                 encoding='utf-8', commits_checked=10000):

        self.repourl = repourl
        self.branches = branches
        self.lastRev = {}
        self.currentRev = {}
        base.PollingChangeSource.__init__(
            self, name=repourl, pollInterval=pollInterval)
        self.encoding = encoding
        self.lastChange = time.time()
        self.lastPoll = time.time()
        self.hgbin = hgbin
        self.workdir = workdir
        self.usetimestamps = usetimestamps
        self.category = category
        self.project = project
        self.commitInfo  = {}
        self.initLock = defer.DeferredLock()
        self.commits_checked = commits_checked

        if self.workdir == None:
            config.error("workdir is mandatory for now in HgPoller")

        if len(self.branches) == 0:
            config.error("HgPoller: missing branches configuration, for example branches={'include': [r'.*'], 'exclude': [r'default']}")

    def describe(self):
        status = ""
        if not self.master:
            status = "[STOPPED - check log]"
        return ("HgPoller watching the remote Mercurial repository %r "
                "in workdir %r %s") % (self.repourl, self.workdir, status)

    def startService(self):
        d = self.getState('lastRev', {})
        def setLastRev(lastRev):
            self.lastRev = lastRev
        d.addCallback(setLastRev)

        d.addCallback(lambda _:
        base.PollingChangeSource.startService(self))
        d.addErrback(log.err, 'while initializing HgPoller repository')

        return d

    @deferredLocked('initLock')
    def poll(self):
        d = self._getRepositoryChanges()
        d.addCallback(self._processBranches)
        d.addCallback(self._processChangesAllBranches)
        d.addErrback(self._processChangesFailure)
        return d

    def _absWorkdir(self):
        workdir = self.workdir
        if os.path.isabs(workdir):
            return workdir
        return os.path.join(self.master.basedir, workdir)

    def _getRevDetails(self, rev):
        """Return a deferred for (date, author, comments) of given rev.

        Deferred will be in error if rev is unknown.
        """
        args = ['log', '-r', rev, r'--template={date|hgdate}\n{author}\n{desc|strip}']
        # Mercurial fails with status 255 if rev is unknown
        d = utils.getProcessOutput(self.hgbin, args, path=self._absWorkdir(),
                                   env=os.environ, errortoo=False )
        def process(output):
            # fortunately, Mercurial issues all filenames one one line
            if sys.platform != 'win32':
                linesep = os.linesep
            else:
                linesep = '\n'
            date, author, comments = output.decode(self.encoding, "replace").split(
                linesep, 2)

            if not self.usetimestamps:
                stamp = None
            else:
                try:
                    stamp = float(date.split()[0])
                except:
                    log.msg('hgpoller: caught exception converting output %r '
                            'to timestamp' % date)
                    raise
            return stamp, author.strip(), comments.strip()

        d.addCallback(process)
        return d

    def _isRepositoryReady(self):
        """Easy to patch in tests."""
        return os.path.exists(os.path.join(self._absWorkdir(), '.hg'))

    def _initRepository(self):
        """Have mercurial init the workdir as a repository (hg init) if needed.

        hg init will also create all needed intermediate directories.
        """
        if self._isRepositoryReady():
            return defer.succeed(None)
        log.msg('hgpoller: initializing working dir from %s' % self.repourl)
        d = utils.getProcessOutputAndValue(self.hgbin,
                                           ['init', self._absWorkdir()],
                                           env=os.environ)
        d.addCallback(self._convertNonZeroToFailure)
        d.addErrback(self._stopOnFailure)
        d.addCallback(lambda _ : log.msg(
            "hgpoller: finished initializing working dir %r" % self.workdir))
        return d

    def _getRepositoryChanges(self):
        self.lastPoll = time.time()

        d = self._initRepository()
        d.addCallback(lambda _ : log.msg(
            "hgpoller: polling hg repo at %s" % self.repourl))

        # get a deferred object that performs the fetch
        args = ['pull', self.repourl]

        # This command always produces data on stderr, but we actually do not
        # care about the stderr or stdout from this command.
        # We set errortoo=True to avoid an errback from the deferred.
        # The callback which will be added to this
        # deferred will not use the response.
        d.addCallback(lambda _: utils.getProcessOutput(
            self.hgbin, args, path=self._absWorkdir(),
            env=os.environ, errortoo=True))

        return d

    @defer.inlineCallbacks
    def _processBranches(self, output):

        search = 'last(:tip,{0}):&head()&!closed()+bookmark()'.format(self.commits_checked)
        args = ['log', '-r', search, '--template', '{branch} {bookmarks} {rev}:{node|short}\n']

        results = yield utils.getProcessOutput(self.hgbin, args,
                                               path=self._absWorkdir(), env=os.environ, errortoo=False )

        branchlist = [branch for branch in results.strip().split('\n')]

        self.currentRev  = {}
        for branch in branchlist:
            list = branch.strip().split()
            if len(list) > 0:
                if self.trackingBranch(list[0]):
                    if len(list) == 2:
                        self.currentRev[list[0]] = list[1]
                    elif len(list) == 3:
                        self.currentRev[list[0]] = list[2]
                        self.currentRev[list[1]] = list[2]
            else:
                log.msg("Error while polling: {0}".format(self.repourl))

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
    def _processChangesAllBranches(self, output):
        updated = False

        # in case the branch is not longer visible
        for branch,rev in self.currentRev.iteritems():
            current = None
            if branch in self.lastRev.keys():
                current = self.lastRev[branch]

            if rev != current:
                updated = True
                yield self._processChangesByBranch(branch=branch,current=current)
                self.lastRev[branch] = rev

        if updated:
            # if branches were deleted we need to replace with currentRev
            self.lastRev = self.currentRev
            yield self.setState('lastRev', self.lastRev)

    @defer.inlineCallbacks
    def _processChangesByBranch(self, branch, current):

        # hg log on a range of revisions is never empty
        # also, if a numeric revision does not exist, a node may match.
        # Therefore, we have to check explicitely that branch head > current.
        head = yield self._getHead(branch)

        # skipped get changes on a close branch
        if head is None:
            return

        if current is None:
            # we could have used current = -1 convention as well (as hg does)
            revrange = '%s:%s' % (head, head)
        else:
            revrange = '%d:%s' % (int(current.split(":")[0]) + 1, head)

        # two passes for hg log makes parsing simpler (comments is multi-lines)
        revListArgs = ['log', '-b', branch, '-r', revrange,
                       r'--template={rev}:{node}\n']
        results = yield utils.getProcessOutput(self.hgbin, revListArgs,
                                               path=self._absWorkdir(), env=os.environ, errortoo=False )

        revNodeList = [rn.split(':', 1) for rn in results.strip().split()]

        log.msg('hgpoller: processing %d changes: %r in %r'
                % (len(revNodeList), revNodeList, self._absWorkdir()))
        for rev, node in revNodeList:
            timestamp, author, comments = yield self._getRevDetails(
                node)
            yield self.master.addChange(
                author=author,
                revision=node,
                files=None,
                comments=comments,
                when_timestamp=epoch2datetime(timestamp),
                branch=branch,
                category=self.category,
                project=self.project,
                repository=self.repourl,
                src='hg')

    def _getHead(self, branch):
        """Return a deferred for branch head revision or None.

        We'll get an error if there is no head for this branch, which is
        proabably a good thing, since it's probably a mispelling
        (if really buildbotting a branch that does not have any changeset
        yet, one shouldn't be surprised to get errors)
        """
        d = utils.getProcessOutput(self.hgbin,
                                   ['heads', branch, '--template={node}' + os.linesep],
                                   path=self._absWorkdir(), env=os.environ, errortoo=False)

        def no_head_err(exc):
            log.err("hgpoller: could not find branch %r in repository %r" % (
                branch, self.repourl))
        d.addErrback(no_head_err)

        def results(heads):
            if not heads:
                return

            if len(heads.split()) > 1:
                log.err(("hgpoller: caught several heads in branch %r "
                         "from repository %r. Staying at previous revision"
                         "You should wait until the situation is normal again "
                         "due to a merge or directly strip if remote repo "
                         "gets stripped later.") % (branch, self.repourl))
                return

            # in case of whole reconstruction, are we sure that we'll get the
            # same node -> rev assignations ?
            return heads.strip()

        d.addCallback(results)
        return d

    def _processChangesFailure(self, f):
        log.msg('hgpoller: repo poll failed')
        log.err(f)
        # eat the failure to continue along the defered chain - we still want to catch up
        return None

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
            d.addErrback(log.err, 'while stopping broken HgPoller service')
        return f
