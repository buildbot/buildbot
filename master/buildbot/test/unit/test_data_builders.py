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

from buildbot.data import builders
from buildbot.data import resultspec
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.test.util.misc import TestReactorMixin


class BuilderEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builders.BuilderEndpoint
    resourceTypeClass = builders.Builder

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insertTestData([
            fakedb.Builder(id=1, name='buildera'),
            fakedb.Builder(id=2, name='builderb'),
            fakedb.Master(id=13),
            fakedb.BuilderMaster(id=1, builderid=2, masterid=13),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing(self):
        builder = yield self.callGet(('builders', 2))

        self.validateData(builder)
        self.assertEqual(builder['name'], 'builderb')

    @defer.inlineCallbacks
    def test_get_missing(self):
        builder = yield self.callGet(('builders', 99))

        self.assertEqual(builder, None)

    @defer.inlineCallbacks
    def test_get_missing_with_name(self):
        builder = yield self.callGet(('builders', 'builderc'))

        self.assertEqual(builder, None)

    @defer.inlineCallbacks
    def test_get_existing_with_master(self):
        builder = yield self.callGet(('masters', 13, 'builders', 2))

        self.validateData(builder)
        self.assertEqual(builder['name'], 'builderb')

    @defer.inlineCallbacks
    def test_get_existing_with_different_master(self):
        builder = yield self.callGet(('masters', 14, 'builders', 2))

        self.assertEqual(builder, None)

    @defer.inlineCallbacks
    def test_get_missing_with_master(self):
        builder = yield self.callGet(('masters', 13, 'builders', 99))

        self.assertEqual(builder, None)


class BuildersEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builders.BuildersEndpoint
    resourceTypeClass = builders.Builder

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insertTestData([
            fakedb.Builder(id=1, name='buildera'),
            fakedb.Builder(id=2, name='builderb'),
            fakedb.Builder(id=3, name='builderTagA'),
            fakedb.Builder(id=4, name='builderTagB'),
            fakedb.Builder(id=5, name='builderTagAB'),
            fakedb.Tag(id=3, name="tagA"),
            fakedb.Tag(id=4, name="tagB"),
            fakedb.BuildersTags(builderid=3, tagid=3),
            fakedb.BuildersTags(builderid=4, tagid=4),
            fakedb.BuildersTags(builderid=5, tagid=3),
            fakedb.BuildersTags(builderid=5, tagid=4),
            fakedb.Master(id=13),
            fakedb.BuilderMaster(id=1, builderid=2, masterid=13),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get(self):
        builders = yield self.callGet(('builders',))

        [self.validateData(b) for b in builders]
        self.assertEqual(sorted([b['builderid'] for b in builders]),
                         [1, 2, 3, 4, 5])

    @defer.inlineCallbacks
    def test_get_masterid(self):
        builders = yield self.callGet(('masters', 13, 'builders'))

        [self.validateData(b) for b in builders]
        self.assertEqual(sorted([b['builderid'] for b in builders]),
                         [2])

    @defer.inlineCallbacks
    def test_get_masterid_missing(self):
        builders = yield self.callGet(('masters', 14, 'builders'))

        self.assertEqual(sorted([b['builderid'] for b in builders]), [])

    @defer.inlineCallbacks
    def test_get_contains_one_tag(self):
        resultSpec = resultspec.ResultSpec(
            filters=[resultspec.Filter('tags', 'contains', ["tagA"])])
        builders = yield self.callGet(('builders',))

        builders = resultSpec.apply(builders)
        [self.validateData(b) for b in builders]
        self.assertEqual(sorted([b['builderid'] for b in builders]),
                         [3, 5])

    @defer.inlineCallbacks
    def test_get_contains_two_tags(self):
        resultSpec = resultspec.ResultSpec(
            filters=[resultspec.Filter('tags', 'contains', ["tagA", "tagB"])])
        builders = yield self.callGet(('builders',))

        builders = resultSpec.apply(builders)
        [self.validateData(b) for b in builders]
        self.assertEqual(sorted([b['builderid'] for b in builders]),
                         [3, 4, 5])

    @defer.inlineCallbacks
    def test_get_contains_two_tags_one_unknown(self):
        resultSpec = resultspec.ResultSpec(
            filters=[resultspec.Filter('tags', 'contains', ["tagA", "tagC"])])
        builders = yield self.callGet(('builders',))

        builders = resultSpec.apply(builders)
        [self.validateData(b) for b in builders]
        self.assertEqual(sorted([b['builderid'] for b in builders]),
                         [3, 5])


class Builder(interfaces.InterfaceTests, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantDb=True,
                                             wantData=True)
        self.rtype = builders.Builder(self.master)
        return self.master.db.insertTestData([
            fakedb.Master(id=13),
            fakedb.Master(id=14),
        ])

    def test_signature_findBuilderId(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.findBuilderId,  # fake
            self.rtype.findBuilderId)  # real
        def findBuilderId(self, name):
            pass

    def test_findBuilderId(self):
        # this just passes through to the db method, so test that
        rv = defer.succeed(None)
        self.master.db.builders.findBuilderId = mock.Mock(return_value=rv)
        self.assertIdentical(self.rtype.findBuilderId('foo'), rv)

    def test_signature_updateBuilderInfo(self):
        @self.assertArgSpecMatches(self.master.data.updates.updateBuilderInfo)
        def updateBuilderInfo(self, builderid, description, tags):
            pass

    def test_signature_updateBuilderList(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.updateBuilderList,  # fake
            self.rtype.updateBuilderList)  # real
        def updateBuilderList(self, masterid, builderNames):
            pass

    @defer.inlineCallbacks
    def test_updateBuilderList(self):
        # add one builder master
        yield self.rtype.updateBuilderList(13, ['somebuilder'])
        self.assertEqual(sorted((yield self.master.db.builders.getBuilders())),
                         sorted([
                             dict(id=1, masterids=[13],
                                  name='somebuilder', description=None, tags=[]),
                         ]))
        self.master.mq.assertProductions([(('builders', '1', 'started'),
                                           {'builderid': 1, 'masterid': 13, 'name': 'somebuilder'})])

        # add another
        yield self.rtype.updateBuilderList(13, ['somebuilder', 'another'])

        def builderKey(builder):
            return builder['id']

        self.assertEqual(sorted((yield self.master.db.builders.getBuilders()), key=builderKey),
                         sorted([
                             dict(id=1, masterids=[13],
                                  name='somebuilder', description=None, tags=[]),
                             dict(id=2, masterids=[13],
                                  name='another', description=None, tags=[]),
                         ], key=builderKey))
        self.master.mq.assertProductions([(('builders', '2', 'started'),
                                           {'builderid': 2, 'masterid': 13, 'name': 'another'})])

        # add one for another master
        yield self.rtype.updateBuilderList(14, ['another'])
        self.assertEqual(sorted((yield self.master.db.builders.getBuilders()), key=builderKey),
                         sorted([
                             dict(id=1, masterids=[13],
                                  name='somebuilder', description=None, tags=[]),
                             dict(id=2, masterids=[13, 14],
                                  name='another', description=None, tags=[]),
                         ], key=builderKey))
        self.master.mq.assertProductions([(('builders', '2', 'started'),
                                           {'builderid': 2, 'masterid': 14, 'name': 'another'})])

        # remove both for the first master
        yield self.rtype.updateBuilderList(13, [])
        self.assertEqual(sorted((yield self.master.db.builders.getBuilders()), key=builderKey),
                         sorted([
                             dict(
                                 id=1, masterids=[], name='somebuilder', description=None, tags=[]),
                             dict(
                                 id=2, masterids=[14], name='another', description=None, tags=[]),
                         ], key=builderKey))
        self.master.mq.assertProductions([
            (('builders', '1', 'stopped'),
             {'builderid': 1, 'masterid': 13, 'name': 'somebuilder'}),
            (('builders', '2', 'stopped'),
             {'builderid': 2, 'masterid': 13, 'name': 'another'}),
        ])

    @defer.inlineCallbacks
    def test__masterDeactivated(self):
        # this method just calls updateBuilderList, so test that.
        self.rtype.updateBuilderList = mock.Mock(
            spec=self.rtype.updateBuilderList)
        yield self.rtype._masterDeactivated(10)
        self.rtype.updateBuilderList.assert_called_with(10, [])
