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
        data = {
            'buildid': dbdict['id'],
            'number': dbdict['number'],
            'builderid': dbdict['builderid'],
            'buildrequestid': dbdict['buildrequestid'],
            'buildslaveid': dbdict['buildslaveid'],
            'masterid': dbdict['masterid'],
            'started_at': dbdict['started_at'],
            'complete_at': dbdict['complete_at'],
            'complete': dbdict['complete_at'] is not None,
            'state_string': dbdict['state_string'],
            'results': dbdict['results'],
        }
        return defer.succeed(data)


class BuildEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /builds/n:buildid
        /builders/n:builderid/builds/n:number
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

    def startConsuming(self, callback, options, kwargs):
        builderid = kwargs.get('builderid')
        number = kwargs.get('number')
        buildid = kwargs.get('buildid')
        if builderid is not None:
            return self.master.mq.startConsuming(callback,
                                                 ('builders', str(builderid), 'builds', str(number), None))
        else:
            return self.master.mq.startConsuming(callback,
                                                 ('builds', str(buildid), None))


class BuildsEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /builds
        /builders/n:builderid/builds
        /buildrequests/n:buildrequestid/builds
    """
    rootLinkName = 'builds'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        # following returns None if no filter
        # true or false, if there is a complete filter
        complete = resultSpec.popBooleanFilter("complete")
        builds = yield self.master.db.builds.getBuilds(
            builderid=kwargs.get('builderid'),
            buildrequestid=kwargs.get('buildrequestid'),
            complete=complete)
        defer.returnValue(
            [(yield self.db2data(dbdict)) for dbdict in builds])

    def startConsuming(self, callback, options, kwargs):
        builderid = kwargs.get('builderid')
        buildrequestid = kwargs.get('buildrequestid')
        if builderid is not None:
            return self.master.mq.startConsuming(
                callback,
                ('builders', str(builderid), 'builds', None, None))
        elif buildrequestid is not None:
            # XXX these messages are never produced
            return self.master.mq.startConsuming(callback,
                                                 ('buildrequests', str(buildrequestid), 'builds', None))
        else:
            return self.master.mq.startConsuming(callback,
                                                 ('builds', None, None, None))


class Build(base.ResourceType):

    name = "build"
    plural = "builds"
    endpoints = [BuildEndpoint, BuildsEndpoint]
    keyFields = ['builderid', 'buildid']
    eventPathPatterns = """
        /builders/:builderid/builds/:number
        /builds/:buildid
    """

    class EntityType(types.Entity):
        buildid = types.Integer()
        number = types.Integer()
        builderid = types.Integer()
        buildrequestid = types.Integer()
        buildslaveid = types.Integer()
        masterid = types.Integer()
        started_at = types.DateTime()
        complete = types.Boolean()
        complete_at = types.NoneOk(types.DateTime())
        results = types.NoneOk(types.Integer())
        state_string = types.String()
    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, _id, event):
        # get the build and munge the result for the notification
        build = yield self.master.data.get(('builds', str(_id)))
        self.produceEvent(build, event)

    @base.updateMethod
    @defer.inlineCallbacks
    def addBuild(self, builderid, buildrequestid, buildslaveid):
        res = yield self.master.db.builds.addBuild(
            builderid=builderid,
            buildrequestid=buildrequestid,
            buildslaveid=buildslaveid,
            masterid=self.master.masterid,
            state_string=u'created')
        if res is not None:
            _id, number = res
            yield self.generateEvent(_id, "new")
        defer.returnValue(res)

    @base.updateMethod
    @defer.inlineCallbacks
    def setBuildStateString(self, buildid, state_string):
        res = yield self.master.db.builds.setBuildStateString(
            buildid=buildid, state_string=state_string)
        yield self.generateEvent(buildid, "update")
        defer.returnValue(res)

    @base.updateMethod
    @defer.inlineCallbacks
    def finishBuild(self, buildid, results):
        res = yield self.master.db.builds.finishBuild(
            buildid=buildid, results=results)
        yield self.generateEvent(buildid, "finished")
        defer.returnValue(res)
