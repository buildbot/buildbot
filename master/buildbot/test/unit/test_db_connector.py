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
import mock
from twisted.internet import defer, reactor
from twisted.trial import unittest
from buildbot.db import connector
from buildbot.test.util import db
from buildbot.test.fake import fakedb

class DBConnector(db.RealDatabaseMixin, unittest.TestCase):
    """
    Basic tests of the DBConnector class - all start with an empty DB
    """

    def setUp(self):
        d = self.setUpRealDatabase(
            table_names=['changes', 'change_properties', 'change_links',
                    'change_files', 'patches', 'sourcestamps',
                    'buildset_properties', 'buildsets' ])
        def make_dbc(_):
            self.dbc = connector.DBConnector(mock.Mock(), self.db_url,
                                        os.path.abspath('basedir'))
            self.dbc.start()
        d.addCallback(make_dbc)
        return d

    def tearDown(self):
        self.dbc.stop()
        return self.tearDownRealDatabase()

    def test_runQueryNow_simple(self):
        self.assertEqual(list(self.dbc.runQueryNow("SELECT 1")),
                         [(1,)])

    def test_runQueryNow_exception(self):
        self.assertRaises(Exception, lambda :
            self.dbc.runQueryNow("EAT * FROM cookies"))

    def test_runInterationNow_simple(self):
        def inter(cursor, *args, **kwargs):
            cursor.execute("SELECT 1")
            self.assertEqual(list(cursor.fetchall()), [(1,)])
        self.dbc.runInteractionNow(inter)

    def test_runInterationNow_args(self):
        def inter(cursor, *args, **kwargs):
            self.assertEqual((args, kwargs), ((1, 2), dict(three=4)))
            cursor.execute("SELECT 1")
        self.dbc.runInteractionNow(inter, 1, 2, three=4)

    def test_runInterationNow_exception(self):
        def inter(cursor):
            cursor.execute("GET * WHERE golden")
        self.assertRaises(Exception, lambda : 
            self.dbc.runInteractionNow(inter))

    def test_runQuery_simple(self):
        d = self.dbc.runQuery("SELECT 1")
        def cb(res):
            self.assertEqual(list(res), [(1,)])
        d.addCallback(cb)
        return d

    def test_getPropertiesFromDb(self):
        d = self.insertTestData([
                fakedb.Change(changeid=13),
                fakedb.ChangeProperty(changeid=13, property_name='foo',
                                    property_value='"my prop"'),
                fakedb.SourceStamp(id=23),
                fakedb.Buildset(id=33, sourcestampid=23),
                fakedb.BuildsetProperty(buildsetid=33,
                                    property_name='bar',
                                    property_value='["other prop", "BS"]'),
            ])
        def do_test(_):
            cprops = self.dbc.get_properties_from_db("change_properties",
                                                        "changeid", 13)
            bprops = self.dbc.get_properties_from_db("buildset_properties",
                                                        "buildsetid", 33)
            self.assertEqual(cprops.asList() + bprops.asList(),
                    [ ('foo', 'my prop', 'Change'),
                      ('bar', 'other prop', 'BS')])
        d.addCallback(do_test)
        return d

    def test_doCleanup(self):
        # patch out all of the cleanup tasks; note that we can't patch dbc.doCleanup
        # directly, since it's already been incorporated into the TimerService
        cleanups = set([])
        def pruneChanges(*args):
            cleanups.add('pruneChanges')
            return defer.succeed(None)
        self.dbc.changes.pruneChanges = pruneChanges

        self.dbc.startService()

        d = defer.Deferred()
        def check(_):
            self.assertEqual(cleanups, set(['pruneChanges']))
        d.addCallback(check)

        # shut down the service lest we leave an unclean reactor
        d.addCallback(lambda _ : self.dbc.stopService())

        # take advantage of the fact that TimerService runs immediately; otherwise, we'd need to find
        # a way to inject task.Clock into it
        reactor.callLater(0.001, d.callback, None)

        return d
