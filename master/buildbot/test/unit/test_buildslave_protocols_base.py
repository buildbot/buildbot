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
from buildbot.buildslave.protocols import base
from buildbot.test.fake import fakemaster


class TestListener(unittest.TestCase):
    def test_constructor(self):
        master = fakemaster.make_master()
        listener = base.Listener(master)
        self.assertEqual(listener.master, master)


class TestConnection(unittest.TestCase):
    def setUp(self):
        self.master = fakemaster.make_master()
        self.buildslave = mock.Mock()
        self.conn = base.Connection(self.master, self.buildslave)

    def test_constructor(self):
        self.assertEqual(self.conn.master, self.master)
        self.assertEqual(self.conn.buildslave, self.buildslave)

    def test_notify(self):
        cb = mock.Mock()

        self.conn.notifyOnDisconnect(cb)
        self.conn.notifyDisconnected()
        self.assertNotEqual(cb.call_args_list, [])

    def test_loseConnection(self):
        self.assertRaises(NotImplementedError, self.conn.loseConnection)

    def test_remotePrint(self):
        self.assertRaises(NotImplementedError, self.conn.remotePrint, message='err')

    def test_remoteGetSlaveInfo(self):
        self.assertRaises(NotImplementedError, self.conn.remoteGetSlaveInfo)

    def test_remoteSetBuilderList(self):
        b = ["builder1", "builder2"]
        self.assertRaises(NotImplementedError, self.conn.remoteSetBuilderList, b)
