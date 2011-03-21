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

import time
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.db import buildsets
from buildbot.util import json
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestBuildsetsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
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
        started = int(time.time())
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.buildsets.addBuildset(ssid=234, reason='because',
                properties={}, builderNames=['bldr'], external_idstring='extid'))
        def check(bsid):
            def thd(conn):
                # should see one buildset row
                r = conn.execute(self.db.model.buildsets.select())
                rows = [ (row.id, row.external_idstring, row.reason,
                          row.sourcestampid, row.complete, row.complete_at,
                          row.results) for row in r.fetchall() ]
                bs_submitted_at = row.submitted_at
                self.assertTrue(started <= bs_submitted_at <= time.time(),
                        "now: %s; db: %s" % (time.time(), row.submitted_at))
                self.assertEqual(rows,
                    [ ( bsid, 'extid', 'because', 234, 0, None, -1) ])

                # and one buildrequests row
                r = conn.execute(self.db.model.buildrequests.select())
                rows = [ (row.buildsetid, row.buildername, row.priority,
                          row.claimed_at, row.claimed_by_name,
                          row.claimed_by_incarnation, row.complete, row.results,
                          row.submitted_at, row.complete_at)
                          for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( bsid, 'bldr', 0, 0, None, None, 0,
                        -1, bs_submitted_at, None) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_addBuildset_bigger(self):
        props = dict(prop=(['list'], 'test'))
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.buildsets.addBuildset(ssid=234, reason='because',
                                properties=props, builderNames=['a', 'b']))
        def check(bsid):
            def thd(conn):
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
                rows = [ (row.buildsetid, row.buildername)
                          for row in r.fetchall() ]
                self.assertEqual(sorted(rows),
                    [ ( bsid, 'a'), (bsid, 'b') ])
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
