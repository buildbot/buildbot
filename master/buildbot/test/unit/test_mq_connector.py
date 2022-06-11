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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.mq import base
from buildbot.mq import connector
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import service


class FakeMQ(service.ReconfigurableServiceMixin, base.MQBase):

    new_config = "not_called"

    def reconfigServiceWithBuildbotConfig(self, new_config):
        self.new_config = new_config
        return defer.succeed(None)

    def produce(self, routingKey, data):
        pass

    def startConsuming(self, callback, filter, persistent_name=None):
        return defer.succeed(None)


class MQConnector(TestReactorMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        self.mqconfig = self.master.config.mq = {}
        self.conn = connector.MQConnector()
        yield self.conn.setServiceParent(self.master)

    def patchFakeMQ(self, name='fake'):
        self.patch(connector.MQConnector, 'classes',
                   {name:
                    {'class': 'buildbot.test.unit.test_mq_connector.FakeMQ'},
                    })

    @defer.inlineCallbacks
    def test_setup_unknown_type(self):
        self.mqconfig['type'] = 'unknown'
        with self.assertRaises(AssertionError):
            yield self.conn.setup()

    @defer.inlineCallbacks
    def test_setup_simple_type(self):
        self.patchFakeMQ(name='simple')
        self.mqconfig['type'] = 'simple'
        yield self.conn.setup()
        self.assertIsInstance(self.conn.impl, FakeMQ)
        self.assertEqual(self.conn.impl.produce, self.conn.produce)
        self.assertEqual(self.conn.impl.startConsuming,
                         self.conn.startConsuming)

    @defer.inlineCallbacks
    def test_reconfigServiceWithBuildbotConfig(self):
        self.patchFakeMQ()
        self.mqconfig['type'] = 'fake'
        self.conn.setup()
        new_config = mock.Mock()
        new_config.mq = dict(type='fake')
        yield self.conn.reconfigServiceWithBuildbotConfig(new_config)

        self.assertIdentical(self.conn.impl.new_config, new_config)

    @defer.inlineCallbacks
    def test_reconfigService_change_type(self):
        self.patchFakeMQ()
        self.mqconfig['type'] = 'fake'
        yield self.conn.setup()
        new_config = mock.Mock()
        new_config.mq = dict(type='other')
        try:
            yield self.conn.reconfigServiceWithBuildbotConfig(new_config)
        except AssertionError:
            pass  # expected
        else:
            self.fail("should have failed")
