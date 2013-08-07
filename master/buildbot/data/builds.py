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
from buildbot.data import base, types
from buildbot.util import datetime2epoch

class Db2DataMixin(object):

    def db2data(self, dbdict):
        data = {
            'buildid': dbdict['id'],
            'number': dbdict['number'],
            'builderid': dbdict['builderid'],
            'builder_link': base.Link(('builder', str(dbdict['builderid']))),
            'buildrequestid': dbdict['buildrequestid'],
            'buildrequest_link': base.Link(('buildrequest',
                                           str(dbdict['buildrequestid']))),
            'buildslaveid': dbdict['buildslaveid'],
            'slave_link': base.Link(('slave', str(dbdict['buildslaveid']))),
            'masterid': dbdict['masterid'],
            'master_link': base.Link(('master', str(dbdict['masterid']))),
            'started_at': datetime2epoch(dbdict['started_at']),
            'complete_at': datetime2epoch(dbdict['complete_at']),
            'complete': dbdict['complete_at'] is not None,
            'state_strings': dbdict['state_strings'],
            'results': dbdict['results'],
            'link': base.Link(('build', str(dbdict['id']))),
        }
        return defer.succeed(data)


class BuildEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /build/n:buildid
        /builder/n:builderid/build/n:number
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        if 'buildid' in kwargs:
            dbdict = yield self.master.db.builds.getBuild(kwargs['buildid'])
        else:
            bldr = kwargs['builderid']
            num = kwargs['number']
            dbdict = yield self.master.db.builds.getBuildByNumber(bldr, num)
        defer.returnValue((yield self.db2data(dbdict))
                                if dbdict else None)


class BuildsEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /build
        /builder/n:builderid/build
        /buildrequest/n:buildrequestid/build
    """
    rootLinkName = 'builds'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        builds = yield self.master.db.builds.getBuilds(
                                builderid=kwargs.get('builderid'),
                                buildrequestid=kwargs.get('buildrequestid'))
        defer.returnValue(
                [ (yield self.db2data(dbdict)) for dbdict in builds ])

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('build', None, None, None))


class Build(base.ResourceType):

    name = "build"
    plural = "builds"
    endpoints = [ BuildEndpoint, BuildsEndpoint ]
    keyFields = [ 'builderid', 'buildid' ]

    class EntityType(types.Entity):
        buildid = types.Integer()
        number = types.Integer()
        builderid = types.Integer()
        builder_link = types.Link()
        buildrequestid = types.Integer()
        buildrequest_link = types.Link()
        buildslaveid = types.Integer()
        slave_link = types.Link()
        masterid = types.Integer()
        master_link = types.Link()
        started_at = types.Integer()
        complete = types.Boolean()
        complete_at = types.NoneOk(types.Integer)
        results = types.NoneOk(types.Integer())
        state_strings = types.List(of=types.String())
        link = types.Link()
    entityType = EntityType(name)

    @base.updateMethod
    def newBuild(self, builderid, buildrequestid, buildslaveid):
        return self.master.db.builds.addBuild(
                builderid=builderid,
                buildrequestid=buildrequestid,
                buildslaveid=buildslaveid,
                masterid=self.master.masterid,
                state_strings=[u'starting'])

    @base.updateMethod
    def setBuildStateStrings(self, buildid, state_strings):
        return self.master.db.builds.setBuildStateStrings(
                buildid=buildid, state_strings=state_strings)

    @base.updateMethod
    def finishBuild(self, buildid, results):
        return self.master.db.builds.finishBuild(
                buildid=buildid, results=results)
