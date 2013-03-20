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

import mock
from twisted.trial import unittest
from buildbot.changes import bzrpoller
from buildbot.test.util import changesource
from buildbot.test.fake.fakedb import FakeDBConnector


class FakeRevision(object):
    """A fake bzr revision."""

    def __init__(self, revno, changes_from=None):
        self.revno = revno
        self._changes_from = changes_from

    def changes_from(self, rev):
        return self._changes_from.get(rev.revno)


class FakeChange(object):

    def __init__(self, added=(), removed=(), modified=(), renamed=()):
        self.added = added
        self.removed = removed
        self.modified = modified
        self.renamed = renamed


class TestBzrPoller(changesource.ChangeSourceMixin,
                    unittest.TestCase):

    def setUp(self):
        bzrpoller.BzrBranch = mock.Mock()  # FakeBzrBranch
        self.branch = mock.Mock()
        bzrpoller.BzrBranch.open_containing = mock.Mock(
            return_value=[self.branch])
        self.branch.get_rev_id.side_effect = lambda rev: 'revid-%d' % rev

        d = self.setUpChangeSource()
        self.remote_repo = 'sftp://example.com/foo/baz/trunk'
        self.repo_ready = True

        def _isRepositoryReady():
            return self.repo_ready

        def create_poller(_):
            self.poller = bzrpoller.BzrPoller(self.remote_repo,
                                              branch_name='branch name')
            self.poller.master = self.master
            self.poller._isRepositoryReady = _isRepositoryReady

        def create_db(_):
            db = self.master.db = FakeDBConnector(self)
            return db.setup()

        d.addCallback(create_poller)
        d.addCallback(create_db)
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def test_describe(self):
        self.assertSubstring("BzrPoller", self.poller.describe())

    def test_poll_initial(self):
        self.repo_ready = False
        self.branch.revno.return_value = 123
        rev = self.branch.repository.get_revision.return_value
        rev.get_apparent_authors.return_value = [
            'Bob Test <bobtest@example.org>']
        rev.message = 'This is revision 123'
        revisions = {
            'revid-123': FakeRevision(123, changes_from={
                122: FakeChange(added=[('a/f1', '', 'file')],
                                removed=[('r/f2', '', 'file')],
                                modified=[('f3', '', 'file')])}),
            'revid-122': FakeRevision(122)}
        tree = self.branch.repository.revision_tree
        tree.side_effect = lambda revid: revisions[revid]

        # do the poll
        d = self.poller.poll()

        # check the results
        def check_changes(_):
            self.assertEqual(len(self.changes_added), 1)

            change = self.changes_added[0]
            self.assertEqual(change['revision'], 123)
            self.assertEqual(change['author'],
                             'Bob Test <bobtest@example.org>')
            self.assertEqual(change['files'], ['a/f1 file ADDED',
                                               'r/f2 file REMOVED',
                                               'f3 file MODIFIED'])
            self.assertEqual(change['src'], 'bzr')
            self.assertEqual(change['branch'], 'branch name')
            self.assertEqual(change['comments'], 'This is revision 123')
#           TODO there's currently no timestamp in emitted bzr changes
#            self.assertEqual(change['when_timestamp'],
#                             epoch2datetime(1273258100)),

        d.addCallback(check_changes)
        d.addCallback(self.check_current_rev(123))
        return d

    def check_current_rev(self, wished):
        def check_on_rev(_):
            d = self.poller._getStateCurrentRev()
            d.addCallback(lambda oid_rev: self.assertEqual(oid_rev[1], wished))
        return check_on_rev
