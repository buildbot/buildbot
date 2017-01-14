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
from future.utils import iteritems

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types
from buildbot.data.resultspec import ResultSpec


class Db2DataMixin(object):

    def _generate_filtered_properties(self, props, filters):
        """
        This method returns Build's properties according to property filters.

        .. seealso::

            `Official Documentation <http://docs.buildbot.net/latest/developer/rtype-build.html>`_

        :param props: The Build's properties as a dict (from db)
        :param filters: Desired properties keys as a list (from API URI)

        """
        # by default none properties are returned
        if props and filters:  # pragma: no cover
            return (props
                    if '*' in filters
                    else dict(((k, v) for k, v in iteritems(props) if k in filters)))

    def db2data(self, dbdict):
        data = {
            'buildid': dbdict['id'],
            'number': dbdict['number'],
            'builderid': dbdict['builderid'],
            'buildrequestid': dbdict['buildrequestid'],
            'workerid': dbdict['workerid'],
            'masterid': dbdict['masterid'],
            'started_at': dbdict['started_at'],
            'complete_at': dbdict['complete_at'],
            'complete': dbdict['complete_at'] is not None,
            'state_string': dbdict['state_string'],
            'results': dbdict['results'],
            'properties': {}
        }
        return defer.succeed(data)
    fieldMapping = {
        'buildid': 'builds.id',
        'number': 'builds.number',
        'builderid': 'builds.builderid',
        'buildrequestid': 'builds.buildrequestid',
        'workerid': 'builds.workerid',
        'masterid': 'builds.masterid',
        'started_at': 'builds.started_at',
        'complete_at': 'builds.complete_at',
        'state_string': 'builds.state_string',
        'results': 'builds.results',
    }


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

        data = yield self.db2data(dbdict) if dbdict else None
        # In some cases, data could be None
        if data:
            filters = resultSpec.popProperties() if hasattr(
                resultSpec, 'popProperties') else []
            # Avoid to request DB for Build's properties if not specified
            if filters:  # pragma: no cover
                try:
                    props = yield self.master.db.builds.getBuildProperties(data['buildid'])
                except (KeyError, TypeError):
                    props = {}
                filtered_properties = self._generate_filtered_properties(
                    props, filters)
                if filtered_properties:
                    data['properties'] = filtered_properties
        defer.returnValue(data)

    def control(self, action, args, kwargs):
        # we convert the action into a mixedCase method name
        action_method = getattr(self, "action" + action.capitalize())
        if action_method is None:
            raise ValueError("action: {} is not supported".format(action))
        return action_method(args, kwargs)

    @defer.inlineCallbacks
    def actionStop(self, args, kwargs):
        buildid = kwargs.get('buildid')
        if buildid is None:
            bldr = kwargs['builderid']
            num = kwargs['number']
            dbdict = yield self.master.db.builds.getBuildByNumber(bldr, num)
            buildid = dbdict['id']
        self.master.mq.produce(("control", "builds",
                                str(buildid), 'stop'),
                               dict(reason=kwargs.get('reason', args.get('reason', 'no reason'))))

    @defer.inlineCallbacks
    def actionRebuild(self, args, kwargs):
        # we use the self.get and not self.data.get to be able to support all
        # the pathPatterns of this endpoint
        build = yield self.get(ResultSpec(), kwargs)
        buildrequest = yield self.master.data.get(('buildrequests', build['buildrequestid']))
        res = yield self.master.data.updates.rebuildBuildrequest(buildrequest)
        defer.returnValue(res)


class BuildsEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /builds
        /builders/n:builderid/builds
        /buildrequests/n:buildrequestid/builds
        /workers/n:workerid/builds
    """
    rootLinkName = 'builds'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        # following returns None if no filter
        # true or false, if there is a complete filter
        complete = resultSpec.popBooleanFilter("complete")
        buildrequestid = resultSpec.popIntegerFilter("buildrequestid")
        resultSpec.fieldMapping = self.fieldMapping
        builds = yield self.master.db.builds.getBuilds(
            builderid=kwargs.get('builderid'),
            buildrequestid=kwargs.get('buildrequestid', buildrequestid),
            workerid=kwargs.get('workerid'),
            complete=complete,
            resultSpec=resultSpec)
        # returns properties' list
        filters = resultSpec.popProperties()
        buildscol = []
        for b in builds:
            data = yield self.db2data(b)
            # Avoid to request DB for Build's properties if not specified
            if filters:  # pragma: no cover
                props = yield self.master.db.builds.getBuildProperties(b['id'])
                filtered_properties = self._generate_filtered_properties(
                    props, filters)
                if filtered_properties:
                    data['properties'] = filtered_properties
            buildscol.append(data)
        defer.returnValue(buildscol)


class Build(base.ResourceType):

    name = "build"
    plural = "builds"
    endpoints = [BuildEndpoint, BuildsEndpoint]
    keyFields = ['builderid', 'buildid', 'workerid']
    eventPathPatterns = """
        /builders/:builderid/builds/:number
        /builds/:buildid
        /workers/:workerid/builds/:buildid
    """

    class EntityType(types.Entity):
        buildid = types.Integer()
        number = types.Integer()
        builderid = types.Integer()
        buildrequestid = types.Integer()
        workerid = types.Integer()
        masterid = types.Integer()
        started_at = types.DateTime()
        complete = types.Boolean()
        complete_at = types.NoneOk(types.DateTime())
        results = types.NoneOk(types.Integer())
        state_string = types.String()
        properties = types.NoneOk(types.SourcedProperties())
    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, _id, event):
        # get the build and munge the result for the notification
        build = yield self.master.data.get(('builds', str(_id)))
        self.produceEvent(build, event)

    @base.updateMethod
    @defer.inlineCallbacks
    def addBuild(self, builderid, buildrequestid, workerid):
        res = yield self.master.db.builds.addBuild(
            builderid=builderid,
            buildrequestid=buildrequestid,
            workerid=workerid,
            masterid=self.master.masterid,
            state_string=u'created')
        defer.returnValue(res)

    @base.updateMethod
    def generateNewBuildEvent(self, buildid):
        return self.generateEvent(buildid, "new")

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
