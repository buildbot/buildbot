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

from buildbot.db import builds
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import epoch2datetime
from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

TIME1 = 1304262222
TIME2 = 1304262223
TIME3 = 1304262224
TIME4 = 1304262235


class Tests(interfaces.InterfaceTests):

    # common sample data

    backgroundData = [
        fakedb.Buildset(id=20),
        fakedb.BuildRequest(id=41, buildsetid=20, buildername='b1'),
        fakedb.BuildRequest(id=42, buildsetid=20, buildername='b2'),
        fakedb.Builder(id=77, name="b1"),
        fakedb.Builder(id=88, name="b2"),
        fakedb.Master(id=88),
        fakedb.Buildslave(id=13, name='sl'),
    ]
    threeBuilds = [
        fakedb.Build(id=50, buildrequestid=42, number=5, masterid=88,
                     builderid=77, buildslaveid=13, state_strings_json='["test"]',
                     started_at=TIME1),
        fakedb.Build(id=51, buildrequestid=41, number=6, masterid=88,
                     builderid=88, buildslaveid=13, state_strings_json='["test"]',
                     started_at=TIME2),
        fakedb.Build(id=52, buildrequestid=42, number=7, masterid=88,
                     builderid=77, buildslaveid=13, state_strings_json='["test"]',
                     started_at=TIME3, complete_at=TIME4, results=5),
    ]

    threeBdicts = {
        50: {'id': 50, 'buildrequestid': 42, 'builderid': 77,
             'masterid': 88, 'number': 5, 'buildslaveid': 13,
             'started_at': epoch2datetime(TIME1),
             'complete_at': None, 'state_strings': [u'test'],
             'results': None},
        51: {'id': 51, 'buildrequestid': 41, 'builderid': 88,
             'masterid': 88, 'number': 6, 'buildslaveid': 13,
             'started_at': epoch2datetime(TIME2),
             'complete_at': None, 'state_strings': [u'test'],
             'results': None},
        52: {'id': 52, 'buildrequestid': 42, 'builderid': 77,
             'masterid': 88, 'number': 7, 'buildslaveid': 13,
             'started_at': epoch2datetime(TIME3),
             'complete_at': epoch2datetime(TIME4),
             'state_strings': [u'test'],
             'results': 5},
    }

    # signature tests

    def test_signature_getBuild(self):
        @self.assertArgSpecMatches(self.db.builds.getBuild)
        def getBuild(self, buildid):
            pass

    def test_signature_getBuildByNumber(self):
        @self.assertArgSpecMatches(self.db.builds.getBuildByNumber)
        def getBuild(self, builderid, number):
            pass

    def test_signature_getBuilds(self):
        @self.assertArgSpecMatches(self.db.builds.getBuilds)
        def getBuilds(self, builderid=None, buildrequestid=None):
            pass

    def test_signature_addBuild(self):
        @self.assertArgSpecMatches(self.db.builds.addBuild)
        def addBuild(self, builderid, buildrequestid, buildslaveid, masterid,
                     state_strings):
            pass

    def test_signature_setBuildStateStrings(self):
        @self.assertArgSpecMatches(self.db.builds.setBuildStateStrings)
        def setBuildStateStrings(self, buildid, state_strings):
            pass

    def test_signature_finishBuild(self):
        @self.assertArgSpecMatches(self.db.builds.finishBuild)
        def finishBuild(self, buildid, results):
            pass

    # method tests

    @defer.inlineCallbacks
    def test_getBuild(self):
        yield self.insertTestData(self.backgroundData + [self.threeBuilds[0]])
        bdict = yield self.db.builds.getBuild(50)
        validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(bdict, dict(id=50, number=5, buildrequestid=42,
                                     masterid=88, builderid=77, buildslaveid=13,
                                     started_at=epoch2datetime(TIME1), complete_at=None,
                                     state_strings=[u'test'], results=None))

    @defer.inlineCallbacks
    def test_getBuild_missing(self):
        bdict = yield self.db.builds.getBuild(50)
        self.assertEqual(bdict, None)

    @defer.inlineCallbacks
    def test_getBuildByNumber(self):
        yield self.insertTestData(self.backgroundData + [self.threeBuilds[0]])
        bdict = yield self.db.builds.getBuildByNumber(builderid=77, number=5)
        validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(bdict['id'], 50)

    @defer.inlineCallbacks
    def test_getBuilds(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds()
        for bdict in bdicts:
            validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd['id']),
                         [self.threeBdicts[50], self.threeBdicts[51],
                          self.threeBdicts[52]])

    @defer.inlineCallbacks
    def test_getBuilds_builderid(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(builderid=88)
        for bdict in bdicts:
            validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd['id']),
                         [self.threeBdicts[51]])

    @defer.inlineCallbacks
    def test_getBuilds_buildrequestid(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(buildrequestid=42)
        for bdict in bdicts:
            validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd['id']),
                         [self.threeBdicts[50], self.threeBdicts[52]])

    @defer.inlineCallbacks
    def test_addBuild_first(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData)
        id, number = yield self.db.builds.addBuild(builderid=77,
                                                   buildrequestid=41, buildslaveid=13, masterid=88,
                                                   state_strings=[u'test', u'test2'], _reactor=clock)
        bdict = yield self.db.builds.getBuild(id)
        validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(bdict, {'buildrequestid': 41, 'builderid': 77,
                                 'id': id, 'masterid': 88, 'number': number, 'buildslaveid': 13,
                                 'started_at': epoch2datetime(TIME1),
                                 'complete_at': None, 'state_strings': [u'test', u'test2'],
                                 'results': None})

    @defer.inlineCallbacks
    def test_addBuild_existing(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData + [
            fakedb.Build(number=10, buildrequestid=41, builderid=77,
                         masterid=88, buildslaveid=13),
        ])
        id, number = yield self.db.builds.addBuild(builderid=77,
                                                   buildrequestid=41, buildslaveid=13, masterid=88,
                                                   state_strings=[u'test', u'test2'], _reactor=clock)
        bdict = yield self.db.builds.getBuild(id)
        validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(number, 11)
        self.assertEqual(bdict, {'buildrequestid': 41, 'builderid': 77,
                                 'id': id, 'masterid': 88, 'number': number, 'buildslaveid': 13,
                                 'started_at': epoch2datetime(TIME1),
                                 'complete_at': None, 'state_strings': [u'test', u'test2'],
                                 'results': None})

    @defer.inlineCallbacks
    def test_setBuildStateStrings(self):
        yield self.insertTestData(self.backgroundData + [self.threeBuilds[0]])
        yield self.db.builds.setBuildStateStrings(buildid=50,
                                                  state_strings=[u'test', u'test2', u'test3'])
        bdict = yield self.db.builds.getBuild(50)
        validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(bdict, dict(id=50, number=5, buildrequestid=42,
                                     masterid=88, builderid=77, buildslaveid=13,
                                     started_at=epoch2datetime(TIME1), complete_at=None,
                                     state_strings=[u'test', u'test2', u'test3'],
                                     results=None))

    @defer.inlineCallbacks
    def test_finishBuild(self):
        clock = task.Clock()
        clock.advance(TIME4)
        yield self.insertTestData(self.backgroundData + [self.threeBuilds[0]])
        yield self.db.builds.finishBuild(buildid=50, results=7, _reactor=clock)
        bdict = yield self.db.builds.getBuild(50)
        validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(bdict, dict(id=50, number=5, buildrequestid=42,
                                     masterid=88, builderid=77, buildslaveid=13,
                                     started_at=epoch2datetime(TIME1),
                                     complete_at=epoch2datetime(TIME4),
                                     state_strings=[u'test'],
                                     results=7))


class RealTests(Tests):

    @defer.inlineCallbacks
    def test_addBuild_existing_race(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData)

        # add new builds at *just* the wrong time, repeatedly
        numbers = range(1, 8)

        def raceHook(conn):
            if not numbers:
                return
            conn.execute(self.db.model.builds.insert(),
                         {'number': numbers.pop(0), 'buildrequestid': 41,
                          'masterid': 88, 'buildslaveid': 13, 'builderid': 77,
                          'started_at': TIME1, 'state_strings_json': '["hi"]'})

        id, number = yield self.db.builds.addBuild(builderid=77,
                                                   buildrequestid=41, buildslaveid=13, masterid=88,
                                                   state_strings=[u'test', u'test2'], _reactor=clock,
                                                   _race_hook=raceHook)
        bdict = yield self.db.builds.getBuild(id)
        validation.verifyDbDict(self, 'builddict', bdict)
        self.assertEqual(number, 8)
        self.assertEqual(bdict, {'buildrequestid': 41, 'builderid': 77,
                                 'id': id, 'masterid': 88, 'number': number, 'buildslaveid': 13,
                                 'started_at': epoch2datetime(TIME1),
                                 'complete_at': None, 'state_strings': [u'test', u'test2'],
                                 'results': None})


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.db = fakedb.FakeDBConnector(self.master, self)
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['builds', 'builders', 'masters', 'buildrequests',
                         'buildsets', 'buildslaves'])

        @d.addCallback
        def finish_setup(_):
            self.db.builds = builds.BuildsConnectorComponent(self.db)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
