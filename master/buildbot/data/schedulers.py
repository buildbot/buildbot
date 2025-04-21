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

from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import masters
from buildbot.data import types
from buildbot.db.schedulers import SchedulerAlreadyClaimedError

if TYPE_CHECKING:
    from buildbot.db.schedulers import SchedulerModel
    from buildbot.util.twisted import InlineCallbacksType


@defer.inlineCallbacks
def _db2data(master, dbdict: SchedulerModel):
    dbmaster = None
    if dbdict.masterid is not None:
        dbmaster = yield master.data.get(('masters', dbdict.masterid))
    data = {
        'schedulerid': dbdict.id,
        'name': dbdict.name,
        'enabled': dbdict.enabled,
        'master': dbmaster,
    }
    return data


class SchedulerEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/schedulers/n:schedulerid",
        "/masters/n:masterid/schedulers/n:schedulerid",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        dbdict = yield self.master.db.schedulers.getScheduler(kwargs['schedulerid'])
        if 'masterid' in kwargs:
            if dbdict.masterid != kwargs['masterid']:
                return None
        return (yield _db2data(self.master, dbdict)) if dbdict else None

    @defer.inlineCallbacks
    def control(self, action, args, kwargs):
        if action == 'enable':
            schedulerid = kwargs['schedulerid']
            v = args['enabled']
            yield self.master.data.updates.schedulerEnable(schedulerid, v)
        return None


class SchedulersEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/schedulers",
        "/masters/n:masterid/schedulers",
    ]
    rootLinkName = 'schedulers'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        schedulers = yield self.master.db.schedulers.getSchedulers(masterid=kwargs.get('masterid'))
        schdicts = yield defer.DeferredList(
            [_db2data(self.master, schdict) for schdict in schedulers],
            consumeErrors=True,
            fireOnOneErrback=True,
        )
        return [r for (s, r) in schdicts]


class Scheduler(base.ResourceType):
    name = "scheduler"
    plural = "schedulers"
    endpoints = [SchedulerEndpoint, SchedulersEndpoint]
    eventPathPatterns = [
        "/schedulers/:schedulerid",
    ]

    class EntityType(types.Entity):
        schedulerid = types.Integer()
        name = types.String()
        enabled = types.Boolean()
        master = types.NoneOk(masters.Master.entityType)

    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, schedulerid, event):
        scheduler = yield self.master.data.get(('schedulers', str(schedulerid)))
        self.produceEvent(scheduler, event)

    @base.updateMethod
    @defer.inlineCallbacks
    def schedulerEnable(self, schedulerid: int, v: bool) -> InlineCallbacksType[None]:
        yield self.master.db.schedulers.enable(schedulerid, v)
        yield self.generateEvent(schedulerid, 'updated')
        return None

    @base.updateMethod
    def findSchedulerId(self, name: str) -> defer.Deferred[int]:
        return self.master.db.schedulers.findSchedulerId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def trySetSchedulerMaster(self, schedulerid: int, masterid: int) -> InlineCallbacksType[bool]:
        try:
            yield self.master.db.schedulers.setSchedulerMaster(schedulerid, masterid)
        except SchedulerAlreadyClaimedError:
            return False
        return True

    @defer.inlineCallbacks
    def _masterDeactivated(self, masterid):
        schedulers = yield self.master.db.schedulers.getSchedulers(masterid=masterid)
        for sch in schedulers:
            yield self.master.db.schedulers.setSchedulerMaster(sch.id, None)
