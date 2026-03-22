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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import dirs
from buildbot.util import maildir

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class TestMaildirService(dirs.DirsMixin, TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.maildir = os.path.abspath("maildir")
        self.newdir = os.path.join(self.maildir, "new")
        self.curdir = os.path.join(self.maildir, "cur")
        self.tmpdir = os.path.join(self.maildir, "tmp")
        self.setUpDirs(self.maildir, self.newdir, self.curdir, self.tmpdir)

        self.master = yield fakemaster.make_master(self, wantDb=True, wantMq=True, wantData=True)

        self.svc = None

    def tearDown(self) -> None:
        if self.svc and self.svc.running:
            self.svc.stopService()

    # tests

    @defer.inlineCallbacks
    def test_start_stop_repeatedly(self) -> InlineCallbacksType[None]:
        self.svc = maildir.MaildirService(self.maildir)  # type: ignore[assignment]
        yield self.svc.setServiceParent(self.master)  # type: ignore[attr-defined]
        yield self.master.startService()
        yield self.master.stopService()
        yield self.master.startService()
        yield self.master.stopService()
        self.assertEqual(len(list(self.svc)), 0)  # type: ignore[call-overload]

    @defer.inlineCallbacks
    def test_messageReceived(self) -> InlineCallbacksType[None]:
        self.svc = maildir.MaildirService(self.maildir)  # type: ignore[assignment]
        yield self.svc.setServiceParent(self.master)  # type: ignore[attr-defined]

        # add a fake messageReceived method
        messagesReceived = []

        def messageReceived(filename: str) -> defer.Deferred[None]:
            messagesReceived.append(filename)
            return defer.succeed(None)

        self.svc.messageReceived = messageReceived  # type: ignore[attr-defined]
        yield self.master.startService()

        self.assertEqual(messagesReceived, [])

        tmpfile = os.path.join(self.tmpdir, "newmsg")
        newfile = os.path.join(self.newdir, "newmsg")
        with open(tmpfile, "w", encoding='utf-8'):
            pass
        os.rename(tmpfile, newfile)

        # TODO: can we wait for a dnotify somehow, if enabled?
        yield self.svc.poll()  # type: ignore[attr-defined]

        self.assertEqual(messagesReceived, ['newmsg'])

    def test_moveToCurDir(self) -> None:
        self.svc = maildir.MaildirService(self.maildir)  # type: ignore[assignment]
        tmpfile = os.path.join(self.tmpdir, "newmsg")
        newfile = os.path.join(self.newdir, "newmsg")
        with open(tmpfile, "w", encoding='utf-8'):
            pass
        os.rename(tmpfile, newfile)
        f = self.svc.moveToCurDir("newmsg")  # type: ignore[attr-defined]
        f.close()
        self.assertEqual(
            [
                os.path.exists(os.path.join(d, "newmsg"))
                for d in (self.newdir, self.curdir, self.tmpdir)
            ],
            [False, True, False],
        )
