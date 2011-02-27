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
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.db import schedulers
from buildbot.util import json
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestSchedulersConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'schedulers', 'scheduler_changes' ])

        def finish_setup(_):
            self.db.schedulers = \
                    schedulers.SchedulersConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    def checkScheduler(self, schedulerid, name, class_name, state):
        def thd(conn):
            q = self.db.model.schedulers.select(
                whereclause=(self.db.model.schedulers.c.schedulerid == schedulerid))
            for row in conn.execute(q):
                self.assertEqual([ row.schedulerid, row.name, row.class_name, row.state ],
                                 [ schedulerid, name, class_name, state ])
        return self.db.pool.do(thd)

    # test data

    change3 = fakedb.Change(changeid=3)
    change4 = fakedb.Change(changeid=4)
    change5 = fakedb.Change(changeid=5)
    change6 = fakedb.Change(changeid=6, branch='sql')

    scheduler24 = fakedb.Scheduler(schedulerid=24)

    def addClassifications(self, _, schedulerid, *classifications):
        def thd(conn):
            q = self.db.model.scheduler_changes.insert()
            conn.execute(q, [
                dict(changeid=c[0], schedulerid=schedulerid, important=c[1])
                for c in classifications ])
        return self.db.pool.do(thd)

    # tests

    def test_getState_good(self):
        d = self.insertTestData([
            fakedb.Scheduler(schedulerid=10, state='{ "foo":"bar" }')
        ])
        d.addCallback(lambda _ : self.db.schedulers.getState(10))
        def check(state):
            self.assertEqual(state, dict(foo="bar"))
        d.addCallback(check)
        return d

    def test_getState_bad(self):
        d = self.insertTestData([
            fakedb.Scheduler(schedulerid=10, state='{ 99notjs0n }')
        ])
        d.addCallback(lambda _ : self.db.schedulers.getState(10))
        def check(state):
            self.assertEqual(state, {})
        d.addCallback(check)
        return d

    def test_getState_missing(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ : self.db.schedulers.getState(10))
        def check(state):
            self.assertEqual(state, {})
        d.addCallback(check)
        return d

    def test_setState(self):
        d = self.insertTestData([
            fakedb.Scheduler(schedulerid=99, state='{}')
        ])
        d.addCallback(lambda _ : self.db.schedulers.setState(99, dict(abc="def")))
        def check(state):
            def thd(conn):
                r = conn.execute(self.db.model.schedulers.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].schedulerid, 99)
                self.assertEqual(json.loads(rows[0].state), dict(abc="def"))
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_setState_unJSON(self):
        d = self.insertTestData([
            fakedb.Scheduler(schedulerid=99, state='{}')
        ])
        d.addCallback(lambda _ : self.db.schedulers.setState(99, mock.Mock()))
        def cb(_):
            self.fail("should have raised a failure")
        def eb(f):
            f.trap(TypeError)
        d.addCallbacks(cb, eb)
        return d

    def test_classifyChanges(self):
        d = self.insertTestData([ self.change3, self.change4,
                                  self.scheduler24 ])
        d.addCallback(lambda _ :
                self.db.schedulers.classifyChanges(24,
                    { 3 : False, 4: True }))
        def check(_):
            def thd(conn):
                sch_chgs_tbl = self.db.model.scheduler_changes
                q = sch_chgs_tbl.select(order_by=sch_chgs_tbl.c.changeid)
                r = conn.execute(q)
                rows = [ (row.schedulerid, row.changeid, row.important)
                         for row in r.fetchall() ]
                self.assertEqual(rows, [ (24, 3, 0), (24, 4, 1) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_classifyChanges_again(self):
        # test reclassifying changes, which may happen during some timing
        # conditions
        d = self.insertTestData([
            self.change3,
            self.scheduler24,
            fakedb.SchedulerChange(schedulerid=24, changeid=3, important=0),
        ])
        d.addCallback(lambda _ :
                self.db.schedulers.classifyChanges(24, { 3 : True }))
        def check(_):
            def thd(conn):
                sch_chgs_tbl = self.db.model.scheduler_changes
                q = sch_chgs_tbl.select(order_by=sch_chgs_tbl.c.changeid)
                r = conn.execute(q)
                rows = [ (row.schedulerid, row.changeid, row.important)
                         for row in r.fetchall() ]
                self.assertEqual(rows, [ (24, 3, 1) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_flushChangeClassifications(self):
        d = self.insertTestData([ self.change3, self.change4,
                                  self.change5, self.scheduler24 ])
        d.addCallback(self.addClassifications, 24,
                (3, 1), (4, 0), (5, 1))
        d.addCallback(lambda _ :
            self.db.schedulers.flushChangeClassifications(24))
        def check(_):
            def thd(conn):
                q = self.db.model.scheduler_changes.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual(rows, [])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_flushChangeClassifications_less_than(self):
        d = self.insertTestData([ self.change3, self.change4,
                                  self.change5, self.scheduler24 ])
        d.addCallback(self.addClassifications, 24,
                (3, 1), (4, 0), (5, 1))
        d.addCallback(lambda _ :
            self.db.schedulers.flushChangeClassifications(24, less_than=5))
        def check(_):
            def thd(conn):
                q = self.db.model.scheduler_changes.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual([ (r.changeid, r.important) for r in rows],
                                 [ (5, 1) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getChangeClassifications(self):
        d = self.insertTestData([ self.change3, self.change4, self.change5,
                                  self.change6, self.scheduler24 ])
        d.addCallback(self.addClassifications, 24,
                (3, 1), (4, 0), (5, 1), (6, 1))
        d.addCallback(lambda _ :
            self.db.schedulers.getChangeClassifications(24))
        def check(cls):
            self.assertEqual(cls, { 3 : True, 4 : False, 5 : True, 6: True })
        d.addCallback(check)
        return d

    def test_getChangeClassifications_branch(self):
        d = self.insertTestData([ self.change3, self.change4, self.change5,
                                  self.change6, self.scheduler24 ])
        d.addCallback(self.addClassifications, 24,
                (3, 1), (4, 0), (5, 1), (6, 1))
        d.addCallback(lambda _ :
            self.db.schedulers.getChangeClassifications(24, branch='sql'))
        def check(cls):
            self.assertEqual(cls, { 6 : True })
        d.addCallback(check)
        return d

    def test_getSchedulerId_first_time(self):
        d = self.insertTestData([
            fakedb.Scheduler(name='distractor', class_name='Weekly',
                schedulerid=992, state='{"foo": "bar"}')
        ])
        d.addCallback(lambda _ :
                self.db.schedulers.getSchedulerId('mysched', 'Nightly'))
        d.addCallback(lambda schid :
                self.checkScheduler(schid, 'mysched', 'Nightly', '{}'))
        return d

    def test_getSchedulerId_existing(self):
        d = self.insertTestData([
            fakedb.Scheduler(name='mysched', class_name='Nightly',
                schedulerid=992, state='{"foo": "bar"}')
        ])
        d.addCallback(lambda _ :
                self.db.schedulers.getSchedulerId('mysched', 'Nightly'))
        def check(schid):
            self.assertEqual(schid, 992)
            return self.checkScheduler(992, 'mysched', 'Nightly', '{"foo": "bar"}')
        d.addCallback(check)
        return d

    def test_getSchedulerId_upgrade(self):
        d = self.insertTestData([
            fakedb.Scheduler(name='mysched', class_name='', schedulerid=992,
                state='{}')
        ])
        d.addCallback(lambda _ :
                self.db.schedulers.getSchedulerId('mysched', 'Hourly'))
        def check(schid):
            self.assertEqual(schid, 992)
            # class has been filled in
            return self.checkScheduler(992, 'mysched', 'Hourly', '{}')
        d.addCallback(check)
        return d
