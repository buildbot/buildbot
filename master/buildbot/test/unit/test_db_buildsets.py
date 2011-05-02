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
from twisted.trial import unittest
from twisted.internet import defer, task
from buildbot.db import buildsets
from buildbot.util import json, UTC
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestBuildsetsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
        self.now = 9272359
        self.clock = task.Clock()
        self.clock.advance(self.now)

        d = self.setUpConnectorComponent(
            table_names=[ 'patches', 'changes', 'sourcestamp_changes',
                'buildsets', 'buildset_properties', 'schedulers',
                'buildrequests', 'scheduler_upstream_buildsets',
                'sourcestamps' ])

        def finish_setup(_):
            self.db.buildsets = buildsets.BuildsetsConnectorComponent(self.db)
        d.addCallback(finish_setup)

        # set up a sourcestamp with id 234 for use below
        d.addCallback(lambda _ :
            self.insertTestData([ fakedb.SourceStamp(id=234) ]))

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # tests

    def test_addBuildset_simple(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.buildsets.addBuildset(ssid=234, reason='because',
                properties={}, builderNames=['bldr'], external_idstring='extid',
                _reactor=self.clock))
        def check((bsid, brids)):
            def thd(conn):
                # we should only have one brid
                self.assertEqual(len(brids), 1)

                # should see one buildset row
                r = conn.execute(self.db.model.buildsets.select())
                rows = [ (row.id, row.external_idstring, row.reason,
                          row.sourcestampid, row.complete, row.complete_at,
                          row.submitted_at, row.results) for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( bsid, 'extid', 'because', 234, 0, None, self.now, -1) ])

                # and one buildrequests row
                r = conn.execute(self.db.model.buildrequests.select())

                rows = [ (row.buildsetid, row.id, row.buildername,
                    row.priority, row.claimed_at, row.claimed_by_name,
                    row.claimed_by_incarnation, row.complete, row.results,
                    row.submitted_at, row.complete_at)
                          for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( bsid, brids['bldr'], 'bldr', 0, 0, None, None, 0,
                        -1, self.now, None) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_addBuildset_bigger(self):
        props = dict(prop=(['list'], 'test'))
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.buildsets.addBuildset(ssid=234, reason='because',
                                properties=props, builderNames=['a', 'b']))
        def check((bsid, brids)):
            def thd(conn):
                self.assertEqual(len(brids), 2)

                # should see one buildset row
                r = conn.execute(self.db.model.buildsets.select())
                rows = [ (row.id, row.external_idstring, row.reason,
                          row.sourcestampid, row.complete,
                          row.complete_at, row.results)
                          for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( bsid, None, u'because', 234, 0, None, -1) ])

                # one property row
                r = conn.execute(self.db.model.buildset_properties.select())
                rows = [ (row.buildsetid, row.property_name, row.property_value)
                          for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( bsid, 'prop', json.dumps([ ['list'], 'test' ]) ) ])

                # and two buildrequests rows (and don't re-check the default columns)
                r = conn.execute(self.db.model.buildrequests.select())
                rows = [ (row.buildsetid, row.id, row.buildername)
                          for row in r.fetchall() ]

                # we don't know which of the brids is assigned to which
                # buildername, but either one will do
                self.assertEqual(sorted(rows),
                    [ ( bsid, brids['a'], 'a'), (bsid, brids['b'], 'b') ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_subscribeToBuildset(self):
        tbl = self.db.model.scheduler_upstream_buildsets
        def add_data_thd(conn):
            conn.execute(self.db.model.schedulers.insert(), [
                    dict(schedulerid=13, name='other', state='', class_name='sch'),
                ])
            conn.execute(self.db.model.sourcestamps.insert(), [
                    dict(id=120, branch='b', revision='120',
                         repository='', project=''),
                ])
            conn.execute(self.db.model.buildsets.insert(), [
                    dict(id=14, sourcestampid=120, complete=0,
                         results=-1, submitted_at=0),
                ])
        d = self.db.pool.do(add_data_thd)
        d.addCallback(lambda _ :
                self.db.buildsets.subscribeToBuildset(schedulerid=13, buildsetid=14))
        def check(_):
            def thd(conn):
                r = conn.execute(tbl.select())
                rows = [ (row.schedulerid, row.buildsetid, row.active)
                          for row in r.fetchall() ]
                self.assertEqual(rows, [ (13, 14, 1) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_unsubscribeFromBuildset(self):
        tbl = self.db.model.scheduler_upstream_buildsets
        def add_data_thd(conn):
            conn.execute(self.db.model.sourcestamps.insert(), [
                    dict(id=120, branch='b', revision='120',
                         repository='', project=''),
                ])
            conn.execute(self.db.model.buildsets.insert(), [
                    dict(id=13, sourcestampid=120, complete=0,
                         results=-1, submitted_at=0),
                    dict(id=14, sourcestampid=120, complete=0,
                         results=-1, submitted_at=0),
                ])
            conn.execute(self.db.model.schedulers.insert(), [
                    dict(schedulerid=92, name='sc', state='', class_name='sch'),
                ])
            conn.execute(tbl.insert(), [
                    dict(schedulerid=92, buildsetid=13, complete=0),
                    dict(schedulerid=92, buildsetid=14, complete=1),
                ])
        d = self.db.pool.do(add_data_thd)
        d.addCallback(
            lambda _ : self.db.buildsets.unsubscribeFromBuildset(
                                            schedulerid=92, buildsetid=14))
        def check(_):
            def thd(conn):
                r = conn.execute(tbl.select())
                rows = [ (row.schedulerid, row.buildsetid)
                          for row in r.fetchall() ]
                self.assertEqual(rows, [ (92, 13) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getSubscribedBuildsets(self):
        tbl = self.db.model.scheduler_upstream_buildsets
        def add_data_thd(conn):
            conn.execute(self.db.model.schedulers.insert(), [
                    dict(schedulerid=92, name='sc', state='', class_name='sch'),
                    dict(schedulerid=93, name='other', state='', class_name='sch'),
                ])
            conn.execute(self.db.model.sourcestamps.insert(), [
                    dict(id=120, branch='b', revision='120',
                         repository='', project=''),
                    dict(id=130, branch='b', revision='130',
                         repository='', project=''),
                    dict(id=140, branch='b', revision='140',
                         repository='', project=''),
                ])
            conn.execute(self.db.model.buildsets.insert(), [
                    dict(id=12, sourcestampid=120, complete=0,
                         results=-1, submitted_at=0),
                    dict(id=13, sourcestampid=130, complete=0,
                         results=-1, submitted_at=0),
                    dict(id=14, sourcestampid=140, complete=1,
                         results=5, submitted_at=0),
                    dict(id=15, sourcestampid=120, complete=0,
                         results=-1, submitted_at=0),
                ])
            conn.execute(tbl.insert(), [
                    dict(schedulerid=92, buildsetid=12, active=1),
                    dict(schedulerid=92, buildsetid=13, active=1),
                    dict(schedulerid=92, buildsetid=14, active=1),
                    # a duplicate row:
                    dict(schedulerid=92, buildsetid=14, active=1),
                    # an inactive row:
                    dict(schedulerid=92, buildsetid=15, active=0),
                    # and a row for another scheduler:
                    dict(schedulerid=93, buildsetid=14, active=1),
                ])
        d = self.db.pool.do(add_data_thd)
        d.addCallback(lambda _ :
                self.db.buildsets.getSubscribedBuildsets(92))
        def check(res):
            self.assertEqual(sorted(res), sorted([
                    (12, 120, 0, -1),
                    (13, 130, 0, -1),
                    (14, 140, 1, 5),
                ]))
        d.addCallback(check)
        return d

    def do_test_getBuildsetProperties(self, buildsetid, rows, expected):
        d = self.insertTestData(rows)
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsetProperties(buildsetid))
        def check(props):
            self.assertEqual(props, expected)
        d.addCallback(check)
        return d

    def test_getBuildsetProperties_multiple(self):
        return self.do_test_getBuildsetProperties(91, [
            fakedb.Buildset(id=91, sourcestampid=234, complete=0,
                    results=-1, submitted_at=0),
            fakedb.BuildsetProperty(buildsetid=91, property_name='prop1',
                    property_value='["one", "fake1"]'),
            fakedb.BuildsetProperty(buildsetid=91, property_name='prop2',
                    property_value='["two", "fake2"]'),
        ], dict(prop1=("one", "fake1"), prop2=("two", "fake2")))

    def test_getBuildsetProperties_empty(self):
        return self.do_test_getBuildsetProperties(91, [
            fakedb.Buildset(id=91, sourcestampid=234, complete=0,
                    results=-1, submitted_at=0),
        ], dict())

    def test_getBuildsetProperties_nosuch(self):
        "returns an empty dict even if no such buildset exists"
        return self.do_test_getBuildsetProperties(91, [], dict())

    def test_getBuildset_incomplete_None(self):
        d = self.insertTestData([
            fakedb.Buildset(id=91, sourcestampid=234, complete=0,
                    complete_at=None, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn'),
        ])
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildset(91))
        def check(bsdict):
            self.assertEqual(bsdict, dict(external_idstring='extid',
                reason='rsn', sourcestampid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=False, complete_at=None, results=-1,
                bsid=91))
        d.addCallback(check)
        return d

    def test_getBuildset_incomplete_zero(self):
        d = self.insertTestData([
            fakedb.Buildset(id=91, sourcestampid=234, complete=0,
                    complete_at=0, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn'),
        ])
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildset(91))
        def check(bsdict):
            self.assertEqual(bsdict, dict(external_idstring='extid',
                reason='rsn', sourcestampid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=False, complete_at=None, results=-1,
                bsid=91))
        d.addCallback(check)
        return d

    def test_getBuildset_complete(self):
        d = self.insertTestData([
            fakedb.Buildset(id=91, sourcestampid=234, complete=1,
                    complete_at=298297875, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn'),
        ])
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildset(91))
        def check(bsdict):
            self.assertEqual(bsdict, dict(external_idstring='extid',
                reason='rsn', sourcestampid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=True,
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                results=-1,
                bsid=91))
        d.addCallback(check)
        return d

    def test_getBuildset_nosuch(self):
        d = self.db.buildsets.getBuildset(91)
        def check(bsdict):
            self.assertEqual(bsdict, None)
        d.addCallback(check)
        return d

    def insert_test_getBuildsets_data(self):
        return self.insertTestData([
            fakedb.Buildset(id=91, sourcestampid=234, complete=0,
                    complete_at=298297875, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn1'),
            fakedb.Buildset(id=92, sourcestampid=234, complete=1,
                    complete_at=298297876, results=7, submitted_at=266761876,
                    external_idstring='extid', reason='rsn2'),
        ])

    def test_getBuildsets_empty(self):
        d = self.db.buildsets.getBuildsets()
        def check(bsdictlist):
            self.assertEqual(bsdictlist, [])
        d.addCallback(check)
        return d

    def test_getBuildsets_all(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsets())
        def check(bsdictlist):
            self.assertEqual(sorted(bsdictlist), sorted([
              dict(external_idstring='extid', reason='rsn1', sourcestampid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=False, results=-1, bsid=91),
              dict(external_idstring='extid', reason='rsn2', sourcestampid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete=True, results=7, bsid=92),
            ]))
        d.addCallback(check)
        return d

    def test_getBuildsets_complete(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsets(complete=True))
        def check(bsdictlist):
            self.assertEqual(bsdictlist, [
              dict(external_idstring='extid', reason='rsn2', sourcestampid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete=True, results=7, bsid=92),
            ])
        d.addCallback(check)
        return d

    def test_getBuildsets_incomplete(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsets(complete=False))
        def check(bsdictlist):
            self.assertEqual(bsdictlist, [
              dict(external_idstring='extid', reason='rsn1', sourcestampid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=False, results=-1, bsid=91),
            ])
        d.addCallback(check)
        return d

    def test_completeBuildset(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.completeBuildset(bsid=91, results=6,
                                                   _reactor=self.clock))
        def check(_):
            def thd(conn):
                # should see one buildset row
                r = conn.execute(self.db.model.buildsets.select())
                rows = [ (row.id, row.complete, row.complete_at, row.results)
                         for row in r.fetchall() ]
                self.assertEqual(sorted(rows), sorted([
                    ( 91, 1, self.now, 6),
                    ( 92, 1, 298297876, 7) ]))
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_completeBuildset_already_completed(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.completeBuildset(bsid=92, results=6,
                                                   _reactor=self.clock))
        def cb(_):
            self.fail("should not succeed")
        def eb(f):
            f.trap(KeyError)
            # pass
        d.addCallbacks(cb, eb)
        return d

    def test_completeBuildset_missing(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.completeBuildset(bsid=93, results=6,
                                                   _reactor=self.clock))
        def cb(_):
            self.fail("should not succeed")
        def eb(f):
            f.trap(KeyError)
            # pass
        d.addCallbacks(cb, eb)
        return d

