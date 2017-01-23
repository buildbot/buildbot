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

from buildbot.test.fake import fakemaster
from buildbot.util import service
from buildbot.wamp import connector


class FakeConfig(object):
    mq = dict(type='wamp', router_url="wss://foo", realm="bb")


class FakeService(service.AsyncMultiService):
    name = "fakeWampService"
    # Fake wamp service
    # just call the maker on demand by the test

    def __init__(self, url, realm, make, extra=None,
                 debug=False, debug_wamp=False, debug_app=False):
        service.AsyncMultiService.__init__(self)
        self.make = make
        self.extra = extra

    def gotConnection(self):
        self.make(None)
        r = self.make(self)
        r.publish = mock.Mock(spec=r.publish)
        r.register = mock.Mock(spec=r.register)
        r.subscribe = mock.Mock(spec=r.subscribe)
        r.onJoin(None)


class TestedWampConnector(connector.WampConnector):
    serviceClass = FakeService


class WampConnector(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        master = fakemaster.make_master()
        self.connector = TestedWampConnector()
        yield self.connector.setServiceParent(master)
        yield master.startService()
        yield self.connector.reconfigServiceWithBuildbotConfig(FakeConfig())

    @defer.inlineCallbacks
    def test_startup(self):
        d = self.connector.getService()
        self.connector.app.gotConnection()
        yield d
        # 824 is the hardcoded masterid of fakemaster
        self.connector.service.publish.assert_called_with(
            "org.buildbot.824.connected")

    @defer.inlineCallbacks
    def test_subscribe(self):
        d = self.connector.subscribe('callback', 'topic', 'options')
        self.connector.app.gotConnection()
        yield d
        self.connector.service.subscribe.assert_called_with(
            'callback', 'topic', 'options')

    @defer.inlineCallbacks
    def test_publish(self):
        d = self.connector.publish('topic', 'data', 'options')
        self.connector.app.gotConnection()
        yield d
        self.connector.service.publish.assert_called_with(
            'topic', 'data', options='options')

    @defer.inlineCallbacks
    def test_OnLeave(self):
        d = self.connector.getService()
        self.connector.app.gotConnection()
        yield d
        self.assertTrue(self.connector.master.running)
        self.connector.service.onLeave(None)
        self.assertFalse(self.connector.master.running)
