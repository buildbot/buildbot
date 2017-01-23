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
from future.utils import lrange

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot.data import resultspec
from buildbot.db import builds
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import epoch2datetime

TIME1 = 1304262222
TIME2 = 1304262223
TIME3 = 1304262224
TIME4 = 1304262235


class Tests(interfaces.InterfaceTests):

    # common sample data

    backgroundData = [
        fakedb.Buildset(id=20),
        fakedb.Builder(id=77, name="b1"),
        fakedb.Builder(id=88, name="b2"),
        fakedb.BuildRequest(id=40, buildsetid=20, builderid=77),
        fakedb.BuildRequest(id=41, buildsetid=20, builderid=77),
        fakedb.BuildRequest(id=42, buildsetid=20, builderid=88),
        fakedb.Master(id=88),
        fakedb.Master(id=89, name="bar"),
        fakedb.Worker(id=13, name='wrk'),
        fakedb.Worker(id=12, name='sl2'),
    ]

    threeBuilds = [
        fakedb.Build(id=50, buildrequestid=42, number=5, masterid=88,
                     builderid=77, workerid=13, state_string="test",
                     started_at=TIME1),
        fakedb.Build(id=51, buildrequestid=41, number=6, masterid=88,
                     builderid=88, workerid=13, state_string="test",
                     started_at=TIME2),
        fakedb.Build(id=52, buildrequestid=42, number=7, masterid=88,
                     builderid=77, workerid=12, state_string="test",
                     started_at=TIME3, complete_at=TIME4, results=5),
    ]

    threeBdicts = {
        50: {'id': 50, 'buildrequestid': 42, 'builderid': 77,
             'masterid': 88, 'number': 5, 'workerid': 13,
             'started_at': epoch2datetime(TIME1),
             'complete_at': None, 'state_string': 'test',
             'results': None},
        51: {'id': 51, 'buildrequestid': 41, 'builderid': 88,
             'masterid': 88, 'number': 6, 'workerid': 13,
             'started_at': epoch2datetime(TIME2),
             'complete_at': None, 'state_string': 'test',
             'results': None},
        52: {'id': 52, 'buildrequestid': 42, 'builderid': 77,
             'masterid': 88, 'number': 7, 'workerid': 12,
             'started_at': epoch2datetime(TIME3),
             'complete_at': epoch2datetime(TIME4),
             'state_string': 'test',
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
        def getBuilds(self, builderid=None, buildrequestid=None, workerid=None,
                      complete=None, resultSpec=None):
            pass

    def test_signature_addBuild(self):
        @self.assertArgSpecMatches(self.db.builds.addBuild)
        def addBuild(self, builderid, buildrequestid, workerid, masterid,
                     state_string):
            pass

    def test_signature_setBuildStateString(self):
        @self.assertArgSpecMatches(self.db.builds.setBuildStateString)
        def setBuildStateString(self, buildid, state_string):
            pass

    def test_signature_finishBuild(self):
        @self.assertArgSpecMatches(self.db.builds.finishBuild)
        def finishBuild(self, buildid, results):
            pass

    def test_signature_getBuildProperties(self):
        @self.assertArgSpecMatches(self.db.builds.getBuildProperties)
        def getBuildProperties(self, bid):
            pass

    def test_signature_setBuildProperty(self):
        @self.assertArgSpecMatches(self.db.builds.setBuildProperty)
        def setBuildProperty(self, bid, name, value, source):
            pass

    # method tests

    @defer.inlineCallbacks
    def test_getBuild(self):
        yield self.insertTestData(self.backgroundData + [self.threeBuilds[0]])
        bdict = yield self.db.builds.getBuild(50)
        validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(bdict, dict(id=50, number=5, buildrequestid=42,
                                     masterid=88, builderid=77, workerid=13,
                                     started_at=epoch2datetime(TIME1), complete_at=None,
                                     state_string=u'test', results=None))

    @defer.inlineCallbacks
    def test_getBuild_missing(self):
        bdict = yield self.db.builds.getBuild(50)
        self.assertEqual(bdict, None)

    @defer.inlineCallbacks
    def test_getBuildByNumber(self):
        yield self.insertTestData(self.backgroundData + [self.threeBuilds[0]])
        bdict = yield self.db.builds.getBuildByNumber(builderid=77, number=5)
        validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(bdict['id'], 50)

    @defer.inlineCallbacks
    def test_getBuilds(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds()
        for bdict in bdicts:
            validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd['id']),
                         [self.threeBdicts[50], self.threeBdicts[51],
                          self.threeBdicts[52]])

    @defer.inlineCallbacks
    def test_getBuilds_builderid(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(builderid=88)
        for bdict in bdicts:
            validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd['id']),
                         [self.threeBdicts[51]])

    @defer.inlineCallbacks
    def test_getBuilds_buildrequestid(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(buildrequestid=42)
        for bdict in bdicts:
            validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd['id']),
                         [self.threeBdicts[50], self.threeBdicts[52]])

    @defer.inlineCallbacks
    def test_getBuilds_workerid(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(workerid=13)
        for bdict in bdicts:
            validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd['id']),
                         [self.threeBdicts[50], self.threeBdicts[51]])

    @defer.inlineCallbacks
    def test_getBuilds_complete(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(complete=True)
        for bdict in bdicts:
            validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd['id']),
                         [self.threeBdicts[52]])

    @defer.inlineCallbacks
    def test_addBuild_first(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData)
        id, number = yield self.db.builds.addBuild(builderid=77,
                                                   buildrequestid=41, workerid=13, masterid=88,
                                                   state_string=u'test test2', _reactor=clock)
        bdict = yield self.db.builds.getBuild(id)
        validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(bdict, {'buildrequestid': 41, 'builderid': 77,
                                 'id': id, 'masterid': 88, 'number': number, 'workerid': 13,
                                 'started_at': epoch2datetime(TIME1),
                                 'complete_at': None, 'state_string': u'test test2',
                                 'results': None})

    @defer.inlineCallbacks
    def test_addBuild_existing(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData + [
            fakedb.Build(number=10, buildrequestid=41, builderid=77,
                         masterid=88, workerid=13),
        ])
        id, number = yield self.db.builds.addBuild(builderid=77,
                                                   buildrequestid=41, workerid=13, masterid=88,
                                                   state_string=u'test test2', _reactor=clock)
        bdict = yield self.db.builds.getBuild(id)
        validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(number, 11)
        self.assertEqual(bdict, {'buildrequestid': 41, 'builderid': 77,
                                 'id': id, 'masterid': 88, 'number': number, 'workerid': 13,
                                 'started_at': epoch2datetime(TIME1),
                                 'complete_at': None, 'state_string': u'test test2',
                                 'results': None})

    @defer.inlineCallbacks
    def test_setBuildStateString(self):
        yield self.insertTestData(self.backgroundData + [self.threeBuilds[0]])
        yield self.db.builds.setBuildStateString(buildid=50,
                                                 state_string=u'test test2')
        bdict = yield self.db.builds.getBuild(50)
        validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(bdict, dict(id=50, number=5, buildrequestid=42,
                                     masterid=88, builderid=77, workerid=13,
                                     started_at=epoch2datetime(TIME1), complete_at=None,
                                     state_string=u'test test2', results=None))

    @defer.inlineCallbacks
    def test_finishBuild(self):
        clock = task.Clock()
        clock.advance(TIME4)
        yield self.insertTestData(self.backgroundData + [self.threeBuilds[0]])
        yield self.db.builds.finishBuild(buildid=50, results=7, _reactor=clock)
        bdict = yield self.db.builds.getBuild(50)
        validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(bdict, dict(id=50, number=5, buildrequestid=42,
                                     masterid=88, builderid=77, workerid=13,
                                     started_at=epoch2datetime(TIME1),
                                     complete_at=epoch2datetime(TIME4),
                                     state_string=u'test',
                                     results=7))

    @defer.inlineCallbacks
    def testgetBuildPropertiesEmpty(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        for buildid in (50, 51, 52):
            props = yield self.db.builds.getBuildProperties(buildid)
            self.assertEqual(0, len(props))

    @defer.inlineCallbacks
    def testsetandgetProperties(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        yield self.db.builds.setBuildProperty(50, 'prop', 42, 'test')
        props = yield self.db.builds.getBuildProperties(50)
        self.assertEqual(props, {'prop': (42, 'test')})

    @defer.inlineCallbacks
    def testsetgetsetProperties(self):
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        props = yield self.db.builds.getBuildProperties(50)
        self.assertEqual(props, {})
        yield self.db.builds.setBuildProperty(50, 'prop', 42, 'test')
        props = yield self.db.builds.getBuildProperties(50)
        self.assertEqual(props, {'prop': (42, 'test')})
        # set a new value
        yield self.db.builds.setBuildProperty(50, 'prop', 45, 'test')
        props = yield self.db.builds.getBuildProperties(50)
        self.assertEqual(props, {'prop': (45, 'test')})
        # set a new source
        yield self.db.builds.setBuildProperty(50, 'prop', 45, 'test_source')
        props = yield self.db.builds.getBuildProperties(50)
        self.assertEqual(props, {'prop': (45, 'test_source')})
        # set the same
        yield self.db.builds.setBuildProperty(50, 'prop', 45, 'test_source')
        props = yield self.db.builds.getBuildProperties(50)
        self.assertEqual(props, {'prop': (45, 'test_source')})


class RealTests(Tests):

    @defer.inlineCallbacks
    def test_addBuild_existing_race(self):
        clock = task.Clock()
        clock.advance(TIME1)
        yield self.insertTestData(self.backgroundData)

        # add new builds at *just* the wrong time, repeatedly
        numbers = lrange(1, 8)

        def raceHook(conn):
            if not numbers:
                return
            conn.execute(self.db.model.builds.insert(),
                         {'number': numbers.pop(0), 'buildrequestid': 41,
                          'masterid': 88, 'workerid': 13, 'builderid': 77,
                          'started_at': TIME1, 'state_string': "hi"})

        id, number = yield self.db.builds.addBuild(builderid=77,
                                                   buildrequestid=41, workerid=13, masterid=88,
                                                   state_string=u'test test2', _reactor=clock,
                                                   _race_hook=raceHook)
        bdict = yield self.db.builds.getBuild(id)
        validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(number, 8)
        self.assertEqual(bdict, {'buildrequestid': 41, 'builderid': 77,
                                 'id': id, 'masterid': 88, 'number': number, 'workerid': 13,
                                 'started_at': epoch2datetime(TIME1),
                                 'complete_at': None, 'state_string': u'test test2',
                                 'results': None})

    @defer.inlineCallbacks
    def test_getBuilds_resultSpecFilter(self):
        rs = resultspec.ResultSpec(
            filters=[resultspec.Filter('complete_at', 'ne', [None])])
        rs.fieldMapping = {'complete_at': 'builds.complete_at'}
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(resultSpec=rs)
        for bdict in bdicts:
            validation.verifyDbDict(self, 'dbbuilddict', bdict)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd['id']),
                         [self.threeBdicts[52]])

    @defer.inlineCallbacks
    def test_getBuilds_resultSpecOrder(self):
        rs = resultspec.ResultSpec(order=['-started_at'])
        rs.fieldMapping = {'started_at': 'builds.started_at'}
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(resultSpec=rs)

        # applying the spec in the db layer should have emptied the order in
        # resultSpec
        self.assertEqual(rs.order, None)
        # assert applying the same order at the data layer will give the same
        # results
        rs = resultspec.ResultSpec(order=['-started_at'])
        ordered_bdicts = rs.apply(bdicts)
        self.assertEqual(ordered_bdicts, bdicts)

        # assert applying a oposite order at the data layer will give different
        # results
        rs = resultspec.ResultSpec(order=['started_at'])
        ordered_bdicts = rs.apply(bdicts)
        self.assertNotEqual(ordered_bdicts, bdicts)

    @defer.inlineCallbacks
    def test_getBuilds_limit(self):
        rs = resultspec.ResultSpec(order=['-started_at'], limit=1, offset=2)
        rs.fieldMapping = {'started_at': 'builds.started_at'}
        yield self.insertTestData(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(resultSpec=rs)
        # applying the spec in the db layer should have emptied the limit and
        # offset in resultSpec
        self.assertEqual(rs.limit, None)
        self.assertEqual(rs.offset, None)

        # assert applying the same filter at the data layer will give the same
        # results
        rs = resultspec.ResultSpec(order=['-started_at'], limit=1, offset=2)
        bdicts2 = yield self.db.builds.getBuilds()
        ordered_bdicts = rs.apply(bdicts2)
        self.assertEqual(ordered_bdicts, bdicts)


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['builds', 'builders', 'masters', 'buildrequests',
                         'buildsets', 'workers', 'build_properties'])

        @d.addCallback
        def finish_setup(_):
            self.db.builds = builds.BuildsConnectorComponent(self.db)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
