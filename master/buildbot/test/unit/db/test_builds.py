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

import datetime

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import resultspec
from buildbot.db import builds
from buildbot.db.builds import BuildModel
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import UTC
from buildbot.util import epoch2datetime

TIME1 = 1304262222
TIME2 = 1304262223
TIME3 = 1304262224
TIME4 = 1304262235
CREATED_AT = 927845299


class Tests(TestReactorMixin, unittest.TestCase):
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
        fakedb.Build(
            id=50,
            buildrequestid=42,
            number=5,
            masterid=88,
            builderid=77,
            workerid=13,
            state_string="build 5",
            started_at=TIME1,
        ),
        fakedb.Build(
            id=51,
            buildrequestid=41,
            number=6,
            masterid=88,
            builderid=88,
            workerid=13,
            state_string="build 6",
            started_at=TIME2,
        ),
        fakedb.Build(
            id=52,
            buildrequestid=42,
            number=7,
            masterid=88,
            builderid=77,
            workerid=12,
            state_string="build 7",
            started_at=TIME3,
            complete_at=TIME4,
            results=5,
        ),
    ]

    threeBdicts = {
        50: builds.BuildModel(
            id=50,
            buildrequestid=42,
            builderid=77,
            masterid=88,
            number=5,
            workerid=13,
            started_at=epoch2datetime(TIME1),
            complete_at=None,
            locks_duration_s=0,
            state_string="build 5",
            results=None,
        ),
        51: builds.BuildModel(
            id=51,
            buildrequestid=41,
            builderid=88,
            masterid=88,
            number=6,
            workerid=13,
            started_at=epoch2datetime(TIME2),
            complete_at=None,
            locks_duration_s=0,
            state_string="build 6",
            results=None,
        ),
        52: builds.BuildModel(
            id=52,
            buildrequestid=42,
            builderid=77,
            masterid=88,
            number=7,
            workerid=12,
            started_at=epoch2datetime(TIME3),
            complete_at=epoch2datetime(TIME4),
            locks_duration_s=0,
            state_string="build 7",
            results=5,
        ),
    }

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db

    @defer.inlineCallbacks
    def test_getBuild(self):
        yield self.db.insert_test_data([*self.backgroundData, self.threeBuilds[0]])
        bdict = yield self.db.builds.getBuild(50)
        self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            bdict,
            builds.BuildModel(
                id=50,
                number=5,
                buildrequestid=42,
                masterid=88,
                builderid=77,
                workerid=13,
                started_at=epoch2datetime(TIME1),
                complete_at=None,
                locks_duration_s=0,
                state_string='build 5',
                results=None,
            ),
        )

    @defer.inlineCallbacks
    def test_getBuild_missing(self):
        bdict = yield self.db.builds.getBuild(50)
        self.assertEqual(bdict, None)

    @defer.inlineCallbacks
    def test_getBuildByNumber(self):
        yield self.db.insert_test_data([*self.backgroundData, self.threeBuilds[0]])
        bdict = yield self.db.builds.getBuildByNumber(builderid=77, number=5)
        self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(bdict.id, 50)

    @defer.inlineCallbacks
    def test_getBuilds(self):
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds()
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            sorted(bdicts, key=lambda bd: bd.id),
            [self.threeBdicts[50], self.threeBdicts[51], self.threeBdicts[52]],
        )

    @defer.inlineCallbacks
    def test_getBuilds_builderid(self):
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(builderid=88)
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd.id), [self.threeBdicts[51]])

    @defer.inlineCallbacks
    def test_getBuilds_buildrequestid(self):
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(buildrequestid=42)
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            sorted(bdicts, key=lambda bd: bd.id), [self.threeBdicts[50], self.threeBdicts[52]]
        )

    @defer.inlineCallbacks
    def test_getBuilds_workerid(self):
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(workerid=13)
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            sorted(bdicts, key=lambda bd: bd.id), [self.threeBdicts[50], self.threeBdicts[51]]
        )

    @defer.inlineCallbacks
    def do_test_getBuildsForChange(self, rows, changeid, expected):
        yield self.db.insert_test_data(rows)

        builds = yield self.db.builds.getBuildsForChange(changeid)

        self.assertEqual(sorted(builds), sorted(expected))

    def test_getBuildsForChange_OneCodebase(self):
        rows = [
            fakedb.Master(id=88, name="bar"),
            fakedb.Worker(id=13, name='one'),
            fakedb.Builder(id=77, name='A'),
            fakedb.SourceStamp(id=234, created_at=CREATED_AT, revision="aaa"),
            fakedb.Change(changeid=14, codebase='A', sourcestampid=234),
            fakedb.Buildset(id=30, reason='foo', submitted_at=1300305712, results=1),
            fakedb.BuildsetSourceStamp(sourcestampid=234, buildsetid=30),
            fakedb.BuildRequest(
                id=19,
                buildsetid=30,
                builderid=77,
                priority=13,
                submitted_at=1300305712,
                results=1,
                complete=0,
                complete_at=None,
            ),
            fakedb.Build(
                id=50,
                buildrequestid=19,
                number=5,
                masterid=88,
                builderid=77,
                state_string="test",
                workerid=13,
                started_at=1304262222,
                results=1,
            ),
        ]

        expected = [
            builds.BuildModel(
                id=50,
                number=5,
                builderid=77,
                buildrequestid=19,
                workerid=13,
                masterid=88,
                started_at=epoch2datetime(1304262222),
                complete_at=None,
                locks_duration_s=0,
                state_string='test',
                results=1,
            ),
        ]

        return self.do_test_getBuildsForChange(rows, 14, expected)

    @defer.inlineCallbacks
    def test_getBuilds_complete(self):
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(complete=True)
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd.id), [self.threeBdicts[52]])

    @defer.inlineCallbacks
    def test_addBuild_first(self):
        self.reactor.advance(TIME1)
        yield self.db.insert_test_data(self.backgroundData)
        id, number = yield self.db.builds.addBuild(
            builderid=77, buildrequestid=41, workerid=13, masterid=88, state_string='test test2'
        )
        bdict = yield self.db.builds.getBuild(id)
        self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            bdict,
            builds.BuildModel(
                buildrequestid=41,
                builderid=77,
                id=id,
                masterid=88,
                number=number,
                workerid=13,
                started_at=epoch2datetime(TIME1),
                complete_at=None,
                locks_duration_s=0,
                state_string="test test2",
                results=None,
            ),
        )

    @defer.inlineCallbacks
    def test_addBuild_existing(self):
        self.reactor.advance(TIME1)
        yield self.db.insert_test_data([
            *self.backgroundData,
            fakedb.Build(number=10, buildrequestid=41, builderid=77, masterid=88, workerid=13),
        ])
        id, number = yield self.db.builds.addBuild(
            builderid=77, buildrequestid=41, workerid=13, masterid=88, state_string='test test2'
        )
        bdict = yield self.db.builds.getBuild(id)
        self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(number, 11)
        self.assertEqual(
            bdict,
            builds.BuildModel(
                buildrequestid=41,
                builderid=77,
                id=id,
                masterid=88,
                number=number,
                workerid=13,
                started_at=epoch2datetime(TIME1),
                complete_at=None,
                locks_duration_s=0,
                state_string="test test2",
                results=None,
            ),
        )

    @defer.inlineCallbacks
    def test_setBuildStateString(self):
        yield self.db.insert_test_data([*self.backgroundData, self.threeBuilds[0]])
        yield self.db.builds.setBuildStateString(buildid=50, state_string='test test2')
        bdict = yield self.db.builds.getBuild(50)
        self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            bdict,
            builds.BuildModel(
                id=50,
                number=5,
                buildrequestid=42,
                masterid=88,
                builderid=77,
                workerid=13,
                started_at=epoch2datetime(TIME1),
                complete_at=None,
                locks_duration_s=0,
                state_string='test test2',
                results=None,
            ),
        )

    @defer.inlineCallbacks
    def test_add_build_locks_duration(self):
        yield self.db.insert_test_data([*self.backgroundData, self.threeBuilds[0]])
        yield self.db.builds.add_build_locks_duration(buildid=50, duration_s=12)
        bdict = yield self.db.builds.getBuild(50)
        self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            bdict,
            builds.BuildModel(
                id=50,
                number=5,
                buildrequestid=42,
                masterid=88,
                builderid=77,
                workerid=13,
                started_at=epoch2datetime(TIME1),
                complete_at=None,
                locks_duration_s=12,
                state_string="build 5",
                results=None,
            ),
        )

    @defer.inlineCallbacks
    def test_finishBuild(self):
        self.reactor.advance(TIME4)
        yield self.db.insert_test_data([*self.backgroundData, self.threeBuilds[0]])
        yield self.db.builds.finishBuild(buildid=50, results=7)
        bdict = yield self.db.builds.getBuild(50)
        self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            bdict,
            builds.BuildModel(
                id=50,
                number=5,
                buildrequestid=42,
                masterid=88,
                builderid=77,
                workerid=13,
                started_at=epoch2datetime(TIME1),
                complete_at=epoch2datetime(TIME4),
                locks_duration_s=0,
                state_string='build 5',
                results=7,
            ),
        )

    @defer.inlineCallbacks
    def testgetBuildPropertiesEmpty(self):
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        for buildid in (50, 51, 52):
            props = yield self.db.builds.getBuildProperties(buildid)
            self.assertEqual(0, len(props))

    @defer.inlineCallbacks
    def test_testgetBuildProperties_resultSpecFilter(self):
        rs = resultspec.ResultSpec(filters=[resultspec.Filter('name', 'eq', ["prop", "prop2"])])
        rs.fieldMapping = {'name': 'build_properties.name'}
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        yield self.db.builds.setBuildProperty(50, 'prop', 42, 'test')
        yield self.db.builds.setBuildProperty(50, 'prop2', 43, 'test')
        yield self.db.builds.setBuildProperty(50, 'prop3', 44, 'test')
        props = yield self.db.builds.getBuildProperties(50, resultSpec=rs)
        self.assertEqual(props, {'prop': (42, 'test'), 'prop2': (43, 'test')})

        rs = resultspec.ResultSpec(filters=[resultspec.Filter('name', 'eq', ["prop"])])
        rs.fieldMapping = {'name': 'build_properties.name'}
        props = yield self.db.builds.getBuildProperties(50, resultSpec=rs)
        self.assertEqual(
            props,
            {
                'prop': (42, 'test'),
            },
        )

    @defer.inlineCallbacks
    def testsetandgetProperties(self):
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        yield self.db.builds.setBuildProperty(50, 'prop', 42, 'test')
        props = yield self.db.builds.getBuildProperties(50)
        self.assertEqual(props, {'prop': (42, 'test')})

    @defer.inlineCallbacks
    def testsetgetsetProperties(self):
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
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

    @defer.inlineCallbacks
    def test_addBuild_existing_race(self):
        self.reactor.advance(TIME1)
        yield self.db.insert_test_data(self.backgroundData)

        # add new builds at *just* the wrong time, repeatedly
        numbers = list(range(1, 8))

        def raceHook(conn):
            if not numbers:
                return
            conn.execute(
                self.db.model.builds.insert(),
                {
                    "number": numbers.pop(0),
                    "buildrequestid": 41,
                    "masterid": 88,
                    "workerid": 13,
                    "builderid": 77,
                    "started_at": TIME1,
                    "locks_duration_s": 0,
                    "state_string": "hi",
                },
            )
            conn.commit()

        id, number = yield self.db.builds.addBuild(
            builderid=77,
            buildrequestid=41,
            workerid=13,
            masterid=88,
            state_string='test test2',
            _race_hook=raceHook,
        )
        bdict = yield self.db.builds.getBuild(id)
        self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(number, 8)
        self.assertEqual(
            bdict,
            builds.BuildModel(
                buildrequestid=41,
                builderid=77,
                id=id,
                masterid=88,
                number=number,
                workerid=13,
                started_at=epoch2datetime(TIME1),
                complete_at=None,
                locks_duration_s=0,
                state_string="test test2",
                results=None,
            ),
        )

    @defer.inlineCallbacks
    def test_getBuilds_resultSpecFilter(self):
        rs = resultspec.ResultSpec(filters=[resultspec.Filter('complete_at', 'ne', [None])])
        rs.fieldMapping = {'complete_at': 'builds.complete_at'}
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(resultSpec=rs)
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd.id), [self.threeBdicts[52]])

    @defer.inlineCallbacks
    def test_getBuilds_resultSpecOrder(self):
        rs = resultspec.ResultSpec(order=['-started_at'])
        rs.fieldMapping = {'started_at': 'builds.started_at'}
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(resultSpec=rs)

        # applying the spec in the db layer should have emptied the order in
        # resultSpec
        self.assertEqual(rs.order, None)
        # assert applying the same order at the data layer will give the same
        # results
        rs = resultspec.ResultSpec(order=['-started_at'])
        ordered_bdicts = rs.apply(bdicts)
        self.assertEqual(ordered_bdicts, bdicts)

        # assert applying an opposite order at the data layer will give different
        # results
        rs = resultspec.ResultSpec(order=['started_at'])
        ordered_bdicts = rs.apply(bdicts)
        self.assertNotEqual(ordered_bdicts, bdicts)

    @defer.inlineCallbacks
    def test_getBuilds_limit(self):
        rs = resultspec.ResultSpec(order=['-started_at'], limit=1, offset=2)
        rs.fieldMapping = {'started_at': 'builds.started_at'}
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
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

    @defer.inlineCallbacks
    def test_getBuilds_resultSpecFilterEqTwoValues(self):
        rs = resultspec.ResultSpec(filters=[resultspec.Filter('number', 'eq', [6, 7])])
        rs.fieldMapping = {'number': 'builds.number'}
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(resultSpec=rs)
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            sorted(bdicts, key=lambda bd: bd.id), [self.threeBdicts[51], self.threeBdicts[52]]
        )

    @defer.inlineCallbacks
    def test_getBuilds_resultSpecFilterNeTwoValues(self):
        rs = resultspec.ResultSpec(filters=[resultspec.Filter('number', 'ne', [6, 7])])
        rs.fieldMapping = {'number': 'builds.number'}
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(resultSpec=rs)
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd.id), [self.threeBdicts[50]])

    @defer.inlineCallbacks
    def test_getBuilds_resultSpecFilterContainsOneValue(self):
        rs = resultspec.ResultSpec(filters=[resultspec.Filter('state_string', 'contains', ['7'])])
        rs.fieldMapping = {'state_string': 'builds.state_string'}
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(resultSpec=rs)
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(sorted(bdicts, key=lambda bd: bd.id), [self.threeBdicts[52]])

    @defer.inlineCallbacks
    def test_getBuilds_resultSpecFilterContainsTwoValues(self):
        rs = resultspec.ResultSpec(
            filters=[resultspec.Filter('state_string', 'contains', ['build 5', 'build 6'])]
        )
        rs.fieldMapping = {'state_string': 'builds.state_string'}
        yield self.db.insert_test_data(self.backgroundData + self.threeBuilds)
        bdicts = yield self.db.builds.getBuilds(resultSpec=rs)
        for bdict in bdicts:
            self.assertIsInstance(bdict, builds.BuildModel)
        self.assertEqual(
            sorted(bdicts, key=lambda bd: bd.id), [self.threeBdicts[50], self.threeBdicts[51]]
        )

    @defer.inlineCallbacks
    def test_get_triggered_builds(self):
        yield self.db.insert_test_data(
            self.backgroundData
            + self.threeBuilds
            + [
                fakedb.Buildset(id=1000, parent_buildid=51),
                fakedb.BuildRequest(id=1100, buildsetid=1000, builderid=77),
                fakedb.BuildRequest(id=1101, buildsetid=1000, builderid=77),
                fakedb.Build(id=1200, buildrequestid=1100, masterid=88, builderid=77, workerid=13),
                fakedb.Build(id=1201, buildrequestid=1101, masterid=88, builderid=77, workerid=13),
            ]
        )

        builds = yield self.db.builds.get_triggered_builds(50)
        self.assertEqual(builds, [])

        builds = yield self.db.builds.get_triggered_builds(51)
        self.assertEqual(
            builds,
            [
                BuildModel(
                    id=1200,
                    number=1200,
                    builderid=77,
                    buildrequestid=1100,
                    workerid=13,
                    masterid=88,
                    started_at=datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=UTC),
                    complete_at=None,
                    locks_duration_s=0,
                    state_string='test',
                    results=None,
                ),
                BuildModel(
                    id=1201,
                    number=1201,
                    builderid=77,
                    buildrequestid=1101,
                    workerid=13,
                    masterid=88,
                    started_at=datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=UTC),
                    complete_at=None,
                    locks_duration_s=0,
                    state_string='test',
                    results=None,
                ),
            ],
        )
