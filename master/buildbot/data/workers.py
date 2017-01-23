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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types
from buildbot.util import identifiers


class Db2DataMixin(object):

    def db2data(self, dbdict):
        return {
            'workerid': dbdict['id'],
            'name': dbdict['name'],
            'workerinfo': dbdict['workerinfo'],
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
            defer.returnValue(self.db2data(sldict))


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
        workers_dicts = yield self.master.db.workers.getWorkers(
            builderid=kwargs.get('builderid'),
            masterid=kwargs.get('masterid'))
        defer.returnValue([self.db2data(w) for w in workers_dicts])


class Worker(base.ResourceType):

    name = "worker"
    plural = "workers"
    endpoints = [WorkerEndpoint, WorkersEndpoint]
    keyFields = ['workerid']
    eventPathPatterns = """
        /workers/:workerid
    """

    class EntityType(types.Entity):
        workerid = types.Integer()
        name = types.String()
        connected_to = types.List(of=types.Dict(
            masterid=types.Integer()))
        configured_on = types.List(of=types.Dict(
            masterid=types.Integer(),
            builderid=types.Integer()))
        workerinfo = types.JsonObject()
    entityType = EntityType(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def workerConfigured(self, workerid, masterid, builderids):
        yield self.master.db.workers.workerConfigured(
            workerid=workerid,
            masterid=masterid,
            builderids=builderids)

    @base.updateMethod
    def findWorkerId(self, name):
        if not identifiers.isIdentifier(50, name):
            raise ValueError(
                "Worker name %r is not a 50-character identifier" % (name,))
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
    def deconfigureAllWorkersForMaster(self, masterid):
        # unconfigure all workers for this master
        return self.master.db.workers.deconfigureAllWorkersForMaster(
            masterid=masterid)

    def _masterDeactivated(self, masterid):
        return self.deconfigureAllWorkersForMaster(masterid)
