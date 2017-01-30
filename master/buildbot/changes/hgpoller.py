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
from future.utils import text_type

import os
import time

from twisted.internet import defer
from twisted.internet import utils
from twisted.python import log

from buildbot import config
from buildbot.changes import base
from buildbot.util import ascii2unicode
from buildbot.util import bytes2unicode
from buildbot.util import deferredLocked


class HgPoller(base.PollingChangeSource):

    """This source will poll a remote hg repo for changes and submit
    them to the change master."""

    compare_attrs = ("repourl", "branch", "workdir",
                     "pollInterval", "hgpoller", "usetimestamps",
                     "category", "project", "pollAtLaunch")

    db_class_name = 'HgPoller'

    def __init__(self, repourl, branch='default',
                 workdir=None, pollInterval=10 * 60,
                 hgbin='hg', usetimestamps=True,
                 category=None, project='', pollinterval=-2,
                 encoding='utf-8', name=None, pollAtLaunch=False):

        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval

        if name is None:
            name = "%s[%s]" % (repourl, branch)

        self.repourl = repourl
        self.branch = branch
        base.PollingChangeSource.__init__(
            self, name=name, pollInterval=pollInterval, pollAtLaunch=pollAtLaunch)
        self.encoding = encoding
        self.lastChange = time.time()
        self.lastPoll = time.time()
        self.hgbin = hgbin
        self.workdir = workdir
        self.usetimestamps = usetimestamps
        self.category = category if callable(
            category) else ascii2unicode(category)
        self.project = project
        self.commitInfo = {}
        self.initLock = defer.DeferredLock()

        if self.workdir is None:
            config.error("workdir is mandatory for now in HgPoller")

    def describe(self):
        status = ""
        if not self.master:
            status = "[STOPPED - check log]"
        return ("HgPoller watching the remote Mercurial repository %r, "
                "branch: %r, in workdir %r %s") % (self.repourl, self.branch,
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
            output = bytes2unicode(output, self.encoding, "replace")
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
        args = ['pull', '-b', self.branch, self.repourl]

        # This command always produces data on stderr, but we actually do not
        # care about the stderr or stdout from this command.
        # We set errortoo=True to avoid an errback from the deferred.
        # The callback which will be added to this
        # deferred will not use the response.
        d.addCallback(lambda _: utils.getProcessOutput(
            self.hgbin, args, path=self._absWorkdir(),
            env=os.environ, errortoo=True))

        return d

    def _getStateObjectId(self):
        """Return a deferred for object id in state db.

        Being unique among pollers, workdir is used with branch as instance
        name for db.
        """
        return self.master.db.state.getObjectId(
            '#'.join((self.workdir, self.branch)), self.db_class_name)

    def _getCurrentRev(self):
        """Return a deferred for object id in state db and current numeric rev.

        If never has been set, current rev is None.
        """
        d = self._getStateObjectId()

        @d.addCallback
        def oid_cb(oid):
            d = self.master.db.state.getState(oid, 'current_rev', None)

            @d.addCallback
            def addOid(cur):
                if cur is not None:
                    return oid, int(cur)
                return oid, cur
            return d
        return d

    def _setCurrentRev(self, rev, oid=None):
        """Return a deferred to set current revision in persistent state.

        oid is self's id for state db. It can be passed to avoid a db lookup."""
        if oid is None:
            d = self._getStateObjectId()
        else:
            d = defer.succeed(oid)

        @d.addCallback
        def set_in_state(obj_id):
            return self.master.db.state.setState(obj_id, 'current_rev', rev)

        return d

    def _getHead(self):
        """Return a deferred for branch head revision or None.

        We'll get an error if there is no head for this branch, which is
        probably a good thing, since it's probably a mispelling
        (if really buildbotting a branch that does not have any changeset
        yet, one shouldn't be surprised to get errors)
        """
        d = utils.getProcessOutput(self.hgbin,
                                   ['heads', self.branch,
                                       '--template={rev}' + os.linesep],
                                   path=self._absWorkdir(), env=os.environ, errortoo=False)

        @d.addErrback
        def no_head_err(exc):
            log.err("hgpoller: could not find branch %r in repository %r" % (
                self.branch, self.repourl))

        @d.addCallback
        def results(heads):
            if not heads:
                return

            if len(heads.split()) > 1:
                log.err(("hgpoller: caught several heads in branch %r "
                         "from repository %r. Staying at previous revision"
                         "You should wait until the situation is normal again "
                         "due to a merge or directly strip if remote repo "
                         "gets stripped later.") % (self.branch, self.repourl))
                return

            # in case of whole reconstruction, are we sure that we'll get the
            # same node -> rev assignations ?
            return int(heads.strip())
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
        oid, current = yield self._getCurrentRev()
        # hg log on a range of revisions is never empty
        # also, if a numeric revision does not exist, a node may match.
        # Therefore, we have to check explicitly that branch head > current.
        head = yield self._getHead()
        if head is None:
            return
        elif current is not None and head <= current:
            return
        if current is None:
            # we could have used current = -1 convention as well (as hg does)
            revrange = '%d:%d' % (head, head)
        else:
            revrange = '%d:%s' % (current + 1, head)

        # two passes for hg log makes parsing simpler (comments is multi-lines)
        revListArgs = ['log', '-b', self.branch, '-r', revrange,
                       r'--template={rev}:{node}\n']
        results = yield utils.getProcessOutput(self.hgbin, revListArgs,
                                               path=self._absWorkdir(), env=os.environ, errortoo=False)

        revNodeList = [rn.split(':', 1) for rn in results.strip().split()]

        log.msg('hgpoller: processing %d changes: %r in %r'
                % (len(revNodeList), revNodeList, self._absWorkdir()))
        for rev, node in revNodeList:
            timestamp, author, files, comments = yield self._getRevDetails(
                node)
            yield self.master.data.updates.addChange(
                author=author,
                revision=text_type(node),
                files=files,
                comments=comments,
                when_timestamp=int(timestamp) if timestamp else None,
                branch=ascii2unicode(self.branch),
                category=ascii2unicode(self.category),
                project=ascii2unicode(self.project),
                repository=ascii2unicode(self.repourl),
                src=u'hg')
            # writing after addChange so that a rev is never missed,
            # but at once to avoid impact from later errors
            yield self._setCurrentRev(rev, oid=oid)

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
            d = defer.maybeDeferred(lambda: self.stopService())
            d.addErrback(log.err, 'while stopping broken HgPoller service')
        return f
