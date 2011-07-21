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

import mock
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.process.users import manager, manual

class TestUserManager(unittest.TestCase):
    def setUp(self):
        self.master = mock.Mock()
        self.um = manager.UserManager()
        self.um.parent = self.master
        self.um.startService()

    def tearDown(self):
        self.um.stopService()

    def test_setUpManualUsers(self):

        class ManualUsers(manual.UsersBase):

            def startService(self):
                assert self.master is not None
                manual.UsersBase.startService(self)

            def stopService(self):
                return manual.UsersBase.stopService(self)

        d = defer.succeed(None)
        test_ManualUsers = ManualUsers()
        d.addCallback(lambda _ : self.um.setUpManualUsers([test_ManualUsers]))
        def check(_):
            self.assertEqual(test_ManualUsers.parent, self.um)
        d.addCallback(check)
        return d
