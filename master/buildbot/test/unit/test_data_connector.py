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
from twisted.internet import defer
from twisted.python import reflect
from buildbot.data import connector, base
from buildbot.test.fake import fakemaster

class DataConnector(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        # don't load by default
        self.patch(connector.DataConnector, 'submodules', [])
        self.data = connector.DataConnector(self.master)

    def patchFooPattern(self):
        cls = type('MyEndpoint', (base.Endpoint,), {})
        ep = cls(self.master)
        ep.get = mock.Mock(name='MyEndpoint.get')
        ep.get.return_value = defer.succeed(9999)
        self.data.matcher[('foo', 'i:fooid', 'bar')] = ep
        return ep

    # tests

    def test_sets_master(self):
        self.assertIdentical(self.master, self.data.master)

    def test_scanModule(self):
        # use this module as a test
        mod = reflect.namedModule('buildbot.test.unit.test_data_connector')
        self.data._scanModule(mod)

        # check that it discovered MyResourceType and updated endpoints
        match = self.data.matcher[('test', '10')]
        self.assertIsInstance(match[0], TestEndpoint)
        self.assertEqual(match[1], dict(testid=10))

        # and that it found the update method
        self.assertEqual(self.data.updates.testUpdate(), "testUpdate return")

    def test_lookup(self):
        ep = self.patchFooPattern()
        self.assertEqual(self.data._lookup(('foo', '1', 'bar')),
                             (ep, dict(fooid=1)))

    def test_get(self):
        ep = self.patchFooPattern()
        d = self.data.get({'option': '1'}, ('foo', '10', 'bar'))

        @d.addCallback
        def check(gotten):
            self.assertEqual(gotten, 9999)
            ep.get.assert_called_once_with({'option' : '1'},
                                              {'fooid' : 10})
        return d

    def test_startConsuming(self):
        ep = self.patchFooPattern()
        ep.startConsuming = mock.Mock(name='MyEndpoint.startConsuming')
        ep.startConsuming.return_value = 'qref'

        # since startConsuming is a mock, there's no need for real mq stuff
        qref = self.data.startConsuming('cb', {}, ('foo', '10', 'bar'))
        self.assertEqual(qref, 'qref')
        ep.startConsuming.assert_called_with('cb', {}, dict(fooid=10))

    def test_control(self):
        ep = self.patchFooPattern()
        ep.control = mock.Mock(name='MyEndpoint.startConsuming')
        ep.control.return_value = defer.succeed('controlled')

        d = self.data.control('foo!', {'arg': 2}, ('foo', '10', 'bar'))

        @d.addCallback
        def check(gotten):
            self.assertEqual(gotten, 'controlled')
            ep.control.assert_called_once_with('foo!', {'arg' : 2},
                                                        {'fooid' : 10})
        return d

# classes discovered by test_scanModule, above

class TestEndpoint(base.Endpoint):
    pathPattern = ('test', 'i:testid')

class TestResourceType(base.ResourceType):
    name = 'tests'
    type = 'test'
    endpoints = [ TestEndpoint ]
    keyFields = ( 'testid', )

    @base.updateMethod
    def testUpdate(self):
        return "testUpdate return"
