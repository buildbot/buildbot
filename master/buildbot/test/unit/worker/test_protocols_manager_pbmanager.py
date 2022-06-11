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

import mock

from twisted.cred import credentials
from twisted.internet import defer
from twisted.spread import pb
from twisted.trial import unittest

from buildbot.worker.protocols.manager.pb import PBManager


class FakeMaster:
    initLock = defer.DeferredLock()

    def addService(self, svc):
        pass

    @property
    def master(self):
        return self


class TestPBManager(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.pbm = PBManager()
        yield self.pbm.setServiceParent(FakeMaster())
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

    @defer.inlineCallbacks
    def test_register_unregister(self):
        portstr = "tcp:0:interface=127.0.0.1"
        reg = yield self.pbm.register(portstr, "boris", "pass", self.perspectiveFactory)

        # make sure things look right
        self.assertIn(portstr, self.pbm.dispatchers)
        disp = self.pbm.dispatchers[portstr]
        self.assertIn('boris', disp.users)

        # we can't actually connect to it, as that requires finding the
        # dynamically allocated port number which is buried out of reach;
        # however, we can try the requestAvatar and requestAvatarId methods.

        username = yield disp.requestAvatarId(credentials.UsernamePassword(b'boris', b'pass'))

        self.assertEqual(username, b'boris')
        avatar = yield disp.requestAvatar(b'boris', mock.Mock(), pb.IPerspective)

        _, persp, __ = avatar
        self.assertTrue(persp.is_my_persp)
        self.assertIn('boris', self.connections)

        yield reg.unregister()

    @defer.inlineCallbacks
    def test_register_no_user(self):
        portstr = "tcp:0:interface=127.0.0.1"
        reg = yield self.pbm.register(portstr, "boris", "pass", self.perspectiveFactory)

        # make sure things look right
        self.assertIn(portstr, self.pbm.dispatchers)
        disp = self.pbm.dispatchers[portstr]
        self.assertIn('boris', disp.users)

        # we can't actually connect to it, as that requires finding the
        # dynamically allocated port number which is buried out of reach;
        # however, we can try the requestAvatar and requestAvatarId methods.

        username = yield disp.requestAvatarId(credentials.UsernamePassword(b'boris', b'pass'))

        self.assertEqual(username, b'boris')
        with self.assertRaises(ValueError):
            yield disp.requestAvatar(b'notboris', mock.Mock(), pb.IPerspective)

        self.assertNotIn('boris', self.connections)

        yield reg.unregister()

    @defer.inlineCallbacks
    def test_requestAvatarId_noinitLock(self):
        portstr = "tcp:0:interface=127.0.0.1"
        reg = yield self.pbm.register(portstr, "boris", "pass", self.perspectiveFactory)

        disp = self.pbm.dispatchers[portstr]

        d = disp.requestAvatarId(credentials.UsernamePassword(b'boris', b'pass'))
        self.assertTrue(d.called,
            "requestAvatarId should have been called since the lock is free")

        yield reg.unregister()

    @defer.inlineCallbacks
    def test_requestAvatarId_initLock(self):
        portstr = "tcp:0:interface=127.0.0.1"
        reg = yield self.pbm.register(portstr, "boris", "pass", self.perspectiveFactory)

        disp = self.pbm.dispatchers[portstr]

        try:
            # simulate a reconfig/restart in progress
            yield self.pbm.master.initLock.acquire()
            # try to authenticate while the lock is locked
            d = disp.requestAvatarId(credentials.UsernamePassword(b'boris', b'pass'))
            self.assertFalse(d.called,
                "requestAvatarId should block until the lock is released")
        finally:
            # release the lock, it should allow for auth to proceed
            yield self.pbm.master.initLock.release()

        self.assertTrue(d.called,
            "requestAvatarId should have been called after the lock was released")
        yield reg.unregister()
