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

from buildbot.data import builders
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces


class BuilderEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builders.BuilderEndpoint
    resourceTypeClass = builders.Builder

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insertTestData([
            fakedb.Builder(id=1, name=u'buildera'),
            fakedb.Builder(id=2, name=u'builderb'),
            fakedb.Master(id=13),
            fakedb.BuilderMaster(id=1, builderid=2, masterid=13),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_existing(self):
        d = self.callGet(('builders', 2))

        @d.addCallback
        def check(builder):
            self.validateData(builder)
            self.assertEqual(builder['name'], u'builderb')
        return d

    def test_get_missing(self):
        d = self.callGet(('builders', 99))

        @d.addCallback
        def check(builder):
            self.assertEqual(builder, None)
        return d

    def test_get_existing_with_master(self):
        d = self.callGet(('masters', 13, 'builders', 2))

        @d.addCallback
        def check(builder):
            self.validateData(builder)
            self.assertEqual(builder['name'], u'builderb')
        return d

    def test_get_existing_with_different_master(self):
        d = self.callGet(('masters', 14, 'builders', 2))

        @d.addCallback
        def check(builder):
            self.assertEqual(builder, None)
        return d

    def test_get_missing_with_master(self):
        d = self.callGet(('masters', 13, 'builders', 99))

        @d.addCallback
        def check(builder):
            self.assertEqual(builder, None)
        return d


class BuildersEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builders.BuildersEndpoint
    resourceTypeClass = builders.Builder

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insertTestData([
            fakedb.Builder(id=1, name=u'buildera'),
            fakedb.Builder(id=2, name=u'builderb'),
            fakedb.Master(id=13),
            fakedb.BuilderMaster(id=1, builderid=2, masterid=13),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get(self):
        d = self.callGet(('builders',))

        @d.addCallback
        def check(builders):
            [self.validateData(b) for b in builders]
            self.assertEqual(sorted([b['builderid'] for b in builders]),
                             [1, 2])
        return d

    def test_get_masterid(self):
        d = self.callGet(('masters', 13, 'builders'))

        @d.addCallback
        def check(builders):
            [self.validateData(b) for b in builders]
            self.assertEqual(sorted([b['builderid'] for b in builders]),
                             [2])
        return d

    def test_get_masterid_missing(self):
        d = self.callGet(('masters', 14, 'builders'))

        @d.addCallback
        def check(builders):
            self.assertEqual(sorted([b['builderid'] for b in builders]),
                             [])
        return d


class Builder(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantDb=True, wantData=True)
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
        yield self.rtype.updateBuilderList(13, [u'somebuilder'])
        self.assertEqual(sorted((yield self.master.db.builders.getBuilders())),
                         sorted([
                             dict(id=1, masterids=[13],
                                  name='somebuilder', description=None, tags=[]),
                         ]))
        self.master.mq.assertProductions([(('builders', '1', 'started'),
                                           {'builderid': 1, 'masterid': 13, 'name': u'somebuilder'})])

        # add another
        yield self.rtype.updateBuilderList(13, [u'somebuilder', u'another'])

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
                                           {'builderid': 2, 'masterid': 13, 'name': u'another'})])

        # add one for another master
        yield self.rtype.updateBuilderList(14, [u'another'])
        self.assertEqual(sorted((yield self.master.db.builders.getBuilders()), key=builderKey),
                         sorted([
                             dict(id=1, masterids=[13],
                                  name='somebuilder', description=None, tags=[]),
                             dict(id=2, masterids=[13, 14],
                                  name='another', description=None, tags=[]),
                         ], key=builderKey))
        self.master.mq.assertProductions([(('builders', '2', 'started'),
                                           {'builderid': 2, 'masterid': 14, 'name': u'another'})])

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
             {'builderid': 1, 'masterid': 13, 'name': u'somebuilder'}),
            (('builders', '2', 'stopped'),
             {'builderid': 2, 'masterid': 13, 'name': u'another'}),
        ])

    @defer.inlineCallbacks
    def test__masterDeactivated(self):
        # this method just calls updateBuilderList, so test that.
        self.rtype.updateBuilderList = mock.Mock(
            spec=self.rtype.updateBuilderList)
        yield self.rtype._masterDeactivated(10)
        self.rtype.updateBuilderList.assert_called_with(10, [])
