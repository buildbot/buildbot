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
from twisted.internet import defer


class Db2DataMixin(object):

    def db2data(self, dbdict):
        return {
            'buildslaveid': dbdict['id'],
            'name': dbdict['name'],
            'slaveinfo': dbdict['slaveinfo'],
            'connected_to': [
                {'masterid': id, 'link': base.Link(('master', str(id)))}
                for id in dbdict['connected_to']],
            'configured_on': [
                {'masterid': c['masterid'],
                 'builderid': c['builderid'],
                 'link': base.Link(('master', str(c['masterid']),
                                    'builder', str(c['builderid'])))}
                for c in dbdict['configured_on']],
            'link': base.Link(('buildslave', str(dbdict['id']))),
        }


class BuildslaveEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /buildslave/n:buildslaveid
        /buildslave/i:name
        /master/n:masterid/buildslave/n:buildslaveid
        /master/n:masterid/buildslave/i:name
        /master/n:masterid/builder/n:builderid/buildslave/n:buildslaveid
        /master/n:masterid/builder/n:builderid/buildslave/i:name
        /builder/n:builderid/buildslave/n:buildslaveid
        /builder/n:builderid/buildslave/i:name
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
    rootLinkName = 'slaves'
    pathPatterns = """
        /buildslave
        /master/n:masterid/buildslave
        /master/n:masterid/builder/n:builderid/buildslave
        /builder/n:builderid/buildslave
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

    class EntityType(types.Entity):
        buildslaveid = types.Integer()
        name = types.String()
        connected_to = types.List(of=types.Dict(
            masterid=types.Integer(),
            link=types.Link()))
        configured_on = types.List(of=types.Dict(
            masterid=types.Integer(),
            builderid=types.Integer(),
            link=types.Link()))
        slaveinfo = types.JsonObject()
        link = types.Link()
    entityType = EntityType(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def buildslaveConfigured(self, buildslaveid, buildermasterids):
        yield self.master.db.buildslaves.buildslaveConfigured(
            buildslaveid=buildslaveid,
            buildermasterids=buildermasterids)

    @base.updateMethod
    def findBuildslaveId(self, name):
        return self.master.db.buildslaves.findBuildslaveId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def buildslaveConnected(self, buildslaveid, masterid, slaveinfo):
        yield self.master.db.buildslaves.buildslaveConnected(
            buildslaveid=buildslaveid,
            masterid=masterid,
            slaveinfo=slaveinfo)
        bs = yield self.master.data.get(('buildslave', buildslaveid))
        self.produceEvent(bs, 'connected')

    @base.updateMethod
    @defer.inlineCallbacks
    def buildslaveDisconnected(self, buildslaveid, masterid):
        yield self.master.db.buildslaves.buildslaveDisconnected(
            buildslaveid=buildslaveid,
            masterid=masterid)
        bs = yield self.master.data.get(('buildslave', buildslaveid))
        self.produceEvent(bs, 'disconnected')
