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

from __future__ import absolute_import
from __future__ import print_function

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process.users import manager
from buildbot.util import service


class FakeUserManager(service.AsyncMultiService):
    pass


class TestUserManager(unittest.TestCase):

    def setUp(self):
        self.master = mock.Mock()
        self.umm = manager.UserManagerManager(self.master)
        self.umm.startService()

        self.config = config.MasterConfig()

    def tearDown(self):
        self.umm.stopService()

    @defer.inlineCallbacks
    def test_reconfigServiceWithBuildbotConfig(self):
        # add a user manager
        um1 = FakeUserManager()
        self.config.user_managers = [um1]

        yield self.umm.reconfigServiceWithBuildbotConfig(self.config)

        self.assertTrue(um1.running)
        self.assertIdentical(um1.master, self.master)

        # and back to nothing
        self.config.user_managers = []
        yield self.umm.reconfigServiceWithBuildbotConfig(self.config)

        self.assertIdentical(um1.master, None)
