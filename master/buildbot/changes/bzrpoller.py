# Copyright (C) 2008-2009 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""\
bzr buildbot integration
========================

TODO #708, to update for integration into core

This file contains both bzr commit/change hooks and a bzr poller.

------------
Requirements
------------

This has been tested with buildbot 0.7.9, bzr 1.10, and Twisted 8.1.0.  It
should work in subsequent releases.

For the hook to work, Twisted must be installed in the same Python that bzr
uses.

-------------------
Contact Information
-------------------

Maintainer/author: gary.poster@canonical.com
"""


import buildbot.util
import buildbot.changes.base
import buildbot.changes.changes
from buildbot.changes.base import PollingChangeSource
try:
    import bzrlib
except ImportError:
    BZRLIB_PRESENT = False
else:
    BZRLIB_PRESENT = True
    from bzrlib.branch import Branch as BzrBranch

import twisted.cred.credentials
import twisted.internet.base
import twisted.internet.defer
import twisted.internet.reactor
import twisted.internet.selectreactor
import twisted.internet.task
import twisted.internet.threads
import twisted.python.log
import twisted.spread.pb


#############################################################################
# This is the code that the poller and the hooks share.

def generate_change(branch,
                    old_revno=None, old_revid=None,
                    new_revno=None, new_revid=None,
                    blame_merge_author=False):
    """Return a dict of information about a change to the branch.

    Dict has keys of "files", "author", "comments", and "revision", as used by
    the buildbot Change (and the PBChangeSource).

    If only the branch is given, the most recent change is returned.

    If only the new_revno is given, the comparison is expected to be between
    it and the previous revno (new_revno -1) in the branch.

    Passing old_revid and new_revid is only an optimization, included because
    bzr hooks usually provide this information.

    blame_merge_author means that the author of the merged branch is
    identified as the "author", not the person who committed the branch itself.
    This is typically used for PQM.
    """
    change = {}  # files, author, comments, revision; NOT branch (= branch.nick)
    if new_revno is None:
        new_revno = branch.revno()
    if new_revid is None:
        new_revid = branch.get_rev_id(new_revno)
    # TODO: This falls over if this is the very first revision
    if old_revno is None:
        old_revno = new_revno - 1
    if old_revid is None:
        old_revid = branch.get_rev_id(old_revno)
    repository = branch.repository
    new_rev = repository.get_revision(new_revid)
    if blame_merge_author:
        # this is a pqm commit or something like it
        change['author'] = repository.get_revision(
            new_rev.parent_ids[-1]).get_apparent_authors()[0]
    else:
        change['author'] = new_rev.get_apparent_authors()[0]
    # maybe useful to know:
    # name, email = bzrtools.config.parse_username(change['who'])
    change['comments'] = new_rev.message
    change['revision'] = new_revno
    change['when_timestamp'] = buildbot.util.epoch2datetime(new_rev.timestamp)
    files = change['files'] = []
    changes = repository.revision_tree(new_revid).changes_from(
        repository.revision_tree(old_revid))
    for (collection, name) in ((changes.added, 'ADDED'),
                               (changes.removed, 'REMOVED'),
                               (changes.modified, 'MODIFIED')):
        for info in collection:
            path = info[0]
            kind = info[2]
            files.append(' '.join([path, kind, name]))
    for info in changes.renamed:
        oldpath, newpath, id, kind, text_modified, meta_modified = info
        elements = [oldpath, kind, 'RENAMED', newpath]
        if text_modified or meta_modified:
            elements.append('MODIFIED')
        files.append(' '.join(elements))
    return change

#############################################################################
# poller

FULL = object()
SHORT = object()


class BzrPoller(PollingChangeSource, buildbot.util.ComparableMixin):

    compare_attrs = ['url']

    db_class_name = 'BzrPoller'

    def __init__(self, url, poll_interval=10*60, blame_merge_author=False,
                 branch_name=None, category=None):
        PollingChangeSource.__init__(self, pollInterval=poll_interval)
        # poll_interval is in seconds, so default poll_interval is 10
        # minutes.
        # bzr+ssh://bazaar.launchpad.net/~launchpad-pqm/launchpad/devel/
        # works, lp:~launchpad-pqm/launchpad/devel/ doesn't without help.
        if url.startswith('lp:'):
            url = 'bzr+ssh://bazaar.launchpad.net/' + url[3:]
        self.url = url
        self.loop = twisted.internet.task.LoopingCall(self.poll)
        self.blame_merge_author = blame_merge_author
        self.branch_name = branch_name
        self.category = category

        self.last_revision = None

    def startService(self):
        if not BZRLIB_PRESENT:
            # this raise has been deferred here to allow for unit testing
            # by injection of a mock
            raise ImportError('bzrlib')

        buildbot.changes.base.PollingChangeSource.startService(self)

    def stopService(self):
        twisted.python.log.msg("BzrPoller(%s) shutting down" % self.url)
        return buildbot.changes.base.PollingChangeSource.stopService(self)

    def describe(self):
        return "BzrPoller watching %s" % self.url

    def _initLastRevision(self):
        """Return a deferred to set last_revision attr from persistent state.
        """

        def set_rev(oid_rev):
            oid, rev = oid_rev
            self.last_revision = rev

        d = self._getStateCurrentRev()
        d.addCallback(set_rev)
        return d

    def _setLastRevision(self, rev, oid=None):
        """Return a deferred to set current revision in persistent state.

        oid is self's id for state db.
        It can be passed to avoid a db lookup.
        """
        if oid is None:
            d = self._getStateObjectId()
        else:
            d = defer.succeed(oid)

        def set_in_state(obj_id):
            return self.master.db.state.setState(
                obj_id, 'current_rev', rev)
        d.addCallback(set_in_state)
        return d

    def _getStateCurrentRev(self):
        """Return a deferred for object id in state db and current numeric rev.

        If never has been set, current rev is None.
        """
        d = self._getStateObjectId()

        def oid_cb(oid):
            current = self.master.db.state.getState(oid, 'current_rev', None)

            def to_int(cur):
                return oid, cur and int(cur) or None
            current.addCallback(to_int)
            return current
        d.addCallback(oid_cb)
        return d

    def _getStateObjectId(self):
        """Return a deferred for object id in state db.
        """
        if self.branch_name is FULL or self.branch_name is None:
            ourbranch = self.url
        elif self.branch_name is SHORT:
            # We are in a bit of trouble, as we cannot really know what our
            # branch is until we have polled new changes.
            # Seems we would have to wait until we polled the first time,
            # and only then do the filtering, grabbing the branch name from
            # whatever we polled.
            # For now, leave it as it was previously (compare against
            # self.url); at least now things work when specifying the
            # branch name explicitly.
            ourbranch = self.url
        else:
            ourbranch = self.branch_name

        return self.master.db.state.getObjectId(ourbranch, self.db_class_name)

    @twisted.internet.defer.inlineCallbacks
    def poll(self):
        if self.last_revision is None:
            yield self._initLastRevision()
        try:
            # On a big tree, even individual elements of the bzr commands
            # can take awhile. So we just push the bzr work off to a
            # thread.
            try:
                changes = yield twisted.internet.threads.deferToThread(
                    self.getRawChanges)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                # we'll try again next poll.  Meanwhile, let's report.
                twisted.python.log.err()
            else:
                for change in changes:
                    yield self.addChange(change)
                    self.last_revision = change['revision']
                    yield self._setLastRevision(self.last_revision)
        finally:
            pass

    def getRawChanges(self):
        branch = BzrBranch.open_containing(self.url)[0]
        if self.branch_name is FULL:
            branch_name = self.url
        elif self.branch_name is SHORT:
            branch_name = branch.nick
        else:  # presumably a string or maybe None
            branch_name = self.branch_name
        changes = []
        change = generate_change(
            branch, blame_merge_author=self.blame_merge_author)
        if (self.last_revision is None or
                change['revision'] > self.last_revision):
            change['branch'] = branch_name
            change['category'] = self.category
            changes.append(change)
            if self.last_revision is not None:
                while self.last_revision + 1 < change['revision']:
                    change = generate_change(
                        branch, new_revno=change['revision']-1,
                        blame_merge_author=self.blame_merge_author)
                    change['branch'] = branch_name
                    changes.append(change)
        changes.reverse()
        return changes

    def addChange(self, change):
        return self.master.addChange(src='bzr', **change)

##########################
# Work around Twisted bug.
# See http://twistedmatrix.com/trac/ticket/3591
# TODO GR: merged 4 years ago ; check if current minimum required version
# is more recent, and then, remove
import operator
import socket
from twisted.internet import defer
from twisted.python import failure


def _putResultInDeferred(reactor, deferred, f, args, kwargs):
    """
    Run a function and give results to a Deferred.

    replaces twisted.internet.thread equivalent
    """
    try:
        result = f(*args, **kwargs)
    except:
        f = failure.Failure()
        reactor.callFromThread(deferred.errback, f)
    else:
        reactor.callFromThread(deferred.callback, result)


def deferToThreadInReactor(reactor, f, *args, **kwargs):
    """
    Run function in thread and return result as Deferred.

    would be a proposed addition.  deferToThread could use it
    """
    d = defer.Deferred()
    reactor.callInThread(_putResultInDeferred, reactor, d, f, args, kwargs)
    return d


class ThreadedResolver(twisted.internet.base.ThreadedResolver):
    """Uses its own reactor for the threaded calls, unlike Twisted's."""

    def getHostByName(self, name, timeout=(1, 3, 11, 45)):
        if timeout:
            timeoutDelay = reduce(operator.add, timeout)
        else:
            timeoutDelay = 60
        userDeferred = defer.Deferred()
        lookupDeferred = deferToThreadInReactor(
            self.reactor, socket.gethostbyname, name)
        cancelCall = self.reactor.callLater(
            timeoutDelay, self._cleanup, name, lookupDeferred)
        self._runningQueries[lookupDeferred] = (userDeferred, cancelCall)
        lookupDeferred.addBoth(self._checkTimeout, name, lookupDeferred)
        return userDeferred
