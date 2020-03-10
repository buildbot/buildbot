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


from twisted.internet import defer

from buildbot.db import schedulers
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row


class Scheduler(Row):
    table = "schedulers"

    defaults = dict(
        id=None,
        name='schname',
        name_hash=None,
        enabled=1,
    )

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]


class SchedulerMaster(Row):
    table = "scheduler_masters"

    defaults = dict(
        schedulerid=None,
        masterid=None,
    )

    foreignKeys = ('schedulerid', 'masterid')
    required_columns = ('schedulerid', 'masterid')


class SchedulerChange(Row):
    table = "scheduler_changes"

    defaults = dict(
        schedulerid=None,
        changeid=None,
        important=1,
    )

    foreignKeys = ('schedulerid', 'changeid')
    required_columns = ('schedulerid', 'changeid')


class FakeSchedulersComponent(FakeDBComponent):

    def setUp(self):
        self.schedulers = {}
        self.scheduler_masters = {}
        self.states = {}
        self.classifications = {}
        self.enabled = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, SchedulerChange):
                cls = self.classifications.setdefault(row.schedulerid, {})
                cls[row.changeid] = row.important
            if isinstance(row, Scheduler):
                self.schedulers[row.id] = row.name
                self.enabled[row.id] = True
            if isinstance(row, SchedulerMaster):
                self.scheduler_masters[row.schedulerid] = row.masterid

    # component methods

    def classifyChanges(self, schedulerid, classifications):
        self.classifications.setdefault(
            schedulerid, {}).update(classifications)
        return defer.succeed(None)

    def flushChangeClassifications(self, schedulerid, less_than=None):
        if less_than is not None:
            classifications = self.classifications.setdefault(schedulerid, {})
            for changeid in list(classifications):
                if changeid < less_than:
                    del classifications[changeid]
        else:
            self.classifications[schedulerid] = {}
        return defer.succeed(None)

    def getChangeClassifications(self, schedulerid, branch=-1, repository=-1,
                                 project=-1, codebase=-1):
        classifications = self.classifications.setdefault(schedulerid, {})

        sentinel = dict(branch=object(), repository=object(),
                        project=object(), codebase=object())

        if branch != -1:
            # filter out the classifications for the requested branch
            classifications = dict(
                (k, v) for (k, v) in classifications.items()
                if self.db.changes.changes.get(k, sentinel)['branch'] == branch)

        if repository != -1:
            # filter out the classifications for the requested branch
            classifications = dict(
                (k, v) for (k, v) in classifications.items()
                if self.db.changes.changes.get(k, sentinel)['repository'] == repository)

        if project != -1:
            # filter out the classifications for the requested branch
            classifications = dict(
                (k, v) for (k, v) in classifications.items()
                if self.db.changes.changes.get(k, sentinel)['project'] == project)

        if codebase != -1:
            # filter out the classifications for the requested branch
            classifications = dict(
                (k, v) for (k, v) in classifications.items()
                if self.db.changes.changes.get(k, sentinel)['codebase'] == codebase)

        return defer.succeed(classifications)

    def findSchedulerId(self, name):
        for sch_id, sch_name in self.schedulers.items():
            if sch_name == name:
                return defer.succeed(sch_id)
        new_id = (max(self.schedulers) + 1) if self.schedulers else 1
        self.schedulers[new_id] = name
        return defer.succeed(new_id)

    def getScheduler(self, schedulerid):
        if schedulerid in self.schedulers:
            rv = dict(
                id=schedulerid,
                name=self.schedulers[schedulerid],
                enabled=self.enabled.get(schedulerid, True),
                masterid=None)
            # only set masterid if the relevant scheduler master exists and
            # is active
            rv['masterid'] = self.scheduler_masters.get(schedulerid)
            return defer.succeed(rv)
        return None

    def getSchedulers(self, active=None, masterid=None):
        d = defer.DeferredList([
            self.getScheduler(id) for id in self.schedulers
        ])

        @d.addCallback
        def filter(results):
            # filter off the DeferredList results (we know it's good)
            results = [r[1] for r in results]
            # filter for masterid
            if masterid is not None:
                results = [r for r in results
                           if r['masterid'] == masterid]
            # filter for active or inactive if necessary
            if active:
                results = [r for r in results
                           if r['masterid'] is not None]
            elif active is not None:
                results = [r for r in results
                           if r['masterid'] is None]
            return results
        return d

    def setSchedulerMaster(self, schedulerid, masterid):
        current_masterid = self.scheduler_masters.get(schedulerid)
        if current_masterid and masterid is not None and current_masterid != masterid:
            return defer.fail(schedulers.SchedulerAlreadyClaimedError())
        self.scheduler_masters[schedulerid] = masterid
        return defer.succeed(None)

    # fake methods

    def fakeClassifications(self, schedulerid, classifications):
        """Set the set of classifications for a scheduler"""
        self.classifications[schedulerid] = classifications

    def fakeScheduler(self, name, schedulerid):
        self.schedulers[schedulerid] = name

    def fakeSchedulerMaster(self, schedulerid, masterid):
        if masterid is not None:
            self.scheduler_masters[schedulerid] = masterid
        else:
            del self.scheduler_masters[schedulerid]

    # assertions

    def assertClassifications(self, schedulerid, classifications):
        self.t.assertEqual(
            self.classifications.get(schedulerid, {}),
            classifications)

    def assertSchedulerMaster(self, schedulerid, masterid):
        self.t.assertEqual(self.scheduler_masters.get(schedulerid),
                           masterid)

    def enable(self, schedulerid, v):
        assert schedulerid in self.schedulers
        self.enabled[schedulerid] = v
        return defer.succeed((('control', 'schedulers', schedulerid, 'enable'), {'enabled': v}))
