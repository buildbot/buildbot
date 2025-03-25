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
from buildbot.data import exceptions
from buildbot.data import types
from buildbot.util import identifiers

if TYPE_CHECKING:
    from buildbot.db.workers import WorkerModel
    from buildbot.util.twisted import InlineCallbacksType


def _db2data(model: WorkerModel):
    return {
        'workerid': model.id,
        'name': model.name,
        'workerinfo': model.workerinfo,
        'paused': model.paused,
        "pause_reason": model.pause_reason,
        'graceful': model.graceful,
        'connected_to': [{'masterid': id} for id in model.connected_to],
        'configured_on': [
            {'masterid': c.masterid, 'builderid': c.builderid} for c in model.configured_on
        ],
    }


class WorkerEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/workers/n:workerid",
        "/workers/i:name",
        "/masters/n:masterid/workers/n:workerid",
        "/masters/n:masterid/workers/i:name",
        "/masters/n:masterid/builders/n:builderid/workers/n:workerid",
        "/masters/n:masterid/builders/n:builderid/workers/i:name",
        "/builders/n:builderid/workers/n:workerid",
        "/builders/n:builderid/workers/i:name",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        sldict = yield self.master.db.workers.getWorker(
            workerid=kwargs.get('workerid'),
            name=kwargs.get('name'),
            masterid=kwargs.get('masterid'),
            builderid=kwargs.get('builderid'),
        )
        if sldict:
            return _db2data(sldict)
        return None

    @defer.inlineCallbacks
    def control(self, action, args, kwargs):
        if action not in ("stop", "pause", "unpause", "kill"):
            raise exceptions.InvalidControlException(f"action: {action} is not supported")

        worker = yield self.get(None, kwargs)
        if worker is not None:
            self.master.mq.produce(
                ("control", "worker", str(worker["workerid"]), action),
                {"reason": kwargs.get("reason", args.get("reason", "no reason"))},
            )
        else:
            raise exceptions.exceptions.InvalidPathError("worker not found")


class WorkersEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    rootLinkName = 'workers'
    pathPatterns = [
        "/workers",
        "/masters/n:masterid/workers",
        "/masters/n:masterid/builders/n:builderid/workers",
        "/builders/n:builderid/workers",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        paused = resultSpec.popBooleanFilter('paused')
        graceful = resultSpec.popBooleanFilter('graceful')
        workers_dicts = yield self.master.db.workers.getWorkers(
            builderid=kwargs.get('builderid'),
            masterid=kwargs.get('masterid'),
            paused=paused,
            graceful=graceful,
        )
        return [_db2data(w) for w in workers_dicts]


class MasterBuilderEntityType(types.Entity):
    masterid = types.Integer()
    builderid = types.Integer()


class MasterIdEntityType(types.Entity):
    masterid = types.Integer()


class Worker(base.ResourceType):
    name = "worker"
    plural = "workers"
    endpoints = [WorkerEndpoint, WorkersEndpoint]
    eventPathPatterns = [
        "/workers/:workerid",
    ]

    class EntityType(types.Entity):
        workerid = types.Integer()
        name = types.String()
        connected_to = types.List(of=MasterIdEntityType("master_id"))
        configured_on = types.List(of=MasterBuilderEntityType("master_builder"))
        workerinfo = types.JsonObject()
        paused = types.Boolean()
        pause_reason = types.NoneOk(types.String())
        graceful = types.Boolean()

    entityType = EntityType(name)

    @base.updateMethod
    # returns a Deferred that returns None
    def workerConfigured(self, workerid, masterid, builderids):
        return self.master.db.workers.workerConfigured(
            workerid=workerid, masterid=masterid, builderids=builderids
        )

    @base.updateMethod
    def findWorkerId(self, name: str) -> int:
        if not identifiers.isIdentifier(50, name):
            raise ValueError(f"Worker name {name!r} is not a 50-character identifier")
        return self.master.db.workers.findWorkerId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def workerConnected(
        self, workerid: int, masterid: int, workerinfo: str
    ) -> InlineCallbacksType[None]:
        yield self.master.db.workers.workerConnected(
            workerid=workerid, masterid=masterid, workerinfo=workerinfo
        )
        bs = yield self.master.data.get(('workers', workerid))
        self.produceEvent(bs, 'connected')

    @base.updateMethod
    @defer.inlineCallbacks
    def workerDisconnected(self, workerid: int, masterid: int) -> InlineCallbacksType[None]:
        yield self.master.db.workers.workerDisconnected(workerid=workerid, masterid=masterid)
        bs = yield self.master.data.get(('workers', workerid))
        self.produceEvent(bs, 'disconnected')

    @base.updateMethod
    @defer.inlineCallbacks
    def workerMissing(
        self, workerid: int, masterid: int, last_connection: int, notify: bool
    ) -> InlineCallbacksType[None]:
        bs = yield self.master.data.get(('workers', workerid))
        bs['last_connection'] = last_connection
        bs['notify'] = notify
        self.produceEvent(bs, 'missing')

    @base.updateMethod
    @defer.inlineCallbacks
    def set_worker_paused(
        self, workerid: int, paused: bool, pause_reason: str | None = None
    ) -> InlineCallbacksType[None]:
        yield self.master.db.workers.set_worker_paused(
            workerid=workerid, paused=paused, pause_reason=pause_reason
        )
        bs = yield self.master.data.get(('workers', workerid))
        self.produceEvent(bs, 'state_updated')

    @base.updateMethod
    @defer.inlineCallbacks
    def set_worker_graceful(self, workerid: int, graceful: bool) -> InlineCallbacksType[None]:
        yield self.master.db.workers.set_worker_graceful(workerid=workerid, graceful=graceful)
        bs = yield self.master.data.get(('workers', workerid))
        self.produceEvent(bs, 'state_updated')

    @base.updateMethod
    def deconfigureAllWorkersForMaster(self, masterid: int) -> defer.Deferred[None]:
        # unconfigure all workers for this master
        return self.master.db.workers.deconfigureAllWorkersForMaster(masterid=masterid)

    def _masterDeactivated(self, masterid: int) -> defer.Deferred[None]:
        return self.deconfigureAllWorkersForMaster(masterid)
