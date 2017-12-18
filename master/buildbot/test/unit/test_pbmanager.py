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
"""
Test clean shutdown functionality of the master
"""

from __future__ import absolute_import
from __future__ import print_function

import mock

from twisted.cred import credentials
from twisted.internet import defer
from twisted.spread import pb
from twisted.trial import unittest

from buildbot import pbmanager


class TestPBManager(unittest.TestCase):

    def setUp(self):
        self.pbm = pbmanager.PBManager()
        self.pbm.startService()
        self.connections = []

    def tearDown(self):
        return self.pbm.stopService()

    def perspectiveFactory(self, mind, username):
        persp = mock.Mock()
        persp.is_my_persp = True
        persp.attached = lambda mind: defer.succeed(None)
        self.connections.append(username)
        return defer.succeed(persp)

    def test_repr(self):
        reg = self.pbm.register(
            'tcp:0:interface=127.0.0.1', "x", "y", self.perspectiveFactory)
        self.assertEqual(repr(self.pbm.dispatchers['tcp:0:interface=127.0.0.1']),
                         '<pbmanager.Dispatcher for x on tcp:0:interface=127.0.0.1>')
        self.assertEqual(
            repr(reg), '<pbmanager.Registration for x on tcp:0:interface=127.0.0.1>')

    def test_register_unregister(self):
        portstr = "tcp:0:interface=127.0.0.1"
        reg = self.pbm.register(
            portstr, "boris", "pass", self.perspectiveFactory)

        # make sure things look right
        self.assertIn(portstr, self.pbm.dispatchers)
        disp = self.pbm.dispatchers[portstr]
        self.assertIn('boris', disp.users)

        # we can't actually connect to it, as that requires finding the
        # dynamically allocated port number which is buried out of reach;
        # however, we can try the requestAvatar and requestAvatarId methods.

        d = disp.requestAvatarId(credentials.UsernamePassword(b'boris', b'pass'))

        def check_avatarid(username):
            self.assertEqual(username, b'boris')
        d.addCallback(check_avatarid)
        d.addCallback(lambda _:
                      disp.requestAvatar(b'boris', mock.Mock(), pb.IPerspective))

        def check_avatar(avatar):
            (iface, persp, detach_fn) = avatar
            self.assertTrue(persp.is_my_persp)
            self.assertIn('boris', self.connections)
        d.addCallback(check_avatar)

        d.addCallback(lambda _: reg.unregister())
        return d

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
        d.addCallback(lambda _: reg2.unregister())

        def check_dispatcher_gone(_):
            self.assertEqual(len(self.pbm.dispatchers), 0)
        d.addCallback(check_dispatcher_gone)
        return d
