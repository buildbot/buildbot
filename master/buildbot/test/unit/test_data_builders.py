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

from twisted.trial import unittest
from twisted.internet import defer
from buildbot.data import builders
from buildbot.test.util import types, endpoint
from buildbot.test.fake import fakemaster

class Builder(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builders.BuilderEndpoint
    resourceTypeClass = builders.BuildersResourceType

    def setUp(self):
        self.setUpEndpoint()
        # TODO: use insertTestData instead
        self.rtype.builderIds = { 1 : u'buildera', 2 : u'builderb' }
        self.rtype.builders = self.rtype.builderIds.keys()

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_existing(self):
        d = self.callGet(dict(), dict(builderid=2))
        @d.addCallback
        def check(builder):
            types.verifyData(self, 'builder', {}, builder)
            self.assertEqual(builder['name'], u'builderb')
        return d

    def test_get_missing(self):
        d = self.callGet(dict(), dict(builderid=99))
        @d.addCallback
        def check(builder):
            self.assertEqual(builder, None)
        return d

    def test_get_existing_with_master(self):
        d = self.callGet(dict(), dict(masterid=13, builderid=2))
        @d.addCallback
        def check(builder):
            types.verifyData(self, 'builder', {}, builder)
            self.assertEqual(builder['name'], u'builderb')
        return d

    def test_get_missing_with_master(self):
        d = self.callGet(dict(), dict(masterid=13, builderid=99))
        @d.addCallback
        def check(builder):
            self.assertEqual(builder, None)
        return d


class Builders(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builders.BuildersEndpoint
    resourceTypeClass = builders.BuildersResourceType

    def setUp(self):
        self.setUpEndpoint()
        self.rtype.builderIds = { 1 : u'buildera', 2 : u'builderb' }
        self.rtype.builders = self.rtype.builderIds.values()


    def tearDown(self):
        self.tearDownEndpoint()


    def test_get(self):
        d = self.callGet(dict(), dict())
        @d.addCallback
        def check(builders):
            [ types.verifyData(self, 'builder', {}, b) for b in builders ]
            self.assertEqual(sorted([b['builderid'] for b in builders]),
                             [1, 2])
        return d

    def test_startConsuming(self):
        self.callStartConsuming({}, {},
                expected_filter=('builder', None, 'new'))


class BuilderResourceType(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                                                testcase=self)
        self.rtype = builders.BuildersResourceType(self.master)

    @defer.inlineCallbacks
    def test_updateBuilderList(self):
        # TODO: this method doesn't do anything yet, so very little to test..
        yield self.rtype.updateBuilderList(13, [ u'somebuidler' ])
