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
from buildbot.process import debug
from buildbot.test.fake import fakemaster
from buildbot.util import service


class FakeManhole(service.AsyncService):
    pass


class TestDebugServices(unittest.TestCase):

    def setUp(self):
        self.master = mock.Mock(name='master')
        self.config = config.MasterConfig()

    @defer.inlineCallbacks
    def test_reconfigService_manhole(self):
        master = fakemaster.make_master()
        ds = debug.DebugServices()
        ds.setServiceParent(master)
        yield master.startService()

        # start off with no manhole
        yield ds.reconfigServiceWithBuildbotConfig(self.config)

        # set a manhole, fire it up
        self.config.manhole = manhole = FakeManhole()
        yield ds.reconfigServiceWithBuildbotConfig(self.config)

        self.assertTrue(manhole.running)
        self.assertIdentical(manhole.master, master)

        # unset it, see it stop
        self.config.manhole = None
        yield ds.reconfigServiceWithBuildbotConfig(self.config)

        self.assertFalse(manhole.running)
        self.assertIdentical(manhole.master, None)

        # re-start to test stopService
        self.config.manhole = manhole
        yield ds.reconfigServiceWithBuildbotConfig(self.config)

        # disown the service, and see that it unregisters
        yield ds.disownServiceParent()

        self.assertFalse(manhole.running)
        self.assertIdentical(manhole.master, None)
