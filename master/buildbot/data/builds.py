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
            'builder_link': base.Link(('builder', str(dbdict['builderid']))),
            'buildrequestid': dbdict['buildrequestid'],
            'buildrequest_link': base.Link(('buildrequest',
                                           str(dbdict['buildrequestid']))),
            'buildslaveid': dbdict['buildslaveid'],
            'slave_link': base.Link(('slave', str(dbdict['buildslaveid']))),
            'masterid': dbdict['masterid'],
            'master_link': base.Link(('master', str(dbdict['masterid']))),
            'started_at': dbdict['started_at'],
            'complete_at': dbdict['complete_at'],
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

    def startConsuming(self, callback, options, kwargs):
        builderid = kwargs.get('builderid')
        number = kwargs.get('number')
        buildid = kwargs.get('buildid')
        if builderid is not None:
            return self.master.mq.startConsuming(callback,
                                                 ('builder', str(builderid), 'build', str(number), None))
        else:
            return self.master.mq.startConsuming(callback,
                                                 ('build', str(buildid), None))


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
            [(yield self.db2data(dbdict)) for dbdict in builds])

    def startConsuming(self, callback, options, kwargs):
        builderid = kwargs.get('builderid')
        buildrequestid = kwargs.get('buildrequestid')
        if builderid is not None:
            return self.master.mq.startConsuming(
                callback,
                ('builder', str(builderid), 'build', None, None))
        elif buildrequestid is not None:
            # XXX these messages are never produced
            return self.master.mq.startConsuming(callback,
                                                 ('buildrequest', buildrequestid, 'build', None))
        else:
            return self.master.mq.startConsuming(callback,
                                                 ('build', None, None, None))


class Build(base.ResourceType):

    name = "build"
    plural = "builds"
    endpoints = [BuildEndpoint, BuildsEndpoint]
    keyFields = ['builderid', 'buildid']
    eventPathPatterns = """
        /builder/:builderid/build/:number
        /build/:buildid
    """

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
        started_at = types.DateTime()
        complete = types.Boolean()
        complete_at = types.NoneOk(types.DateTime())
        results = types.NoneOk(types.Integer())
        state_strings = types.List(of=types.String())
        link = types.Link()
    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, _id, event):
        # get the build and munge the result for the notification
        build = yield self.master.data.get(('build', str(_id)))
        self.produceEvent(build, event)

    @base.updateMethod
    @defer.inlineCallbacks
    def newBuild(self, builderid, buildrequestid, buildslaveid):
        res = yield self.master.db.builds.addBuild(
            builderid=builderid,
            buildrequestid=buildrequestid,
            buildslaveid=buildslaveid,
            masterid=self.master.masterid,
            state_strings=[u'created'])
        if res is not None:
            _id, number = res
            yield self.generateEvent(_id, "new")
        defer.returnValue(res)

    @base.updateMethod
    @defer.inlineCallbacks
    def setBuildStateStrings(self, buildid, state_strings):
        res = yield self.master.db.builds.setBuildStateStrings(
            buildid=buildid, state_strings=state_strings)
        yield self.generateEvent(buildid, "update")
        defer.returnValue(res)

    @base.updateMethod
    @defer.inlineCallbacks
    def finishBuild(self, buildid, results):
        res = yield self.master.db.builds.finishBuild(
            buildid=buildid, results=results)
        yield self.generateEvent(buildid, "finished")
        defer.returnValue(res)
