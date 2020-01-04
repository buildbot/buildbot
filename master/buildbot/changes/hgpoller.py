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
import time

from twisted.internet import defer
from twisted.internet import utils
from twisted.python import log

from buildbot import config
from buildbot.changes import base
from buildbot.util import bytes2unicode
from buildbot.util import deferredLocked
from buildbot.util.state import StateMixin


class HgPoller(base.PollingChangeSource, StateMixin):

    """This source will poll a remote hg repo for changes and submit
    them to the change master."""

    compare_attrs = ("repourl", "branch", "branches", "bookmarks", "workdir",
                     "pollInterval", "hgpoller", "usetimestamps",
                     "category", "project", "pollAtLaunch")

    db_class_name = 'HgPoller'

    def __init__(self, repourl, branch=None, branches=None, bookmarks=None,
                 workdir=None, pollInterval=10 * 60,
                 hgbin='hg', usetimestamps=True,
                 category=None, project='', pollinterval=-2,
                 encoding='utf-8', name=None, pollAtLaunch=False,
                 revlink=lambda branch, revision: ('')
                 ):

        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval

        self.repourl = repourl

        if branch and branches:
            config.error("HgPoller: can't specify both branch and branches")
        elif branch:
            self.branches = [branch]
        else:
            self.branches = branches or []

        self.bookmarks = bookmarks or []

        if name is None:
            name = repourl
            if self.bookmarks:
                name += "_" + "_".join(self.bookmarks)
            if self.branches:
                name += "_" + "_".join(self.branches)

        if not self.branches and not self.bookmarks:
            self.branches = ['default']

        if not callable(revlink):
            config.error(
                "You need to provide a valid callable for revlink")

        super().__init__(name=name, pollInterval=pollInterval, pollAtLaunch=pollAtLaunch)
        self.encoding = encoding
        self.lastChange = time.time()
        self.lastPoll = time.time()
        self.hgbin = hgbin
        self.workdir = workdir
        self.usetimestamps = usetimestamps
        self.category = category if callable(
            category) else bytes2unicode(category)
        self.project = project
        self.initLock = defer.DeferredLock()
        self.lastRev = {}
        self.revlink_callable = revlink

        if self.workdir is None:
            config.error("workdir is mandatory for now in HgPoller")

    @defer.inlineCallbacks
    def activate(self):
        self.lastRev = yield self.getState('lastRev', {})
        super().activate()

    def describe(self):
        status = ""
        if not self.master:
            status = "[STOPPED - check log]"
        return ("HgPoller watching the remote Mercurial repository %r, "
                "branches: %r, in workdir %r %s") % (self.repourl,
                                                     ', '.join(self.branches),
                                                     self.workdir, status)

    @deferredLocked('initLock')
    def poll(self):
        d = self._getChanges()
        d.addCallback(self._processChanges)
        d.addErrback(self._processChangesFailure)
        return d

    def _absWorkdir(self):
        workdir = self.workdir
        if os.path.isabs(workdir):
            return workdir
        return os.path.join(self.master.basedir, workdir)

    def _getRevDetails(self, rev):
        """Return a deferred for (date, author, files, comments) of given rev.

        Deferred will be in error if rev is unknown.
        """
        args = ['log', '-r', rev, os.linesep.join((
            '--template={date|hgdate}',
            '{author}',
            "{files % '{file}" + os.pathsep + "'}",
            '{desc|strip}'))]
        # Mercurial fails with status 255 if rev is unknown
        d = utils.getProcessOutput(self.hgbin, args, path=self._absWorkdir(),
                                   env=os.environ, errortoo=False)

        @d.addCallback
        def process(output):
            # all file names are on one line
            output = output.decode(self.encoding, "replace")
            date, author, files, comments = output.split(
                os.linesep, 3)

            if not self.usetimestamps:
                stamp = None
            else:
                try:
                    stamp = float(date.split()[0])
                except Exception:
                    log.msg('hgpoller: caught exception converting output %r '
                            'to timestamp' % date)
                    raise
            return stamp, author.strip(), files.split(os.pathsep)[:-1], comments.strip()
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
        d.addCallback(lambda _: log.msg(
            "hgpoller: finished initializing working dir %r" % self.workdir))
        return d

    def _getChanges(self):
        self.lastPoll = time.time()

        d = self._initRepository()
        d.addCallback(lambda _: log.msg(
            "hgpoller: polling hg repo at %s" % self.repourl))

        # get a deferred object that performs the fetch
        args = ['pull']
        for name in self.branches:
            args += ['-b', name]
        for name in self.bookmarks:
            args += ['-B', name]
        args += [self.repourl]

        # This command always produces data on stderr, but we actually do not
        # care about the stderr or stdout from this command.
        # We set errortoo=True to avoid an errback from the deferred.
        # The callback which will be added to this
        # deferred will not use the response.
        d.addCallback(lambda _: utils.getProcessOutput(
            self.hgbin, args, path=self._absWorkdir(),
            env=os.environ, errortoo=True))

        return d

    def _getCurrentRev(self, branch='default'):
        """Return a deferred for current numeric rev in state db.

        If never has been set, current rev is None.
        """
        return self.lastRev.get(branch, None)

    def _setCurrentRev(self, rev, branch='default'):
        """Return a deferred to set current revision in persistent state."""
        self.lastRev[branch] = str(rev)
        return self.setState('lastRev', self.lastRev)

    def _getHead(self, branch):
        """Return a deferred for branch head revision or None.

        We'll get an error if there is no head for this branch, which is
        probably a good thing, since it's probably a misspelling
        (if really buildbotting a branch that does not have any changeset
        yet, one shouldn't be surprised to get errors)
        """
        d = utils.getProcessOutput(self.hgbin,
                                   ['heads', '-r', branch,
                                       '--template={rev}' + os.linesep],
                                   path=self._absWorkdir(), env=os.environ, errortoo=False)

        @d.addErrback
        def no_head_err(exc):
            log.err("hgpoller: could not find revision %r in repository %r" % (
                branch, self.repourl))

        @d.addCallback
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
            return heads.strip().decode(self.encoding)
        return d

    @defer.inlineCallbacks
    def _processChanges(self, unused_output):
        """Send info about pulled changes to the master and record current.

        HgPoller does the recording by moving the working dir to the head
        of the branch.
        We don't update the tree (unnecessary treatment and waste of space)
        instead, we simply store the current rev number in a file.
        Recall that hg rev numbers are local and incremental.
        """
        for branch in self.branches + self.bookmarks:
            rev = yield self._getHead(branch)
            if rev is None:
                # Nothing pulled?
                continue
            yield self._processBranchChanges(rev, branch)

    @defer.inlineCallbacks
    def _getRevNodeList(self, revset):
        revListArgs = ['log', '-r', revset, r'--template={rev}:{node}\n']
        results = yield utils.getProcessOutput(self.hgbin, revListArgs,
                                               path=self._absWorkdir(), env=os.environ, errortoo=False)
        results = results.decode(self.encoding)

        revNodeList = [rn.split(':', 1) for rn in results.strip().split()]
        defer.returnValue(revNodeList)

    @defer.inlineCallbacks
    def _processBranchChanges(self, new_rev, branch):
        prev_rev = yield self._getCurrentRev(branch)
        if new_rev == prev_rev:
            # Nothing new.
            return
        if prev_rev is None:
            # First time monitoring; start at the top.
            yield self._setCurrentRev(new_rev, branch)
            return

        # two passes for hg log makes parsing simpler (comments is multi-lines)
        revNodeList = yield self._getRevNodeList('{}::{}'.format(prev_rev, new_rev))

        # revsets are inclusive. Strip the already-known "current" changeset.
        if not revNodeList:
            # empty revNodeList probably means the branch has changed head (strip of force push?)
            # in that case, we should still produce a change for that new rev (but we can't know how many parents were pushed)
            revNodeList = yield self._getRevNodeList(new_rev)
        else:
            del revNodeList[0]

        log.msg('hgpoller: processing %d changes in branch %r: %r in %r'
                % (len(revNodeList), branch, revNodeList, self._absWorkdir()))
        for rev, node in revNodeList:
            timestamp, author, files, comments = yield self._getRevDetails(
                node)
            yield self.master.data.updates.addChange(
                author=author,
                committer=None,
                revision=str(node),
                revlink=self.revlink_callable(branch, str(node)),
                files=files,
                comments=comments,
                when_timestamp=int(timestamp) if timestamp else None,
                branch=bytes2unicode(branch),
                category=bytes2unicode(self.category),
                project=bytes2unicode(self.project),
                repository=bytes2unicode(self.repourl),
                src='hg')
            # writing after addChange so that a rev is never missed,
            # but at once to avoid impact from later errors
            yield self._setCurrentRev(new_rev, branch)

    def _processChangesFailure(self, f):
        log.msg('hgpoller: repo poll failed')
        log.err(f)
        # eat the failure to continue along the deferred chain - we still want
        # to catch up
        return None

    def _convertNonZeroToFailure(self, res):
        "utility method to handle the result of getProcessOutputAndValue"
        (stdout, stderr, code) = res
        if code != 0:
            raise EnvironmentError(
                'command failed with exit code %d: %s' % (code, stderr))
        return (stdout, stderr, code)

    def _stopOnFailure(self, f):
        "utility method to stop the service when a failure occurs"
        if self.running:
            d = defer.maybeDeferred(self.stopService)
            d.addErrback(log.err, 'while stopping broken HgPoller service')
        return f
