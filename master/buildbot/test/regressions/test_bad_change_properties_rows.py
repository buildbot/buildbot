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

from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


class TestBadRows(TestReactorMixin, unittest.TestCase):
    # See bug #1952 for details.  This checks that users who used a development
    # version between 0.8.3 and 0.8.4 get reasonable behavior even though some
    # rows in the change_properties database do not contain a proper [value,
    # source] tuple.

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)

    @defer.inlineCallbacks
    def test_bogus_row_no_source(self):
        yield self.master.db.insert_test_data([
            fakedb.SourceStamp(id=10),
            fakedb.ChangeProperty(changeid=13, property_name='devel', property_value='"no source"'),
            fakedb.Change(changeid=13, sourcestampid=10),
        ])

        c = yield self.master.db.changes.getChange(13)

        self.assertEqual(c.properties, {"devel": ('no source', 'Change')})

    @defer.inlineCallbacks
    def test_bogus_row_jsoned_list(self):
        yield self.master.db.insert_test_data([
            fakedb.SourceStamp(id=10),
            fakedb.ChangeProperty(changeid=13, property_name='devel', property_value='[1, 2]'),
            fakedb.Change(changeid=13, sourcestampid=10),
        ])

        c = yield self.master.db.changes.getChange(13)

        self.assertEqual(c.properties, {"devel": ([1, 2], 'Change')})
