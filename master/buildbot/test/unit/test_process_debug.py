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
from buildbot.process import debug

class TestRegisterDebugClient(unittest.TestCase):

    def test_registerDebugClient(self):
        pbmanager = mock.Mock()
        pbmanager.register.return_value = mock.Mock()
        master = mock.Mock()
        slavePortnum = 9824
        debugPassword = 'seeeekrt'

        rv = debug.registerDebugClient(master, slavePortnum,
                                       debugPassword, pbmanager)

        # test return value and that the register method was called
        self.assertIdentical(rv, pbmanager.register.return_value)
        self.assertEqual(pbmanager.register.call_args[0][0], slavePortnum)
        self.assertEqual(pbmanager.register.call_args[0][1], "debug")
        self.assertEqual(pbmanager.register.call_args[0][2], debugPassword)

        # test the lambda
        mind = mock.Mock()
        username = "hush"
        dc = pbmanager.register.call_args[0][3](mind, username)
        self.assertIsInstance(dc, debug.DebugPerspective)

class TestDebugPerspective(unittest.TestCase):

    def setUp(self):
        self.persp = debug.DebugPerspective()
        self.master = self.persp.master = mock.Mock()
        self.botmaster = self.persp.botmaster = mock.Mock()

    def test_attached(self):
        self.assertIdentical(self.persp.attached(mock.Mock()), self.persp)

    def test_detached(self):
        self.persp.detached(mock.Mock()) # just shouldn't crash

    def test_perspective_reload(self):
        d = defer.maybeDeferred(lambda : self.persp.perspective_reload())
        def check(_):
            self.master.loadTheConfigFile.assert_called_with()
        d.addCallback(check)
        return d

    # remaining methods require IControl adapters or other weird stuff.. TODO
