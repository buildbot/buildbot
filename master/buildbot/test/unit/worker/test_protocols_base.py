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

from buildbot.test.fake import fakeprotocol
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import protocols
from buildbot.worker.protocols import base


class TestFakeConnection(protocols.ConnectionInterfaceTest,
                         TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.worker = mock.Mock()
        self.conn = fakeprotocol.FakeConnection(self.worker)


class TestConnection(protocols.ConnectionInterfaceTest,
                     TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.worker = mock.Mock()
        self.conn = base.Connection(self.worker.workername)

    def test_notify(self):
        cb = mock.Mock()

        self.conn.notifyOnDisconnect(cb)
        self.assertEqual(cb.call_args_list, [])
        self.conn.notifyDisconnected()
        self.assertNotEqual(cb.call_args_list, [])
