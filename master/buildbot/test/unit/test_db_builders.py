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

from buildbot.db import builders
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from twisted.internet import defer
from twisted.trial import unittest


class Tests(interfaces.InterfaceTests):

    # common sample data

    builder_row = [
        fakedb.Builder(id=7, name="some:builder", category="devel"),
    ]

    # tests

    def test_signature_findBuilderId(self):
        @self.assertArgSpecMatches(self.db.builders.findBuilderId)
        def findBuilderId(self, name, category=''):
            pass

    def test_signature_addBuilderMaster(self):
        @self.assertArgSpecMatches(self.db.builders.addBuilderMaster)
        def addBuilderMaster(self, builderid=None, masterid=None):
            pass

    def test_signature_removeBuilderMaster(self):
        @self.assertArgSpecMatches(self.db.builders.removeBuilderMaster)
        def removeBuilderMaster(self, builderid=None, masterid=None):
            pass

    def test_signature_getBuilder(self):
        @self.assertArgSpecMatches(self.db.builders.getBuilder)
        def getBuilder(self, builderid):
            pass

    def test_signature_getBuilders(self):
        @self.assertArgSpecMatches(self.db.builders.getBuilders)
        def getBuilders(self, masterid=None):
            pass

    @defer.inlineCallbacks
    def test_findBuilderId_new(self):
        id = yield self.db.builders.findBuilderId('some:builder')
        builderdict = yield self.db.builders.getBuilder(id)
        self.assertEqual(builderdict,
                         dict(id=id, name='some:builder', category='',
                              masterids=[]))

    @defer.inlineCallbacks
    def test_findBuilderId_exists(self):
        yield self.insertTestData([
            fakedb.Builder(id=7, name='some:builder',category='devel'),
        ])
        id = yield self.db.builders.findBuilderId('some:builder')
        self.assertEqual(id, 7)

    @defer.inlineCallbacks
    def test_addBuilderMaster(self):
        yield self.insertTestData([
            fakedb.Builder(id=7, category='devel'),
            fakedb.Master(id=9, name='abc'),
            fakedb.Master(id=10, name='def'),
            fakedb.BuilderMaster(builderid=7, masterid=10),
        ])
        x=yield self.db.builders.addBuilderMaster(builderid=7, masterid=9)
        builderdict = yield self.db.builders.getBuilder(7)
        validation.verifyDbDict(self, 'builderdict', builderdict)
        self.assertEqual(builderdict,
                         dict(id=7, name='some:builder', category='devel',
                              masterids=[9, 10]))

    @defer.inlineCallbacks
    def test_addBuilderMaster_already_present(self):
        yield self.insertTestData([
            fakedb.Builder(id=7, category='devel'),
            fakedb.Master(id=9, name='abc'),
            fakedb.Master(id=10, name='def'),
            fakedb.BuilderMaster(builderid=7, masterid=9),
        ])
        yield self.db.builders.addBuilderMaster(builderid=7, masterid=9)
        builderdict = yield self.db.builders.getBuilder(7)
        validation.verifyDbDict(self, 'builderdict', builderdict)
        self.assertEqual(builderdict,
                         dict(id=7, name='some:builder', category='devel',
                              masterids=[9]))

    @defer.inlineCallbacks
    def test_removeBuilderMaster(self):
        yield self.insertTestData([
            fakedb.Builder(id=7, category='devel'),
            fakedb.Master(id=9, name='some:master'),
            fakedb.Master(id=10, name='other:master'),
            fakedb.BuilderMaster(builderid=7, masterid=9),
            fakedb.BuilderMaster(builderid=7, masterid=10),
        ])
        yield self.db.builders.removeBuilderMaster(builderid=7, masterid=9)
        builderdict = yield self.db.builders.getBuilder(7)
        validation.verifyDbDict(self, 'builderdict', builderdict)
        self.assertEqual(builderdict,
                         dict(id=7, name='some:builder', category='devel',
                              masterids=[10]))

    @defer.inlineCallbacks
    def test_getBuilder_no_masters(self):
        yield self.insertTestData([
            fakedb.Builder(id=7, name='some:builder',category='devel'),
        ])
        builderdict = yield self.db.builders.getBuilder(7)
        validation.verifyDbDict(self, 'builderdict', builderdict)
        self.assertEqual(builderdict,
                         dict(id=7, name='some:builder', category='devel',
                              masterids=[]))

    @defer.inlineCallbacks
    def test_getBuilder_with_masters(self):
        yield self.insertTestData([
            fakedb.Builder(id=7, name='some:builder', category='devel'),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=7, masterid=3),
            fakedb.BuilderMaster(builderid=7, masterid=4),
        ])
        builderdict = yield self.db.builders.getBuilder(7)
        validation.verifyDbDict(self, 'builderdict', builderdict)
        self.assertEqual(builderdict,
                         dict(id=7, name='some:builder', category='devel',
                              masterids=[3, 4]))

    @defer.inlineCallbacks
    def test_getBuilder_missing(self):
        builderdict = yield self.db.builders.getBuilder(7)
        self.assertEqual(builderdict, None)

    @defer.inlineCallbacks
    def test_getBuilders(self):
        yield self.insertTestData([
            fakedb.Builder(id=7, name='some:builder', category='devel'),
            fakedb.Builder(id=8, name='other:builder', category='stable'),
            fakedb.Builder(id=9, name='third:builder', category='public'),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=7, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=4),
        ])
        builderlist = yield self.db.builders.getBuilders()
        for builderdict in builderlist:
            validation.verifyDbDict(self, 'builderdict', builderdict)
        self.assertEqual(sorted(builderlist), sorted([
            dict(id=7, name='some:builder', category='devel', masterids=[3]),
            dict(id=8, name='other:builder', category='stable', masterids=[3, 4]),
            dict(id=9, name='third:builder', category='public', masterids=[]),
        ]))

    @defer.inlineCallbacks
    def test_getBuilders_masterid(self):
        yield self.insertTestData([
            fakedb.Builder(id=7, name='some:builder', category='devel'),
            fakedb.Builder(id=8, name='other:builder', category='stable'),
            fakedb.Builder(id=9, name='third:builder'),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=7, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=4),
        ])
        builderlist = yield self.db.builders.getBuilders(masterid=3)
        for builderdict in builderlist:
            validation.verifyDbDict(self, 'builderdict', builderdict)
        self.assertEqual(sorted(builderlist), sorted([
            dict(id=7, name='some:builder', category='devel', masterids=[3]),
            dict(id=8, name='other:builder', category='stable',
                 masterids=[3, 4]),
        ]))

    @defer.inlineCallbacks
    def test_getBuilders_empty(self):
        builderlist = yield self.db.builders.getBuilders()
        self.assertEqual(sorted(builderlist), [])


class RealTests(Tests):

    # tests that only "real" implementations will pass

    pass


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.db = fakedb.FakeDBConnector(self.master, self)
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['builders', 'masters', 'builder_masters'])

        @d.addCallback
        def finish_setup(_):
            self.db.builders = builders.BuildersConnectorComponent(self.db)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
