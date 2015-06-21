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
            'buildslaveid': dbdict['id'],
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


class BuildslaveEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /buildslaves/n:buildslaveid
        /buildslaves/i:name
        /masters/n:masterid/buildslaves/n:buildslaveid
        /masters/n:masterid/buildslaves/i:name
        /masters/n:masterid/builders/n:builderid/buildslaves/n:buildslaveid
        /masters/n:masterid/builders/n:builderid/buildslaves/i:name
        /builders/n:builderid/buildslaves/n:buildslaveid
        /builders/n:builderid/buildslaves/i:name
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        sldict = yield self.master.db.buildslaves.getBuildslave(
            buildslaveid=kwargs.get('buildslaveid'),
            name=kwargs.get('name'),
            masterid=kwargs.get('masterid'),
            builderid=kwargs.get('builderid'))
        if sldict:
            defer.returnValue(self.db2data(sldict))


class BuildslavesEndpoint(Db2DataMixin, base.Endpoint):

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
        sldicts = yield self.master.db.buildslaves.getBuildslaves(
            builderid=kwargs.get('builderid'),
            masterid=kwargs.get('masterid'))
        defer.returnValue([self.db2data(sl) for sl in sldicts])


class Buildslave(base.ResourceType):

    name = "buildslave"
    plural = "buildslaves"
    endpoints = [BuildslaveEndpoint, BuildslavesEndpoint]
    keyFields = ['buildslaveid']
    eventPathPatterns = """
        /buildslaves/:buildslaveid
    """

    class EntityType(types.Entity):
        buildslaveid = types.Integer()
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
    def buildslaveConfigured(self, buildslaveid, masterid, builderids):
        yield self.master.db.buildslaves.buildslaveConfigured(
            buildslaveid=buildslaveid,
            masterid=masterid,
            builderids=builderids)

    @base.updateMethod
    def findBuildslaveId(self, name):
        if not identifiers.isIdentifier(50, name):
            raise ValueError("Buildslave name %r is not a 50-character identifier" % (name,))
        return self.master.db.buildslaves.findBuildslaveId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def buildslaveConnected(self, buildslaveid, masterid, slaveinfo):
        yield self.master.db.buildslaves.buildslaveConnected(
            buildslaveid=buildslaveid,
            masterid=masterid,
            slaveinfo=slaveinfo)
        bs = yield self.master.data.get(('buildslaves', buildslaveid))
        self.produceEvent(bs, 'connected')

    @base.updateMethod
    @defer.inlineCallbacks
    def buildslaveDisconnected(self, buildslaveid, masterid):
        yield self.master.db.buildslaves.buildslaveDisconnected(
            buildslaveid=buildslaveid,
            masterid=masterid)
        bs = yield self.master.data.get(('buildslaves', buildslaveid))
        self.produceEvent(bs, 'disconnected')

    @base.updateMethod
    def deconfigureAllBuidslavesForMaster(self, masterid):
        # unconfigure all slaves for this master
        return self.master.db.buildslaves.deconfigureAllBuidslavesForMaster(
            masterid=masterid)

    def _masterDeactivated(self, masterid):
        return self.deconfigureAllBuidslavesForMaster(masterid)
