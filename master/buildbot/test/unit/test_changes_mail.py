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
from twisted.trial import unittest
from buildbot.test.util import changesource, dirs
from buildbot.changes import mail

class TestMaildirSource(changesource.ChangeSourceMixin, dirs.DirsMixin,
                        unittest.TestCase):

    def setUp(self):
        self.maildir = os.path.abspath("maildir")

        d = self.setUpChangeSource()
        d.addCallback(lambda _ : self.setUpDirs(self.maildir))
        return d

    def populateMaildir(self):
        "create a fake maildir with a fake new message ('newmsg') in it"
        newdir = os.path.join(self.maildir, "new")
        os.makedirs(newdir)

        curdir = os.path.join(self.maildir, "cur")
        os.makedirs(curdir)

        fake_message = "Subject: test\n\nthis is a test"
        mailfile = os.path.join(newdir, "newmsg")
        open(mailfile, "w").write(fake_message)

    def assertMailProcessed(self):
        self.assertFalse(os.path.exists(os.path.join(self.maildir, "new", "newmsg")))
        self.assertTrue(os.path.exists(os.path.join(self.maildir, "cur", "newmsg")))

    def tearDown(self):
        d = self.tearDownDirs()
        d.addCallback(lambda _ : self.tearDownChangeSource())
        return d

    # tests

    def test_describe(self):
        mds = mail.MaildirSource(self.maildir)
        self.assertSubstring(self.maildir, mds.describe())

    def test_messageReceived(self):
        self.populateMaildir()
        mds = mail.MaildirSource(self.maildir)
        self.attachChangeSource(mds)

        # monkey-patch in a parse method
        def parse(message, prefix):
            assert 'this is a test' in message.get_payload()
            return dict(fake_chdict=1)
        mds.parse = parse

        d = mds.messageReceived('newmsg')
        def check(_):
            self.assertMailProcessed()
            self.assertEqual(len(self.changes_added), 1)
            self.assertEqual(self.changes_added[0]['fake_chdict'], 1)
        d.addCallback(check)
        return d
