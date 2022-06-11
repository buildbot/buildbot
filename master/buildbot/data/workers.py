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

from buildbot.data import base
from buildbot.data import exceptions
from buildbot.data import types
from buildbot.util import identifiers


class Db2DataMixin:

    def db2data(self, dbdict):
        return {
            'workerid': dbdict['id'],
            'name': dbdict['name'],
            'workerinfo': dbdict['workerinfo'],
            'paused': dbdict['paused'],
            'graceful': dbdict['graceful'],
            'connected_to': [
                {'masterid': id}
                for id in dbdict['connected_to']],
            'configured_on': [
                {'masterid': c['masterid'],
                 'builderid': c['builderid']}
                for c in dbdict['configured_on']],
        }


class WorkerEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /workers/n:workerid
        /workers/i:name
        /masters/n:masterid/workers/n:workerid
        /masters/n:masterid/workers/i:name
        /masters/n:masterid/builders/n:builderid/workers/n:workerid
        /masters/n:masterid/builders/n:builderid/workers/i:name
        /builders/n:builderid/workers/n:workerid
        /builders/n:builderid/workers/i:name
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        sldict = yield self.master.db.workers.getWorker(
            workerid=kwargs.get('workerid'),
            name=kwargs.get('name'),
            masterid=kwargs.get('masterid'),
            builderid=kwargs.get('builderid'))
        if sldict:
            return self.db2data(sldict)
        return None

    @defer.inlineCallbacks
    def control(self, action, args, kwargs):
        if action not in ("stop", "pause", "unpause", "kill"):
            raise exceptions.InvalidControlException(f"action: {action} is not supported")

        worker = yield self.get(None, kwargs)
        if worker is not None:
            self.master.mq.produce(("control", "worker",
                                    str(worker['workerid']), action),
                                dict(reason=kwargs.get('reason', args.get('reason', 'no reason'))))
        else:
            raise exceptions.exceptions.InvalidPathError("worker not found")


class WorkersEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    rootLinkName = 'workers'
    pathPatterns = """
        /workers
        /masters/n:masterid/workers
        /masters/n:masterid/builders/n:builderid/workers
        /builders/n:builderid/workers
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        paused = resultSpec.popBooleanFilter('paused')
        graceful = resultSpec.popBooleanFilter('graceful')
        workers_dicts = yield self.master.db.workers.getWorkers(
            builderid=kwargs.get('builderid'),
            masterid=kwargs.get('masterid'),
            paused=paused,
            graceful=graceful)
        return [self.db2data(w) for w in workers_dicts]


class MasterBuilderEntityType(types.Entity):
    masterid = types.Integer()
    builderid = types.Integer()


class MasterIdEntityType(types.Entity):
    masterid = types.Integer()


class Worker(base.ResourceType):

    name = "worker"
    plural = "workers"
    endpoints = [WorkerEndpoint, WorkersEndpoint]
    keyField = 'workerid'
    eventPathPatterns = """
        /workers/:workerid
    """
    subresources = ["Build"]

    class EntityType(types.Entity):
        workerid = types.Integer()
        name = types.String()
        connected_to = types.List(of=MasterIdEntityType("master_id", 'MasterId'))
        configured_on = types.List(of=MasterBuilderEntityType("master_builder", 'MasterBuilder'))
        workerinfo = types.JsonObject()
        paused = types.Boolean()
        graceful = types.Boolean()
    entityType = EntityType(name, 'Worker')

    @base.updateMethod
    # returns a Deferred that returns None
    def workerConfigured(self, workerid, masterid, builderids):
        return self.master.db.workers.workerConfigured(
            workerid=workerid,
            masterid=masterid,
            builderids=builderids)

    @base.updateMethod
    def findWorkerId(self, name):
        if not identifiers.isIdentifier(50, name):
            raise ValueError(f"Worker name {repr(name)} is not a 50-character identifier")
        return self.master.db.workers.findWorkerId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def workerConnected(self, workerid, masterid, workerinfo):
        yield self.master.db.workers.workerConnected(
            workerid=workerid,
            masterid=masterid,
            workerinfo=workerinfo)
        bs = yield self.master.data.get(('workers', workerid))
        self.produceEvent(bs, 'connected')

    @base.updateMethod
    @defer.inlineCallbacks
    def workerDisconnected(self, workerid, masterid):
        yield self.master.db.workers.workerDisconnected(
            workerid=workerid,
            masterid=masterid)
        bs = yield self.master.data.get(('workers', workerid))
        self.produceEvent(bs, 'disconnected')

    @base.updateMethod
    @defer.inlineCallbacks
    def workerMissing(self, workerid, masterid, last_connection, notify):
        bs = yield self.master.data.get(('workers', workerid))
        bs['last_connection'] = last_connection
        bs['notify'] = notify
        self.produceEvent(bs, 'missing')

    @base.updateMethod
    @defer.inlineCallbacks
    def setWorkerState(self, workerid, paused, graceful):
        yield self.master.db.workers.setWorkerState(
            workerid=workerid,
            paused=paused,
            graceful=graceful)
        bs = yield self.master.data.get(('workers', workerid))
        self.produceEvent(bs, 'state_updated')

    @base.updateMethod
    def deconfigureAllWorkersForMaster(self, masterid):
        # unconfigure all workers for this master
        return self.master.db.workers.deconfigureAllWorkersForMaster(
            masterid=masterid)

    def _masterDeactivated(self, masterid):
        return self.deconfigureAllWorkersForMaster(masterid)
