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
            'buildworkerid': dbdict['id'],
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


class BuildworkerEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /buildworkers/n:buildworkerid
        /buildworkers/i:name
        /masters/n:masterid/buildworkers/n:buildworkerid
        /masters/n:masterid/buildworkers/i:name
        /masters/n:masterid/builders/n:builderid/buildworkers/n:buildworkerid
        /masters/n:masterid/builders/n:builderid/buildworkers/i:name
        /builders/n:builderid/buildworkers/n:buildworkerid
        /builders/n:builderid/buildworkers/i:name
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        sldict = yield self.master.db.buildworkers.getBuildworker(
            buildworkerid=kwargs.get('buildworkerid'),
            name=kwargs.get('name'),
            masterid=kwargs.get('masterid'),
            builderid=kwargs.get('builderid'))
        if sldict:
            defer.returnValue(self.db2data(sldict))


class BuildworkersEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    rootLinkName = 'buildworkers'
    pathPatterns = """
        /buildworkers
        /masters/n:masterid/buildworkers
        /masters/n:masterid/builders/n:builderid/buildworkers
        /builders/n:builderid/buildworkers
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        sldicts = yield self.master.db.buildworkers.getBuildworkers(
            builderid=kwargs.get('builderid'),
            masterid=kwargs.get('masterid'))
        defer.returnValue([self.db2data(sl) for sl in sldicts])


class Buildworker(base.ResourceType):

    name = "buildworker"
    plural = "buildworkers"
    endpoints = [BuildworkerEndpoint, BuildworkersEndpoint]
    keyFields = ['buildworkerid']
    eventPathPatterns = """
        /buildworkers/:buildworkerid
    """

    class EntityType(types.Entity):
        buildworkerid = types.Integer()
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
    def buildworkerConfigured(self, buildworkerid, masterid, builderids):
        yield self.master.db.buildworkers.buildworkerConfigured(
            buildworkerid=buildworkerid,
            masterid=masterid,
            builderids=builderids)

    @base.updateMethod
    def findBuildworkerId(self, name):
        if not identifiers.isIdentifier(50, name):
            raise ValueError("Buildworker name %r is not a 50-character identifier" % (name,))
        return self.master.db.buildworkers.findBuildworkerId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def buildworkerConnected(self, buildworkerid, masterid, workerinfo):
        yield self.master.db.buildworkers.buildworkerConnected(
            buildworkerid=buildworkerid,
            masterid=masterid,
            workerinfo=workerinfo)
        bs = yield self.master.data.get(('buildworkers', buildworkerid))
        self.produceEvent(bs, 'connected')

    @base.updateMethod
    @defer.inlineCallbacks
    def buildworkerDisconnected(self, buildworkerid, masterid):
        yield self.master.db.buildworkers.buildworkerDisconnected(
            buildworkerid=buildworkerid,
            masterid=masterid)
        bs = yield self.master.data.get(('buildworkers', buildworkerid))
        self.produceEvent(bs, 'disconnected')

    @base.updateMethod
    def deconfigureAllBuidworkersForMaster(self, masterid):
        # unconfigure all workers for this master
        return self.master.db.buildworkers.deconfigureAllBuidworkersForMaster(
            masterid=masterid)

    def _masterDeactivated(self, masterid):
        return self.deconfigureAllBuidworkersForMaster(masterid)
