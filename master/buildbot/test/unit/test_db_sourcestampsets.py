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
from twisted.internet import defer
from buildbot.db import sourcestampsets
from buildbot.test.util import connector_component

class TestSourceStampSetsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=[ 'patches', 'buildsets', 'sourcestamps',
                'sourcestampsets' ])

        def finish_setup(_):
            self.db.sourcestampsets = \
                    sourcestampsets.SourceStampSetsConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # tests
    def test_addSourceStampSet_simple(self):
        d = defer.succeed(None)

        d.addCallback(lambda _ :
            self.db.sourcestampsets.addSourceStampSet())

        def check(sourcestampsetid):
            def thd(conn):
                # should see one sourcestamp row
                ssset_tbl = self.db.model.sourcestampsets
                r = conn.execute(ssset_tbl.select())
                rows = [ (row.id)
                         for row in r.fetchall() ]
                # Test if returned setid is in database
                self.assertEqual(rows,
                    [ ( sourcestampsetid) ])
                # Test if returned set id starts with
                self.assertEqual(sourcestampsetid, 1)
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d
