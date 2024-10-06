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

from buildbot.changes import mail
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import changesource
from buildbot.test.util import dirs


class TestMaildirSource(
    changesource.ChangeSourceMixin, dirs.DirsMixin, TestReactorMixin, unittest.TestCase
):
    async def setUp(self):
        self.setup_test_reactor()
        self.maildir = os.path.abspath("maildir")

        await self.setUpChangeSource()
        await self.setUpDirs(self.maildir)

    def populateMaildir(self):
        "create a fake maildir with a fake new message ('newmsg') in it"
        newdir = os.path.join(self.maildir, "new")
        os.makedirs(newdir)

        curdir = os.path.join(self.maildir, "cur")
        os.makedirs(curdir)

        fake_message = "Subject: test\n\nthis is a test"
        mailfile = os.path.join(newdir, "newmsg")
        with open(mailfile, "w", encoding='utf-8') as f:
            f.write(fake_message)

    def assertMailProcessed(self):
        self.assertFalse(os.path.exists(os.path.join(self.maildir, "new", "newmsg")))
        self.assertTrue(os.path.exists(os.path.join(self.maildir, "cur", "newmsg")))

    async def tearDown(self):
        await self.tearDownDirs()
        await self.tearDownChangeSource()

    # tests

    def test_describe(self):
        mds = mail.MaildirSource(self.maildir)
        self.assertSubstring(self.maildir, mds.describe())

    async def test_messageReceived_svn(self):
        self.populateMaildir()
        mds = mail.MaildirSource(self.maildir)
        await self.attachChangeSource(mds)

        # monkey-patch in a parse method
        def parse(message, prefix):
            assert 'this is a test' in message.get_payload()
            return ('svn', {"author": 'jimmy'})

        mds.parse = parse

        await mds.messageReceived('newmsg')

        self.assertMailProcessed()
        self.assertEqual(
            self.master.data.updates.changesAdded,
            [
                {
                    'author': 'jimmy',
                    'committer': None,
                    'branch': None,
                    'category': None,
                    'codebase': None,
                    'comments': None,
                    'files': None,
                    'project': '',
                    'properties': {},
                    'repository': '',
                    'revision': None,
                    'revlink': '',
                    'src': 'svn',
                    'when_timestamp': None,
                }
            ],
        )

    async def test_messageReceived_bzr(self):
        self.populateMaildir()
        mds = mail.MaildirSource(self.maildir)
        await self.attachChangeSource(mds)

        # monkey-patch in a parse method
        def parse(message, prefix):
            assert 'this is a test' in message.get_payload()
            return ('bzr', {"author": 'jimmy'})

        mds.parse = parse

        await mds.messageReceived('newmsg')

        self.assertMailProcessed()
        self.assertEqual(
            self.master.data.updates.changesAdded,
            [
                {
                    'author': 'jimmy',
                    'committer': None,
                    'branch': None,
                    'category': None,
                    'codebase': None,
                    'comments': None,
                    'files': None,
                    'project': '',
                    'properties': {},
                    'repository': '',
                    'revision': None,
                    'revlink': '',
                    'src': 'bzr',
                    'when_timestamp': None,
                }
            ],
        )
