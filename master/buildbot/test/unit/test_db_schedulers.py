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

from buildbot.db import schedulers
from buildbot.test.fake import fakedb
from buildbot.test.util import connector_component
from twisted.trial import unittest


class TestSchedulersConnectorComponent(
    connector_component.ConnectorComponentMixin,
        unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'objects', 'scheduler_changes'])

        def finish_setup(_):
            self.db.schedulers = \
                schedulers.SchedulersConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    def checkScheduler(self, objectid, name, class_name):
        def thd(conn):
            q = self.db.model.schedulers.select(
                whereclause=(self.db.model.schedulers.c.objectid == objectid))
            for row in conn.execute(q):
                self.assertEqual([row.objectid, row.name, row.class_name],
                                 [objectid, name, class_name])
        return self.db.pool.do(thd)

    # test data

    change3 = fakedb.Change(changeid=3)
    change4 = fakedb.Change(changeid=4)
    change5 = fakedb.Change(changeid=5)
    change6 = fakedb.Change(changeid=6, branch='sql')

    scheduler24 = fakedb.Object(id=24)

    def addClassifications(self, _, objectid, *classifications):
        def thd(conn):
            q = self.db.model.scheduler_changes.insert()
            conn.execute(q, [
                dict(changeid=c[0], objectid=objectid, important=c[1])
                for c in classifications])
        return self.db.pool.do(thd)

    # tests
    def test_classifyChanges(self):
        d = self.insertTestData([self.change3, self.change4,
                                 self.scheduler24])
        d.addCallback(lambda _:
                      self.db.schedulers.classifyChanges(24,
                                                         {3: False, 4: True}))

        def check(_):
            def thd(conn):
                sch_chgs_tbl = self.db.model.scheduler_changes
                q = sch_chgs_tbl.select(order_by=sch_chgs_tbl.c.changeid)
                r = conn.execute(q)
                rows = [(row.objectid, row.changeid, row.important)
                        for row in r.fetchall()]
                self.assertEqual(rows, [(24, 3, 0), (24, 4, 1)])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_classifyChanges_again(self):
        # test reclassifying changes, which may happen during some timing
        # conditions.  It's important that this test uses multiple changes,
        # only one of which already exists
        d = self.insertTestData([
        # conditions.  It's important that this test uses multiple changes,
        # only one of which already exists
            self.change3,
            self.change4,
            self.change5,
            self.change6,
            self.scheduler24,
            fakedb.SchedulerChange(objectid=24, changeid=5, important=0),
        ])
        d.addCallback(lambda _:
                      self.db.schedulers.classifyChanges(
                          24, {3: True, 4: False, 5: True, 6: False}))

        def check(_):
            def thd(conn):
                sch_chgs_tbl = self.db.model.scheduler_changes
                q = sch_chgs_tbl.select(order_by=sch_chgs_tbl.c.changeid)
                r = conn.execute(q)
                rows = [(row.objectid, row.changeid, row.important)
                        for row in r.fetchall()]
                self.assertEqual(sorted(rows),
                                 sorted([(24, 3, 1), (24, 4, 0),
                                         (24, 5, 1), (24, 6, 0)]))
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_flushChangeClassifications(self):
        d = self.insertTestData([self.change3, self.change4,
                                 self.change5, self.scheduler24])
        d.addCallback(self.addClassifications, 24,
                      (3, 1), (4, 0), (5, 1))
        d.addCallback(lambda _:
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
        d = self.insertTestData([self.change3, self.change4,
                                 self.change5, self.scheduler24])
        d.addCallback(self.addClassifications, 24,
                      (3, 1), (4, 0), (5, 1))
        d.addCallback(lambda _:
                      self.db.schedulers.flushChangeClassifications(24, less_than=5))

        def check(_):
            def thd(conn):
                q = self.db.model.scheduler_changes.select()
                rows = conn.execute(q).fetchall()
                self.assertEqual([(r.changeid, r.important) for r in rows],
                                 [(5, 1)])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getChangeClassifications(self):
        d = self.insertTestData([self.change3, self.change4, self.change5,
                                 self.change6, self.scheduler24])
        d.addCallback(self.addClassifications, 24,
                      (3, 1), (4, 0), (5, 1), (6, 1))
        d.addCallback(lambda _:
                      self.db.schedulers.getChangeClassifications(24))

        def check(cls):
            self.assertEqual(cls, {3: True, 4: False, 5: True, 6: True})
        d.addCallback(check)
        return d

    def test_getChangeClassifications_branch(self):
        d = self.insertTestData([self.change3, self.change4, self.change5,
                                 self.change6, self.scheduler24])
        d.addCallback(self.addClassifications, 24,
                      (3, 1), (4, 0), (5, 1), (6, 1))
        d.addCallback(lambda _:
                      self.db.schedulers.getChangeClassifications(24, branch='sql'))

        def check(cls):
            self.assertEqual(cls, {6: True})
        d.addCallback(check)
        return d
