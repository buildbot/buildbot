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
from buildbot.db.connector import DBConnector
from buildbot.test.util import change_import

class TestWeirdChanges(change_import.ChangeImportMixin, unittest.TestCase):
    def setUp(self):
        self.setUpChangeImport()
        self.dbc = DBConnector(self.db_url, self.basedir)
        # note the connector isn't started, as we're testing upgrades

    def tearDown(self):
        if self.dbc:
            self.dbc.stop()
        self.tearDownChangeImport()

    def testListsAsFilenames(self):
        # sometimes the 'filenames' in a Change object are actually lists of files.  I don't
        # know how this happens, but we should be resilient to it.
        self.make_pickle(
                self.make_change(
                    who=u"Frosty the \N{SNOWMAN}".encode("utf8"),
                    files=[["foo","bar"],['bing']],
                    comments=u"Frosty the \N{SNOWMAN}".encode("utf8"),
                    branch="b1",
                    revision=12345))

        d = self.dbc.model.upgrade()
        d.addCallback(lambda _ : self.dbc.start())
        d.addCallback(lambda _ : self.dbc.getChangeByNumber(1))
        def check(c):
            self.failIf(c is None)
            self.assertEquals(sorted(c.files), sorted([u"foo", u"bar", u"bing"]))
        d.addCallback(check)
        return d
