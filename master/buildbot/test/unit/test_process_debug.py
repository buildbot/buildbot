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

from buildbot import config
from buildbot.process import debug
from buildbot.util import service
from twisted.internet import defer
from twisted.trial import unittest


class FakeManhole(service.AsyncService):
    pass


class TestDebugServices(unittest.TestCase):

    def setUp(self):
        self.master = mock.Mock(name='master')
        self.config = config.MasterConfig()

    @defer.inlineCallbacks
    def test_reconfigService_manhole(self):
        master = mock.Mock(name='master')
        ds = debug.DebugServices(master)
        ds.startService()

        # start off with no manhole
        yield ds.reconfigService(self.config)

        # set a manhole, fire it up
        self.config.manhole = manhole = FakeManhole()
        yield ds.reconfigService(self.config)

        self.assertTrue(manhole.running)
        self.assertIdentical(manhole.master, master)

        # unset it, see it stop
        self.config.manhole = None
        yield ds.reconfigService(self.config)

        self.assertFalse(manhole.running)
        self.assertIdentical(manhole.master, None)

        # re-start to test stopService
        self.config.manhole = manhole
        yield ds.reconfigService(self.config)

        # stop the service, and see that it unregisters
        yield ds.stopService()

        self.assertFalse(manhole.running)
        self.assertIdentical(manhole.master, None)


