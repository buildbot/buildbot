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

# Test clean shutdown functionality of the master
import mock
from twisted.trial import unittest
from buildbot import pbmanager   

class TestPBManager(unittest.TestCase):

    def setUp(self):
        self.pbm = pbmanager.PBManager()
        self.pbm.startService()

    def tearDown(self):
        return self.pbm.stopService()

    def perspectiveFactory(self, mind, username):
        self.connections.append(username)
        return mock.Mock()

    def test_register_unregister(self):
        portstr = "tcp:0:interface=127.0.0.1"
        reg = self.pbm.register(portstr, "boris", "pass", None)

        # make sure things look right
        self.assertIn(portstr, self.pbm.dispatchers)
        disp = self.pbm.dispatchers[portstr]
        self.assertIn('boris', disp.users)

        # TODO: actually connect to it?  How can we find the dynamically
        # allocated port?

        return reg.unregister()

    def test_double_register_unregister(self):
        portstr = "tcp:0:interface=127.0.0.1"
        reg1 = self.pbm.register(portstr, "boris", "pass", None)
        reg2 = self.pbm.register(portstr, "ivona", "pass", None)

        # make sure things look right
        self.assertEqual(len(self.pbm.dispatchers), 1)
        self.assertIn(portstr, self.pbm.dispatchers)
        disp = self.pbm.dispatchers[portstr]
        self.assertIn('boris', disp.users)
        self.assertIn('ivona', disp.users)

        d = reg1.unregister()
        def check_boris_gone(_):
            self.assertEqual(len(self.pbm.dispatchers), 1)
            self.assertIn(portstr, self.pbm.dispatchers)
            disp = self.pbm.dispatchers[portstr]
            self.assertNotIn('boris', disp.users)
            self.assertIn('ivona', disp.users)
        d.addCallback(check_boris_gone)
        d.addCallback(lambda _ : reg2.unregister())
        def check_dispatcher_gone(_):
            self.assertEqual(len(self.pbm.dispatchers), 0)
        d.addCallback(check_dispatcher_gone)
        return d
