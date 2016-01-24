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

from buildbot.data import base
from buildbot.data import types
from buildbot.util import identifiers
from twisted.internet import defer


class Db2DataMixin(object):

    def db2data(self, dbdict):
        return {
            'workerid': dbdict['id'],
            'name': dbdict['name'],
            'slaveinfo': dbdict['slaveinfo'],
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
        /buildslaves/n:workerid
        /buildslaves/i:name
        /masters/n:masterid/buildslaves/n:workerid
        /masters/n:masterid/buildslaves/i:name
        /masters/n:masterid/builders/n:builderid/buildslaves/n:workerid
        /masters/n:masterid/builders/n:builderid/buildslaves/i:name
        /builders/n:builderid/buildslaves/n:workerid
        /builders/n:builderid/buildslaves/i:name
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
    rootLinkName = 'buildslaves'
    pathPatterns = """
        /buildslaves
        /masters/n:masterid/buildslaves
        /masters/n:masterid/builders/n:builderid/buildslaves
        /builders/n:builderid/buildslaves
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        sldicts = yield self.master.db.workers.getWorkers(
            builderid=kwargs.get('builderid'),
            masterid=kwargs.get('masterid'))
        defer.returnValue([self.db2data(sl) for sl in sldicts])


class Worker(base.ResourceType):

    name = "buildslave"
    plural = "buildslaves"
    endpoints = [WorkerEndpoint, WorkersEndpoint]
    keyFields = ['workerid']
    eventPathPatterns = """
        /buildslaves/:workerid
    """

    class EntityType(types.Entity):
        workerid = types.Integer()
        name = types.String()
        connected_to = types.List(of=types.Dict(
            masterid=types.Integer()))
        configured_on = types.List(of=types.Dict(
            masterid=types.Integer(),
            builderid=types.Integer()))
        slaveinfo = types.JsonObject()
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
            raise ValueError("Worker name %r is not a 50-character identifier" % (name,))
        return self.master.db.workers.findWorkerId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def workerConnected(self, workerid, masterid, slaveinfo):
        yield self.master.db.workers.workerConnected(
            workerid=workerid,
            masterid=masterid,
            workerinfo=slaveinfo)
        bs = yield self.master.data.get(('buildslaves', workerid))
        self.produceEvent(bs, 'connected')

    @base.updateMethod
    @defer.inlineCallbacks
    def workerDisconnected(self, workerid, masterid):
        yield self.master.db.workers.workerDisconnected(
            workerid=workerid,
            masterid=masterid)
        bs = yield self.master.data.get(('buildslaves', workerid))
        self.produceEvent(bs, 'disconnected')

    @base.updateMethod
    def deconfigureAllWorkersForMaster(self, masterid):
        # unconfigure all workers for this master
        return self.master.db.workers.deconfigureAllWorkersForMaster(
            masterid=masterid)

    def _masterDeactivated(self, masterid):
        return self.deconfigureAllWorkersForMaster(masterid)
