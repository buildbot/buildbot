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

class TestBuildsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['builds', 'buildrequests', 'buildsets',
                'sourcestamps', 'patches' ])

        def finish_setup(_):
            self.db.builds = builds.BuildsConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # common sample data

    background_data = [
        fakedb.SourceStamp(id=27, revision='abcd'),
        fakedb.Buildset(id=20, sourcestampid=27),
        fakedb.Buildset(id=30, sourcestampid=27),
        fakedb.BuildRequest(id=41, buildsetid=20, buildername='b1'),
        fakedb.BuildRequest(id=42, buildsetid=30, buildername='b1'),
    ]

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
                self.db.builds.addBuild(brid=41, number=119, _reactor=clock))
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

