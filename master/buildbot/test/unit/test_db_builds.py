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
from twisted.internet import defer, task
from buildbot.db import builds
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb
from buildbot.util import epoch2datetime
from buildbot.status.results import SUCCESS

class TestBuildsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    SUBMITTED_AT_EPOCH = 298297875
    COMPLETE_AT_EPOCH = 329920275

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['builds', 'buildrequests', 'buildsets',
                'sourcestamps', 'sourcestampsets', 'patches' ])

        def finish_setup(_):
            self.db.builds = builds.BuildsConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # common sample data

    background_data = [
        fakedb.SourceStampSet(id=27),
        fakedb.SourceStamp(id=27, sourcestampsetid=27, revision='abcd'),
        fakedb.Buildset(id=20, sourcestampsetid=27),
        fakedb.Buildset(id=30, sourcestampsetid=27),
        fakedb.BuildRequest(id=41, buildsetid=20, buildername='b1'),
        fakedb.BuildRequest(id=42, buildsetid=30, buildername='b1'),
    ]

    last_builds = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder",
                                       complete=1, results=0,
                                       submitted_at=SUBMITTED_AT_EPOCH,
                                       complete_at=COMPLETE_AT_EPOCH),
                   fakedb.Buildset(id=1, sourcestampsetid=1),
                   fakedb.SourceStampSet(id=1),
                   fakedb.SourceStamp(id=1, revision='a', codebase='1',
                                      sourcestampsetid=1, branch='master', repository='z'),
                   fakedb.SourceStamp(id=2, revision='b', codebase='2', sourcestampsetid=1,
                                      branch='staging', repository='w'),
                   fakedb.Build(id=1, number=4, brid=1, start_time=SUBMITTED_AT_EPOCH,
                                finish_time=COMPLETE_AT_EPOCH, slavename='slave-01')]

    # tests

    def test_getBuild(self):
        d = self.insertTestData(self.background_data + [
            fakedb.Build(id=50, brid=42, number=5, start_time=1304262222),
        ])
        d.addCallback(lambda _ :
                self.db.builds.getBuild(50))
        def check(bdict):
            self.assertEqual(bdict, dict(bid=50, number=5, brid=42,
                start_time=epoch2datetime(1304262222), finish_time=None))
        d.addCallback(check)
        return d

    def test_getBuild_missing(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
                self.db.builds.getBuild(50))
        def check(bdict):
            self.assertEqual(bdict, None)
        d.addCallback(check)
        return d

    def test_getBuildsForRequest(self):
        d = self.insertTestData(self.background_data + [
            fakedb.Build(id=50, brid=42, number=5, start_time=1304262222),
            fakedb.Build(id=51, brid=41, number=6, start_time=1304262223),
            fakedb.Build(id=52, brid=42, number=7, start_time=1304262224,
                                                  finish_time=1304262235),
        ])
        d.addCallback(lambda _ :
                self.db.builds.getBuildsForRequest(42))
        def check(bdicts):
            self.assertEqual(sorted(bdicts), sorted([
                dict(bid=50, number=5, brid=42,
                    start_time=epoch2datetime(1304262222), finish_time=None),
                dict(bid=52, number=7, brid=42,
                    start_time=epoch2datetime(1304262224),
                    finish_time=epoch2datetime(1304262235)),
            ]))
        d.addCallback(check)
        return d

    def test_addBuild(self):
        clock = task.Clock()
        clock.advance(1302222222)
        d = self.insertTestData(self.background_data)
        d.addCallback(lambda _ :
                self.db.builds.addBuild(brid=41, number=119, slavename="slave-01", _reactor=clock))
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.builds.select())
                rows = [ (row.brid, row.number, row.start_time,
                          row.finish_time) for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ (41, 119, 1302222222, None) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_finishBuilds(self):
        clock = task.Clock()
        clock.advance(1305555555)

        d = self.insertTestData(self.background_data + [
            fakedb.Build(id=50, brid=41, number=5, start_time=1304262222),
            fakedb.Build(id=51, brid=42, number=5, start_time=1304262222),
            fakedb.Build(id=52, brid=42, number=6, start_time=1304262222),
        ])
        d.addCallback(lambda _ :
                self.db.builds.finishBuilds([50,51], _reactor=clock))
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.builds.select())
                rows = [ (row.id, row.brid, row.number, row.start_time,
                          row.finish_time) for row in r.fetchall() ]
                self.assertEqual(sorted(rows), [
                    (50, 41, 5, 1304262222, 1305555555),
                    (51, 42, 5, 1304262222, 1305555555),
                    (52, 42, 6, 1304262222, None),
                ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_finishBuilds_big(self):
        clock = task.Clock()
        clock.advance(1305555555)

        d = self.insertTestData(self.background_data + [
            fakedb.Build(id=nn, brid=41, number=nn, start_time=1304262222)
            for nn in xrange(50,200)
        ])
        d.addCallback(lambda _ :
                self.db.builds.finishBuilds(range(50,200), _reactor=clock))
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.builds.select())
                rows = [ (row.id, row.brid, row.number, row.start_time,
                          row.finish_time) for row in r.fetchall() ]
                self.assertEqual(sorted(rows), [
                    (nn, 41, nn, 1304262222, 1305555555)
                    for nn in xrange(50,200)
                ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersCodeBasesFound(self):
        yield  self.insertTestData(self.last_builds)

        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'master'},
                          {'b_codebase': '2', 'b_branch': 'staging'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter, num_builds=1)

        self.assertEqual(lastBuildNumber, [4])

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersCodeBasesNotFound(self):
        yield  self.insertTestData(self.last_builds)

        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'development'},
                          {'b_codebase': '2', 'b_branch': 'qa'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter, num_builds=1)

        self.assertEqual(lastBuildNumber, [])

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersOneFilter(self):
        yield  self.insertTestData(self.last_builds)

        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'master'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter, num_builds=1)

        self.assertEqual(lastBuildNumber, [4])

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersMultipleBuilds(self):
        builds = [fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder",
                                       complete=1, results=0,
                                       submitted_at=self.SUBMITTED_AT_EPOCH,
                                       complete_at=self.COMPLETE_AT_EPOCH),
                   fakedb.Buildset(id=2, sourcestampsetid=2),
                   fakedb.SourceStampSet(id=2),
                   fakedb.SourceStamp(id=3, revision='a', codebase='1',
                                      sourcestampsetid=2, branch='master', repository='z'),
                   fakedb.SourceStamp(id=4, revision='b', codebase='4', sourcestampsetid=2,
                                      branch='development', repository='w'),
                   fakedb.Build(id=2, number=3, brid=2, start_time=self.SUBMITTED_AT_EPOCH,
                                finish_time=self.COMPLETE_AT_EPOCH)]
        yield  self.insertTestData(self.last_builds + builds)

        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'master'},
                          {'b_codebase': '2', 'b_branch': 'qa'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter, num_builds=4)

        self.assertEqual(lastBuildNumber, [3])

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersFilterBranchResults(self):
        builds = [fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder",
                                       complete=1, results=4,
                                       submitted_at=self.SUBMITTED_AT_EPOCH,
                                       complete_at=self.COMPLETE_AT_EPOCH),
                   fakedb.Buildset(id=2, sourcestampsetid=2),
                   fakedb.SourceStampSet(id=2),
                   fakedb.SourceStamp(id=3, revision='a', codebase='1',
                                      sourcestampsetid=2, branch='master', repository='z'),
                   fakedb.SourceStamp(id=4, revision='b', codebase='4', sourcestampsetid=2,
                                      branch='development', repository='w'),
                   fakedb.Build(id=2, number=3, brid=2, start_time=self.SUBMITTED_AT_EPOCH,
                                finish_time=self.COMPLETE_AT_EPOCH)]
        yield  self.insertTestData(self.last_builds + builds)

        sourcestamps_filter = [{'b_branch': 'master'}, {'b_branch': 'qa'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter,
                                                                    results=[0],
                                                                    num_builds=4)

        self.assertEqual(lastBuildNumber, [4])

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter,
                                                                    results=[0, 4],
                                                                    num_builds=4)

        self.assertEqual(lastBuildNumber, [4, 3])

    @defer.inlineCallbacks
    def insertRecentBuilds(self):
        builds = [{'buildername': "builder",
                   'submitted_at': 1457706077,
                   'complete_at': 1457706089,
                   'revision': 'abzdewf',
                   'slavename': 'slave-02'},
                  {'buildername': "builder",
                   'submitted_at': 1457895804,
                   'complete_at': 1457895819,
                   'revision': 'zbzdewf',
                   'slavename': 'slave-01'},
                  {'buildername': "builder-01",
                   'submitted_at': 1457895804,
                   'complete_at': 1457895819,
                   'revision': 'zbzdewf',
                   'slavename': 'slave-01'},
                  {'buildername': "builder",
                   'submitted_at': self.SUBMITTED_AT_EPOCH,
                   'complete_at': self.COMPLETE_AT_EPOCH,
                   'revision': 'fwbzdeif',
                   'slavename': 'slave-01'}]

        recent_builds = []

        for idx, b in enumerate(builds):
            rowid = idx + 1
            recent_builds += [fakedb.BuildRequest(id=rowid, buildsetid=rowid, buildername=b['buildername'],
                                                 complete=1, results=SUCCESS,
                                                 submitted_at=b['submitted_at'],
                                                 complete_at=b['complete_at']),
                             fakedb.Buildset(id=rowid, sourcestampsetid=rowid),
                             fakedb.SourceStampSet(id=rowid),
                             fakedb.SourceStamp(id=rowid, revision=b['revision'], codebase='1',
                                                sourcestampsetid=rowid, branch='master', repository='z'),
                            fakedb.Build(id=rowid, number=rowid, brid=rowid,
                                         start_time=b['submitted_at'],
                                         finish_time=b['complete_at'],
                                         slavename=b['slavename'])
                             ]
        yield  self.insertTestData(recent_builds)

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersOrderByCompleted(self):
        yield self.insertRecentBuilds()

        builds = yield self.db.builds.getLastBuildsNumbers(buildername="builder")
        self.assertEquals([2, 1, 4], builds)

    @defer.inlineCallbacks
    def test_getLastsBuildsNumbersBySlave(self):
        builds = [fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder1",
                                       complete=1, results=0,
                                       submitted_at=self.SUBMITTED_AT_EPOCH,
                                       complete_at=self.COMPLETE_AT_EPOCH),
                   fakedb.Buildset(id=2, sourcestampsetid=2),
                   fakedb.SourceStampSet(id=2),
                   fakedb.SourceStamp(id=3, revision='a', codebase='1',
                                      sourcestampsetid=2, branch='master', repository='z'),
                   fakedb.SourceStamp(id=4, revision='b', codebase='4', sourcestampsetid=2,
                                      branch='development', repository='w'),
                   fakedb.Build(id=2, number=3, brid=2, start_time=self.SUBMITTED_AT_EPOCH,
                                finish_time=self.COMPLETE_AT_EPOCH, slavename='slave-01'),
                   fakedb.BuildRequest(id=3, buildsetid=2, buildername="builder2",
                                       complete=1, results=0,
                                       submitted_at=self.SUBMITTED_AT_EPOCH,
                                       complete_at=self.COMPLETE_AT_EPOCH),
                   fakedb.Build(id=3, number=5, brid=3, start_time=self.SUBMITTED_AT_EPOCH,
                                finish_time=self.COMPLETE_AT_EPOCH, slavename='slave-02')]
        yield  self.insertTestData(self.last_builds + builds)

        lastBuildNumber = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename='slave-01')
        self.assertEqual(lastBuildNumber, {'builder': [4], 'builder1': [3]})

        lastBuildNumber = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename='slave-02')
        self.assertEqual(lastBuildNumber, {'builder2': [5]})

    @defer.inlineCallbacks
    def test_getLastsBuildsNumbersBySlaveFilterResults(self):
        builds = [fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder1",
                                       complete=1, results=4,
                                       submitted_at=self.SUBMITTED_AT_EPOCH,
                                       complete_at=self.COMPLETE_AT_EPOCH),
                   fakedb.Buildset(id=2, sourcestampsetid=2),
                   fakedb.SourceStampSet(id=2),
                   fakedb.SourceStamp(id=3, revision='a', codebase='1',
                                      sourcestampsetid=2, branch='master', repository='z'),
                   fakedb.SourceStamp(id=4, revision='b', codebase='4', sourcestampsetid=2,
                                      branch='development', repository='w'),
                   fakedb.Build(id=2, number=3, brid=2, start_time=self.SUBMITTED_AT_EPOCH,
                                finish_time=self.COMPLETE_AT_EPOCH, slavename='slave-01'),
                   fakedb.BuildRequest(id=3, buildsetid=2, buildername="builder2",
                                       complete=1, results=7,
                                       submitted_at=self.SUBMITTED_AT_EPOCH,
                                       complete_at=self.COMPLETE_AT_EPOCH),
                   fakedb.Build(id=3, number=5, brid=3, start_time=self.SUBMITTED_AT_EPOCH,
                                finish_time=self.COMPLETE_AT_EPOCH, slavename='slave-02')]
        yield  self.insertTestData(self.last_builds + builds)

        lastBuildNumber = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename='slave-01', results=[0, 4])
        self.assertEqual(lastBuildNumber, {'builder': [4], 'builder1': [3]})

        lastBuildNumber = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename='slave-02', results=[7])
        self.assertEqual(lastBuildNumber, {'builder2': [5]})

    @defer.inlineCallbacks
    def test_getLastsBuildsNumbersBySlaveOrderByCompleted(self):
        yield self.insertRecentBuilds()

        builds = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename="slave-01")
        self.assertEquals(builds, {'builder-01': [3], 'builder': [2, 4]})
