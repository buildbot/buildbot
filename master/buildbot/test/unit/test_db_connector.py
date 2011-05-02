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
        d.addCallback(make_dbc)
        return d

    def tearDown(self):
        return self.tearDownRealDatabase()

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
