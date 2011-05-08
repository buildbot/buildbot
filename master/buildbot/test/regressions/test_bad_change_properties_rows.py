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

from twisted.trial import unittest
from buildbot.test.util import connector_component
from buildbot.db import changes
from buildbot.test.fake import fakedb

class TestBadRows(connector_component.ConnectorComponentMixin,
                  unittest.TestCase):
    # See bug #1952 for details.  This checks that users who used a development
    # version between 0.8.3 and 0.8.4 get reasonable behavior even though some
    # rows in the change_properties database do not contain a proper [value,
    # source] tuple.
    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'change_properties',
                         'change_links', 'change_files'])
        def finish_setup(_):
            self.db.changes = changes.ChangesConnectorComponent(self.db)
        d.addCallback(finish_setup)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    def test_bogus_row_no_source(self):
        d = self.insertTestData([
            fakedb.ChangeProperty(changeid=13, property_name='devel',
                property_value='"no source"'),
            fakedb.Change(changeid=13),
        ])
        def get13(_):
            return self.db.changes.getChange(13)
        d.addCallback(get13)
        def check13(c):
            self.assertEqual(c['properties'],
                             dict(devel=('no source', 'Change')))
        d.addCallback(check13)
        return d

    def test_bogus_row_jsoned_list(self):
        d = self.insertTestData([
            fakedb.ChangeProperty(changeid=13, property_name='devel',
                property_value='[1, 2]'),
            fakedb.Change(changeid=13),
        ])
        def get13(_):
            return self.db.changes.getChange(13)
        d.addCallback(get13)
        def check13(c):
            self.assertEqual(c['properties'],
                             dict(devel=([1,2], 'Change')))
        d.addCallback(check13)
        return d

