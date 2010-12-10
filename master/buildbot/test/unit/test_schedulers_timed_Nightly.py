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

from buildbot.schedulers import timed
from buildbot.changes.manager import ChangeManager
from buildbot.changes.changes import Change
from buildbot.test.fake.fakedb import FakeDBConn

class DummyParent:
    def __init__(self, dbconn):
        self.db = dbconn
        self.change_svc = ChangeManager()
        self.change_svc.parent = self

    def publish_buildset(self, name, bsid, t):
        pass

class Nightly(unittest.TestCase):
    def setUp(self):
        self.dbc = FakeDBConn()

    def test_dont_create_scheduler_changes(self):
        s = timed.Nightly(
                name="tsched",
                builderNames=['tbuild'])
        s.parent = DummyParent(self.dbc)

        d = self.dbc.addSchedulers([s])

        # Add some changes
        for i in range(10):
            c = Change(who='just a guy', files=[], comments="")
            d.addCallback(lambda res: self.dbc.addChangeToDatabase(c))

        def runScheduler(res):
            return s.run()
        d.addCallback(runScheduler)

        def checkTables(res):
            # Check that we have the number of changes we think we should have
            self.assertEquals(len(self.dbc.changes), 10)

            # Check that there are no entries in scheduler_changes
            important, unimportant = self.dbc.classified_changes.get(s.schedulerid, ([], []))
            self.assertEquals(len(important+unimportant), 0)
        d.addCallback(checkTables)
        return d

    def test_create_scheduler_changes(self):
        s = timed.Nightly(
                name="tsched",
                builderNames=['tbuild'],
                onlyIfChanged=True)
        s.parent = DummyParent(self.dbc)

        d = self.dbc.addSchedulers([s])

        # Add some changes
        for i in range(10):
            c = Change(who='just a guy', files=[], comments="")
            d.addCallback(lambda res: self.dbc.addChangeToDatabase(c))

        def runScheduler(res):
            return s.run()
        d.addCallback(runScheduler)

        def checkTables(res):
            # Check that we have the number of changes we think we should have
            self.assertEquals(len(self.dbc.changes), 10)

            # Check that there are entries in scheduler_changes
            important, unimportant = self.dbc.classified_changes.get(s.schedulerid, ([], []))
            self.assertEquals(len(important+unimportant), 10)
        d.addCallback(checkTables)
        return d

    def test_expire_old_scheduler_changes(self):
        s = timed.Nightly(
                name="tsched",
                builderNames=['tbuild'],
                )
        s.parent = DummyParent(self.dbc)

        # Hack the scheduler so that it always runs
        def _check_timer(t):
            now = time.time()
            s._maybe_start_build(t)
            s.update_last_build(t, now)

            # reschedule for the next timer
            return now + 10
        s._check_timer = _check_timer

        d = self.dbc.addSchedulers([s])

        # Add a changes
        c = Change(who='just a guy', files=[], comments="")
        d.addCallback(lambda res: self.dbc.addChangeToDatabase(c))

        # Add some dummy scheduler_changes
        def addSchedulerChanges(res):
            for i in range(100):
                self.dbc.classified_changes.setdefault(s.schedulerid, ([], []))[0].append(c)
        d.addCallback(addSchedulerChanges)

        def runScheduler(res):
            return s.run()
        d.addCallback(runScheduler)

        def checkTables(res):
            # Check that there are no entries in scheduler_changes
            important, unimportant = self.dbc.classified_changes.get(s.schedulerid, ([], []))
            self.assertEquals(len(important+unimportant), 0)
        d.addCallback(checkTables)
        return d
