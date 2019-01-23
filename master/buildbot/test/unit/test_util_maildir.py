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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.util import dirs
from buildbot.util import maildir


class TestMaildirService(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.maildir = os.path.abspath("maildir")
        self.newdir = os.path.join(self.maildir, "new")
        self.curdir = os.path.join(self.maildir, "cur")
        self.tmpdir = os.path.join(self.maildir, "tmp")
        self.setUpDirs(self.maildir, self.newdir, self.curdir, self.tmpdir)

        self.svc = None

    def tearDown(self):
        if self.svc and self.svc.running:
            self.svc.stopService()
        self.tearDownDirs()

    # tests

    @defer.inlineCallbacks
    def test_start_stop_repeatedly(self):
        self.svc = maildir.MaildirService(self.maildir)
        self.svc.startService()
        yield self.svc.stopService()
        self.svc.startService()
        yield self.svc.stopService()
        self.assertEqual(len(list(self.svc)), 0)

    @defer.inlineCallbacks
    def test_messageReceived(self):
        self.svc = maildir.MaildirService(self.maildir)

        # add a fake messageReceived method
        messagesReceived = []

        def messageReceived(filename):
            messagesReceived.append(filename)
            return defer.succeed(None)
        self.svc.messageReceived = messageReceived
        yield defer.maybeDeferred(self.svc.startService)

        self.assertEqual(messagesReceived, [])

        tmpfile = os.path.join(self.tmpdir, "newmsg")
        newfile = os.path.join(self.newdir, "newmsg")
        open(tmpfile, "w").close()
        os.rename(tmpfile, newfile)

        # TODO: can we wait for a dnotify somehow, if enabled?
        yield self.svc.poll()

        self.assertEqual(messagesReceived, ['newmsg'])

    def test_moveToCurDir(self):
        self.svc = maildir.MaildirService(self.maildir)
        tmpfile = os.path.join(self.tmpdir, "newmsg")
        newfile = os.path.join(self.newdir, "newmsg")
        open(tmpfile, "w").close()
        os.rename(tmpfile, newfile)
        f = self.svc.moveToCurDir("newmsg")
        f.close()
        self.assertEqual([os.path.exists(os.path.join(d, "newmsg"))
                          for d in (self.newdir, self.curdir, self.tmpdir)],
                         [False, True, False])
