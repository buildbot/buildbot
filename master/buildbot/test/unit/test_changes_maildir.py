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
import shutil
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.changes import maildir

class TestMaildirService(unittest.TestCase):
    def setUp(self):
        self.maildir = os.path.abspath("maildir")
        if os.path.exists(self.maildir):
            shutil.rmtree(self.maildir)

        self.newdir = os.path.join(self.maildir, "new")
        os.makedirs(self.newdir)
        self.curdir = os.path.join(self.maildir, "cur")
        os.makedirs(self.curdir)
        self.tmpdir = os.path.join(self.maildir, "tmp")
        os.makedirs(self.tmpdir)

        self.svc = None

    def tearDown(self):
        if self.svc:
            self.svc.stopService()
        if os.path.exists(self.maildir):
            shutil.rmtree(self.maildir)

    # tests

    def test_messageReceived(self):
        self.svc = maildir.MaildirService(self.maildir)

        # add a fake messageReceived method
        messagesReceived = []
        def messageReceived(filename):
            messagesReceived.append(filename)
            return defer.succeed(None)
        self.svc.messageReceived = messageReceived
        d = defer.maybeDeferred(self.svc.startService)
        def check_empty(_):
            self.assertEqual(messagesReceived, [])
        d.addCallback(check_empty)
        def add_msg(_):
            tmpfile = os.path.join(self.tmpdir, "newmsg")
            newfile = os.path.join(self.newdir, "newmsg")
            open(tmpfile, "w")
            os.rename(tmpfile, newfile)
        d.addCallback(add_msg)
        def trigger(_):
            # TODO: can we wait for a dnotify somehow, if enabled?
            return self.svc.poll()
        d.addCallback(trigger)
        def check_nonempty(_):
            self.assertEqual(messagesReceived, [ 'newmsg' ])
        d.addCallback(check_nonempty)
        return d
