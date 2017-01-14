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

from twisted.trial import unittest

from buildbot.data import base
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint


class ResourceType(unittest.TestCase):

    def makeResourceTypeSubclass(self, **attributes):
        attributes.setdefault('name', 'thing')
        return type('ThingResourceType', (base.ResourceType,), attributes)

    def test_sets_master(self):
        cls = self.makeResourceTypeSubclass()
        master = mock.Mock()
        inst = cls(master)
        self.assertIdentical(inst.master, master)

    def test_getEndpoints_instances_fails(self):
        ep = base.Endpoint(None, None)
        cls = self.makeResourceTypeSubclass(endpoints=[ep])
        inst = cls(None)
        self.assertRaises(TypeError, lambda: inst.getEndpoints())

    def test_getEndpoints_classes(self):
        class MyEndpoint(base.Endpoint):
            pass
        cls = self.makeResourceTypeSubclass(endpoints=[MyEndpoint])
        master = mock.Mock()
        inst = cls(master)
        eps = inst.getEndpoints()
        self.assertIsInstance(eps[0], MyEndpoint)
        self.assertIdentical(eps[0].master, master)

    def test_produceEvent(self):
        cls = self.makeResourceTypeSubclass(
            name='singular',
            eventPathPatterns="/foo/:fooid/bar/:barid")
        master = fakemaster.make_master(testcase=self, wantMq=True)
        master.mq.verifyMessages = False  # since this is a pretend message
        inst = cls(master)
        inst.produceEvent(dict(fooid=10, barid='20'),  # note integer vs. string
                          'tested')
        master.mq.assertProductions([
            (('foo', '10', 'bar', '20', 'tested'), dict(fooid=10, barid='20'))
        ])

    def test_compilePatterns(self):
        class MyResourceType(base.ResourceType):
            eventPathPatterns = """
                /builder/:builderid/build/:number
                /build/:buildid
            """
        master = fakemaster.make_master(testcase=self, wantMq=True)
        master.mq.verifyMessages = False  # since this is a pretend message
        inst = MyResourceType(master)
        self.assertEqual(
            inst.eventPaths, ['builder/{builderid}/build/{number}', 'build/{buildid}'])


class Endpoint(endpoint.EndpointMixin, unittest.TestCase):

    class MyResourceType(base.ResourceType):
        name = "my"

    class MyEndpoint(base.Endpoint):
        pathPatterns = """
            /my/pattern
        """

    endpointClass = MyEndpoint
    resourceTypeClass = MyResourceType

    def setUp(self):
        self.setUpEndpoint()

    def tearDown(self):
        self.tearDownEndpoint()

    def test_sets_master(self):
        self.assertIdentical(self.master, self.ep.master)


class ListResult(unittest.TestCase):

    def test_constructor(self):
        lr = base.ListResult([1, 2, 3], offset=10, total=20, limit=3)
        self.assertEqual(lr.data, [1, 2, 3])
        self.assertEqual(lr.offset, 10)
        self.assertEqual(lr.total, 20)
        self.assertEqual(lr.limit, 3)

    def test_repr(self):
        lr = base.ListResult([1, 2, 3], offset=10, total=20, limit=3)
        self.assertTrue(repr(lr).startswith('ListResult'))

    def test_eq(self):
        lr1 = base.ListResult([1, 2, 3], offset=10, total=20, limit=3)
        lr2 = base.ListResult([1, 2, 3], offset=20, total=30, limit=3)
        lr3 = base.ListResult([1, 2, 3], offset=20, total=30, limit=3)
        self.assertEqual(lr2, lr3)
        self.assertNotEqual(lr1, lr2)
        self.assertNotEqual(lr1, lr3)

    def test_eq_to_list(self):
        list = [1, 2, 3]
        lr1 = base.ListResult([1, 2, 3], offset=10, total=20, limit=3)
        self.assertNotEqual(lr1, list)
        lr2 = base.ListResult([1, 2, 3], offset=None, total=None, limit=None)
        self.assertEqual(lr2, list)
        lr3 = base.ListResult([1, 2, 3], total=3)
        self.assertEqual(lr3, list)
        lr4 = base.ListResult([1, 2, 3], total=4)
        self.assertNotEqual(lr4, list)
