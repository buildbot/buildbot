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

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes import mail
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import changesource
from buildbot.test.util import dirs

if TYPE_CHECKING:
    from email.message import Message

    from buildbot.util.twisted import InlineCallbacksType


class TestMaildirSource(
    changesource.ChangeSourceMixin, dirs.DirsMixin, TestReactorMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.maildir = os.path.abspath("maildir")

        yield self.setUpChangeSource()
        yield self.setUpDirs(self.maildir)

    def populateMaildir(self) -> None:
        "create a fake maildir with a fake new message ('newmsg') in it"
        newdir = os.path.join(self.maildir, "new")
        os.makedirs(newdir)

        curdir = os.path.join(self.maildir, "cur")
        os.makedirs(curdir)

        fake_message = "Subject: test\n\nthis is a test"
        mailfile = os.path.join(newdir, "newmsg")
        with open(mailfile, "w", encoding='utf-8') as f:
            f.write(fake_message)

    def assertMailProcessed(self) -> None:
        self.assertFalse(os.path.exists(os.path.join(self.maildir, "new", "newmsg")))
        self.assertTrue(os.path.exists(os.path.join(self.maildir, "cur", "newmsg")))

    # tests

    def test_describe(self) -> None:
        mds = mail.MaildirSource(self.maildir)
        self.assertSubstring(self.maildir, mds.describe())

    @defer.inlineCallbacks
    def test_messageReceived_svn(self) -> InlineCallbacksType[None]:
        self.populateMaildir()
        mds = mail.MaildirSource(self.maildir)
        yield self.attachChangeSource(mds)

        # monkey-patch in a parse method
        def parse(message: Message, prefix: str | None) -> tuple[str, dict[str, Any]] | None:
            assert 'this is a test' in message.get_payload()
            return ('svn', {"author": 'jimmy'})

        mds.parse = parse  # type: ignore[assignment, method-assign]

        yield mds.messageReceived('newmsg')

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
                    'properties': None,
                    'repository': '',
                    'revision': None,
                    'revlink': '',
                    'src': 'svn',
                    'when_timestamp': None,
                }
            ],
        )

    @defer.inlineCallbacks
    def test_messageReceived_bzr(self) -> InlineCallbacksType[None]:
        self.populateMaildir()
        mds = mail.MaildirSource(self.maildir)
        yield self.attachChangeSource(mds)

        # monkey-patch in a parse method
        def parse(message: Message, prefix: str | None) -> tuple[str, dict[str, Any]] | None:
            assert 'this is a test' in message.get_payload()
            return ('bzr', {"author": 'jimmy'})

        mds.parse = parse  # type: ignore[assignment, method-assign]

        yield mds.messageReceived('newmsg')

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
                    'properties': None,
                    'repository': '',
                    'revision': None,
                    'revlink': '',
                    'src': 'bzr',
                    'when_timestamp': None,
                }
            ],
        )
