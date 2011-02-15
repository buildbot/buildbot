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

class TestUnicodeChanges(change_import.ChangeImportMixin, unittest.TestCase):
    def setUp(self):
        d = self.setUpChangeImport()
        self.db = DBConnector(self.db_url, self.basedir)
        def make_dbc(_):
            self.db = DBConnector(self.db_url, self.basedir)
        d.addCallback(make_dbc)
        # note the connector isn't started, as we're testing upgrades
        return d

    def tearDown(self):
        if self.db:
            self.db.stop()
        return self.tearDownChangeImport()

    def testUnicodeChange(self):
        self.make_pickle(
                self.make_change(
                    who=u"Frosty the \N{SNOWMAN}".encode("utf8"),
                    files=["foo"],
                    comments=u"Frosty the \N{SNOWMAN}".encode("utf8"),
                    branch="b1",
                    revision=12345))

        d = self.db.model.upgrade()
        d.addCallback(lambda _ : self.db.start())
        d.addCallback(lambda _ : self.db.changes.getChangeInstance(1))
        def check(c):
            self.failIf(c is None)
            self.assertEquals(c.who, u"Frosty the \N{SNOWMAN}")
            self.assertEquals(c.comments, u"Frosty the \N{SNOWMAN}")
        d.addCallback(check)
        return d

    def testNonUnicodeChange(self):
        self.make_pickle(
                self.make_change(
                    who="\xff\xff\x00",
                    files=["foo"],
                    comments="\xff\xff\x00",
                    branch="b1",
                    revision=12345))

        d = self.db.model.upgrade()
        def eb(f):
            self.failUnless("UnicodeError" in str(f))
        def cb(r):
            self.fail("upgrade did not fail for non-unicode changes")
        d.addCallbacks(cb, eb)
        return d

    def testAsciiChange(self):
        self.make_pickle(
                self.make_change(
                    who="Frosty the Snowman",
                    files=["foo"],
                    comments="Frosty the Snowman",
                    branch="b1",
                    revision=12345))

        d = self.db.model.upgrade()
        d.addCallback(lambda _ : self.db.start())
        d.addCallback(lambda _ : self.db.changes.getChangeInstance(1))
        def check(c):
            self.failIf(c is None)
            self.assertEquals(c.who, "Frosty the Snowman")
            self.assertEquals(c.comments, "Frosty the Snowman")
        d.addCallback(check)
        return d

    def testUTF16Change(self):
        self.make_pickle(
                self.make_change(
                    who=u"Frosty the \N{SNOWMAN}".encode("utf16"),
                    files=[u"foo".encode('utf16')],
                    comments=u"Frosty the \N{SNOWMAN}".encode("utf16"),
                    branch="b1",
                    revision=12345),
                # instead of running contrib/fix_changes_pickle_encoding.py, we
                # just call the changemanager's recode_changes directly - it's
                # the function at the heart of the script anyway.
                recode_fn=lambda cm : cm.recode_changes('utf16', quiet=True))

        d = self.db.model.upgrade()
        d.addCallback(lambda _ : self.db.start())
        d.addCallback(lambda _ : self.db.changes.getChangeInstance(1))
        def check(c):
            self.failIf(c is None)
            self.assertEquals(c.who, u"Frosty the \N{SNOWMAN}")
            self.assertEquals(c.comments, u"Frosty the \N{SNOWMAN}")
        d.addCallback(check)
        return d
