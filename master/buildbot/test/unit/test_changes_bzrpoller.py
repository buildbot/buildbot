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
from twisted.internet import defer

from buildbot.util import epoch2datetime
from buildbot.changes import bzrpoller
from buildbot.test.util import changesource
from buildbot.test.fake.fakedb import FakeDBConnector


class MockRevision(mock.Mock):
    """A mock bzr revision.

    Besides being a mock object, it has the added capability to return the
    changelog from another revision. In bzrlib, this'd be done by the
    repository tree.

    The collapsing of retrieval of revision from current branch and
    changelog retrieval is actually implemented in prepare_revisions() below.
    """

    def __init__(self, revno, changes_from=None, **kwargs):
        mock.Mock.__init__(self, **kwargs)
        self.revno = revno
        self._changes_from = changes_from

    def _get_child_mock(self, **kw):
        """Override to avoid child mocks (attributes) being of the same class.

        This is explained by docstring in super class.
        """
        return mock.Mock(**kw)

    def get_apparent_authors(self):
        return self.authors

    def changes_from(self, rev):
        return self._changes_from.get(rev.revno)


class TestBzrPoller(changesource.ChangeSourceMixin,
                    unittest.TestCase):

    def setUp(self):
        bzrpoller.BzrBranch = mock.Mock()
        self.branch = mock.Mock()
        bzrpoller.BzrBranch.open_containing = mock.Mock(
            return_value=[self.branch])
        self.branch.get_rev_id.side_effect = lambda rev: 'revid-%d' % rev

        d = self.setUpChangeSource()
        self.remote_repo = 'sftp://example.com/foo/baz/trunk'
        self.repo_ready = True

        def create_poller(_):
            self.poller = bzrpoller.BzrPoller(self.remote_repo,
                                              branch_name='branch name')
            self.poller.master = self.master

        def create_db(_):
            db = self.master.db = FakeDBConnector(self)
            return db.setup()

        d.addCallback(create_poller)
        d.addCallback(create_db)
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def prepare_revisions(self, revisions):
        """Initialize the mock system with given revisions.

        revisions is a list or tuple, the last one being considered the
        head of the mock branch."""

        last_rev = revisions[-1].revno
        rev_dict = dict(('revid-%d' % rev.revno, rev) for rev in revisions)

        self.branch.revno.return_value = last_rev
        repository = self.branch.repository

        get_rev = rev_dict.__getitem__
        repository.get_revision.side_effect = get_rev
        repository.revision_tree.side_effect = get_rev

    def check_current_rev(self, wished):
        def check_on_rev(_):
            d = self.poller._getStateCurrentRev()
            d.addCallback(lambda oid_rev: self.assertEqual(oid_rev[1], wished))
        return check_on_rev

    def test_describe(self):
        self.assertSubstring("BzrPoller", self.poller.describe())

    def test_poll_initial(self):
        self.repo_ready = False
        self.prepare_revisions([
            MockRevision(122, message="No message"),
            MockRevision(123, message="This is revision 123",
                         authors=['Bob Test <bobtest@example.org>'],
                         timestamp=1361795401.71,
                         changes_from={
                             122: mock.Mock(added=[('a/f1', '', 'file')],
                                            removed=[('r/f2', '', 'file')],
                                            renamed=(),
                                            modified=[('f3', '', 'file')])}),
        ])

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
            self.assertEqual(change['when_timestamp'],
                             epoch2datetime(1361795401.71)),

        d.addCallback(check_changes)
        d.addCallback(self.check_current_rev(123))
        return d

    @defer.inlineCallbacks
    def test_poll(self):
        self.repo_ready = False
        self.prepare_revisions([
            MockRevision(314, message="No message", authors=['Someone'],
                         timestamp=0),
            MockRevision(315, message="No message",
                         timestamp=0, authors=['Someone'],
                         changes_from={
                             314: mock.Mock(added=(), removed=(),
                                            renamed=(), modified=())}),
            MockRevision(316, message="This is revision 123",
                         authors=['Bob Test <bobtest@example.org>'],
                         timestamp=1361795401.71,
                         changes_from={
                             315: mock.Mock(added=[('a/f1', '', 'file')],
                                            removed=[('r/f2', '', 'file')],
                                            renamed=(),
                                            modified=[('f3', '', 'file')])}),
        ])

        yield self.poller._setLastRevision(314)

        def check_changes(_):
            self.assertEqual(len(self.changes_added), 2)

        d = self.poller.poll()
        d.addCallback(check_changes)
        d.addCallback(self.check_current_rev(316))
        yield d
