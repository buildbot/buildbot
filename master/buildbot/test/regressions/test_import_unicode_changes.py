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
from buildbot.test.fake import fakemaster
from buildbot.test.util import change_import


class TestUnicodeChanges(change_import.ChangeImportMixin, unittest.TestCase):

    def setUp(self):
        d = self.setUpChangeImport()

        @d.addCallback
        def make_dbc(_):
            master = fakemaster.make_master()
            master.config.db['db_url'] = self.db_url
            self.db = DBConnector(self.basedir)
            self.db.setServiceParent(master)
            return self.db.setup(check_version=False)

        # note the connector isn't started, as we're testing upgrades
        return d

    def tearDown(self):
        return self.tearDownChangeImport()

    # tests

    def testUnicodeChange(self):
        self.make_pickle(
            self.make_change(
                who=u"Frosty the \N{SNOWMAN}".encode("utf8"),
                files=["foo"],
                comments=u"Frosty the \N{SNOWMAN}".encode("utf8"),
                branch="b1",
                revision=12345))

        d = self.db.model.upgrade()
        d.addCallback(lambda _: self.db.changes.getChange(1))

        @d.addCallback
        def check(c):
            self.failIf(c is None)
            self.assertEquals(c['author'], u"Frosty the \N{SNOWMAN}")
            self.assertEquals(c['comments'], u"Frosty the \N{SNOWMAN}")
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
        return self.assertFailure(d, UnicodeError)

    def testAsciiChange(self):
        self.make_pickle(
            self.make_change(
                who="Frosty the Snowman",
                files=["foo"],
                comments="Frosty the Snowman",
                branch="b1",
                revision=12345))

        d = self.db.model.upgrade()
        d.addCallback(lambda _: self.db.changes.getChange(1))

        @d.addCallback
        def check(c):
            self.failIf(c is None)
            self.assertEquals(c['author'], "Frosty the Snowman")
            self.assertEquals(c['comments'], "Frosty the Snowman")
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
            recode_fn=lambda cm: cm.recode_changes('utf16', quiet=True))

        d = self.db.model.upgrade()
        d.addCallback(lambda _: self.db.changes.getChange(1))

        @d.addCallback
        def check(c):
            self.failIf(c is None)
            self.assertEquals(c['author'], u"Frosty the \N{SNOWMAN}")
            self.assertEquals(c['comments'], u"Frosty the \N{SNOWMAN}")
        return d
