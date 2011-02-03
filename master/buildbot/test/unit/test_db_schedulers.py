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
from buildbot.test.util import db, connector_component

class TestChangesConnectorComponent(
            connector_component.ConnectorComponentMixin,
            db.RealDatabaseMixin,
            unittest.TestCase):

    def setUp(self):
        self.setUpRealDatabase()
        self.setUpConnectorComponent(self.db_url)

        # add the .schedulers attribute
        self.db.schedulers = schedulers.SchedulersConnectorComponent(self.db)

        # set up the tables we'll need, following links where ForeignKey
        # constraints are in place.
        def thd(engine):
            self.db.model.changes.create(bind=engine)
            self.db.model.schedulers.create(bind=engine)
            self.db.model.scheduler_changes.create(bind=engine)
        return self.db.pool.do_with_engine(thd)

    def tearDown(self):
        self.tearDownConnectorComponent()
        self.tearDownRealDatabase()

    # add stuff to the database; these are all meant to be used
    # as callbacks on a deferred

    def addChanges(self, _, *rows):
        def thd(conn):
            stmt = self.db.model.changes.insert()
            conn.execute(stmt, rows)
        return self.db.pool.do(thd)

    def addScheduler(self, _, **cols):
        def thd(conn):
            stmt = self.db.model.schedulers.insert()
            conn.execute(stmt, **cols)
        return self.db.pool.do(thd)

    def addSchedulerChanges(self, _, *rows):
        def thd(conn):
            stmt = self.db.model.scheduler_changes.insert()
            conn.execute(stmt, rows)
        return self.db.pool.do(thd)

    def addSampleChanges(self, _):
        d = defer.succeed(None)
        d.addCallback(self.addChanges,
          dict(changeid=3, author="three", comments="3", is_dir=False,
               branch="trunk", revision="0e92a098b", when_timestamp=266738404,
               revlink='lnk', category='devel', repository='git://warner',
               project='Buildbot'),
          dict(changeid=4, author="four", comments="4", is_dir=False,
               branch="trunk", revision="0e92a098b", when_timestamp=266738404,
               revlink='lnk', category='devel', repository='git://warner',
               project='Buildbot'),
          dict(changeid=5, author="five", comments="5", is_dir=False,
               branch="trunk", revision="0e92a098b", when_timestamp=266738404,
               revlink='lnk', category='devel', repository='git://warner',
               project='Buildbot'),
          )
        return d

    def addClassifications(self, _, schedulerid, *classifications):
        def thd(conn):
            q = self.db.model.scheduler_changes.insert()
            conn.execute(q, [
                dict(changeid=c[0], schedulerid=schedulerid, important=c[1])
                for c in classifications ])
        return self.db.pool.do(thd)

    def checkScheduler(self, schedulerid, name, class_name, state):
        def thd(conn):
            q = self.db.model.schedulers.select(
                whereclause=(self.db.model.schedulers.c.schedulerid == schedulerid))
            for row in conn.execute(q):
                self.assertEqual([ row.schedulerid, row.name, row.class_name, row.state ],
                                 [ schedulerid, name, class_name, state ])
        return self.db.pool.do(thd)


    # tests

    def test_getState_good(self):
        d = defer.succeed(None)
        d.addCallback(self.addScheduler,
            schedulerid=10, name='testsched',
            class_name='TestScheduler', state='{ "foo":"bar" }')
        d.addCallback(lambda _ : self.db.schedulers.getState(10))
        def check(state):
            self.assertEqual(state, dict(foo="bar"))
        d.addCallback(check)
        return d

    def test_getState_bad(self):
        d = defer.succeed(None)
        d.addCallback(self.addScheduler,
            schedulerid=10, name='testsched',
            class_name='TestScheduler', state='{ 99notjs0n }')
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
        d = defer.succeed(None)
        d.addCallback(self.addScheduler,
            schedulerid=99, name='trythis',
            class_name='Scheduler', state='{}')
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
        d = defer.succeed(None)
        d.addCallback(self.addScheduler,
            schedulerid=99, name='trythis',
            class_name='Scheduler', state='{}')
        d.addCallback(lambda _ : self.db.schedulers.setState(99, mock.Mock()))
        def cb(_):
            self.fail("should have raised a failure")
        def eb(f):
            f.trap(TypeError)
        d.addCallbacks(cb, eb)
        return d

    def test_classifyChanges(self):
        d = defer.succeed(None)
        d.addCallback(self.addSampleChanges)
        d.addCallback(lambda _ :
                self.db.schedulers.classifyChanges(27,
                    { 3 : False, 4: True }))
        def check(_):
            def thd(conn):
                sch_chgs_tbl = self.db.model.scheduler_changes
                q = sch_chgs_tbl.select(order_by=sch_chgs_tbl.c.changeid)
                r = conn.execute(q)
                rows = [ (row.schedulerid, row.changeid, row.important)
                         for row in r.fetchall() ]
                self.assertEqual(rows, [ (27, 3, 0), (27, 4, 1) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_flushChangeClassifications(self):
        d = defer.succeed(None)
        d.addCallback(self.addSampleChanges)
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
        d = defer.succeed(None)
        d.addCallback(self.addSampleChanges)
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
        d = defer.succeed(None)
        d.addCallback(self.addSampleChanges)
        d.addCallback(self.addChanges,
          dict(changeid=6, author="six", comments="six", is_dir=False,
               branch="sql", revision="0e92a99b", when_timestamp=266738419,
               revlink='lnk', category='sql', repository='git://ayust',
               project='Buildbot'),
        )
        d.addCallback(self.addClassifications, 24,
                (3, 1), (4, 0), (5, 1), (6, 1))
        d.addCallback(lambda _ :
            self.db.schedulers.getChangeClassifications(24))
        def check(cls):
            self.assertEqual(cls, { 3 : True, 4 : False, 5 : True, 6: True })
        d.addCallback(check)
        return d

    def test_getChangeClassifications_branch(self):
        d = defer.succeed(None)
        d.addCallback(self.addSampleChanges)
        d.addCallback(self.addChanges,
          dict(changeid=6, author="six", comments="six", is_dir=False,
               branch="sql", revision="0e92a99b", when_timestamp=266738419,
               revlink='lnk', category='sql', repository='git://ayust',
               project='Buildbot'),
        )
        d.addCallback(self.addClassifications, 24,
                (3, 1), (4, 0), (5, 1), (6, 1))
        d.addCallback(lambda _ :
            self.db.schedulers.getChangeClassifications(24, branch='sql'))
        def check(cls):
            self.assertEqual(cls, { 6 : True })
        d.addCallback(check)
        return d

    def test_getSchedulerId_first_time(self):
        d = defer.succeed(None)
        d.addCallback(self.addScheduler,
                name='distractor', class_name='Weekly',
                schedulerid=9929, state='{"foo": "bar"}')
        d.addCallback(lambda _ :
                self.db.schedulers.getSchedulerId('mysched', 'Nightly'))
        d.addCallback(lambda schid :
                self.checkScheduler(schid, 'mysched', 'Nightly', '{}'))
        return d

    def test_getSchedulerId_existing(self):
        d = defer.succeed(None)
        d.addCallback(self.addScheduler,
                name='mysched', class_name='Nightly',
                schedulerid=9929, state='{"foo": "bar"}')
        d.addCallback(lambda _ :
                self.db.schedulers.getSchedulerId('mysched', 'Nightly'))
        def check(schid):
            self.assertEqual(schid, 9929)
            return self.checkScheduler(9929, 'mysched', 'Nightly', '{"foo": "bar"}')
        d.addCallback(check)
        return d

    def test_getSchedulerId_upgrade(self):
        d = defer.succeed(None)
        d.addCallback(self.addScheduler,
                name='mysched', class_name='', schedulerid=9929, state='{}')
        d.addCallback(lambda _ :
                self.db.schedulers.getSchedulerId('mysched', 'Hourly'))
        def check(schid):
            self.assertEqual(schid, 9929)
            # class has been filled in
            return self.checkScheduler(9929, 'mysched', 'Hourly', '{}')
        d.addCallback(check)
        return d
