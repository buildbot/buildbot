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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import fakemaster


class DBConnector_Basic(unittest.TestCase):
    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    @defer.inlineCallbacks
    def setUp(self):
        self.master = yield fakemaster.make_master(
            self, wantRealReactor=True, wantDb=True, auto_upgrade=False, check_version=False
        )

    @defer.inlineCallbacks
    def test_is_current_empty(self):
        res = yield self.master.db.model.is_current()
        self.assertFalse(res)

    @defer.inlineCallbacks
    def test_is_current_full(self):
        yield self.master.db.model.upgrade()
        res = yield self.master.db.model.is_current()
        self.assertTrue(res)
