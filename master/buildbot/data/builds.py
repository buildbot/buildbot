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

from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types
from buildbot.data.resultspec import ResultSpec

if TYPE_CHECKING:
    from buildbot.db.builds import BuildModel


def _db2data(model: BuildModel):
    return {
        'buildid': model.id,
        'number': model.number,
        'builderid': model.builderid,
        'buildrequestid': model.buildrequestid,
        'workerid': model.workerid,
        'masterid': model.masterid,
        'started_at': model.started_at,
        'complete_at': model.complete_at,
        "locks_duration_s": model.locks_duration_s,
        'complete': model.complete_at is not None,
        'state_string': model.state_string,
        'results': model.results,
        'properties': {},
    }


class Db2DataMixin:
    def _generate_filtered_properties(self, props, filters):
        """
        This method returns Build's properties according to property filters.

        .. seealso::

            `Official Documentation <http://docs.buildbot.net/latest/developer/rtype-build.html>`_

        :param props: The Build's properties as a dict (from db)
        :param filters: Desired properties keys as a list (from API URI)

        """
        # by default none properties are returned
        if props and filters:
            return (
                props
                if '*' in filters
                else dict(((k, v) for k, v in props.items() if k in filters))
            )
        return None

    fieldMapping = {
        'buildid': 'builds.id',
        'number': 'builds.number',
        'builderid': 'builds.builderid',
        'buildrequestid': 'builds.buildrequestid',
        'workerid': 'builds.workerid',
        'masterid': 'builds.masterid',
        'started_at': 'builds.started_at',
        'complete_at': 'builds.complete_at',
        "locks_duration_s": "builds.locks_duration_s",
        'state_string': 'builds.state_string',
        'results': 'builds.results',
    }


class BuildEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = """
        /builds/n:buildid
        /builders/n:builderid/builds/n:build_number
        /builders/s:buildername/builds/n:build_number
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        if 'buildid' in kwargs:
            dbdict = yield self.master.db.builds.getBuild(kwargs['buildid'])
        else:
            bldr = yield self.getBuilderId(kwargs)
            if bldr is None:
                return None
            num = kwargs['build_number']
            dbdict = yield self.master.db.builds.getBuildByNumber(bldr, num)

        data = _db2data(dbdict) if dbdict else None
        # In some cases, data could be None
        if data:
            filters = resultSpec.popProperties() if hasattr(resultSpec, 'popProperties') else []
            # Avoid to request DB for Build's properties if not specified
            if filters:
                try:
                    props = yield self.master.db.builds.getBuildProperties(data['buildid'])
                except (KeyError, TypeError):
                    props = {}
                filtered_properties = self._generate_filtered_properties(props, filters)
                if filtered_properties:
                    data['properties'] = filtered_properties
        return data

    @defer.inlineCallbacks
    def actionStop(self, args, kwargs):
        buildid = kwargs.get('buildid')
        if buildid is None:
            bldr = kwargs['builderid']
            num = kwargs['build_number']
            dbdict = yield self.master.db.builds.getBuildByNumber(bldr, num)
            buildid = dbdict.id
        self.master.mq.produce(
            ("control", "builds", str(buildid), 'stop'),
            {"reason": kwargs.get('reason', args.get('reason', 'no reason'))},
        )

    @defer.inlineCallbacks
    def actionRebuild(self, args, kwargs):
        # we use the self.get and not self.data.get to be able to support all
        # the pathPatterns of this endpoint
        build = yield self.get(ResultSpec(), kwargs)
        buildrequest = yield self.master.data.get(('buildrequests', build['buildrequestid']))
        res = yield self.master.data.updates.rebuildBuildrequest(buildrequest)
        return res


class BuildsEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = """
        /builds
        /builders/n:builderid/builds
        /builders/s:buildername/builds
        /buildrequests/n:buildrequestid/builds
        /changes/n:changeid/builds
        /workers/n:workerid/builds
    """
    rootLinkName = 'builds'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        changeid = kwargs.get('changeid')
        if changeid is not None:
            builds = yield self.master.db.builds.getBuildsForChange(changeid)
        else:
            # following returns None if no filter
            # true or false, if there is a complete filter
            builderid = None
            if 'builderid' in kwargs or 'buildername' in kwargs:
                builderid = yield self.getBuilderId(kwargs)
                if builderid is None:
                    return []
            complete = resultSpec.popBooleanFilter("complete")
            buildrequestid = resultSpec.popIntegerFilter("buildrequestid")
            resultSpec.fieldMapping = self.fieldMapping
            builds = yield self.master.db.builds.getBuilds(
                builderid=builderid,
                buildrequestid=kwargs.get('buildrequestid', buildrequestid),
                workerid=kwargs.get('workerid'),
                complete=complete,
                resultSpec=resultSpec,
            )

        # returns properties' list
        filters = resultSpec.popProperties()

        buildscol = []
        for b in builds:
            data = _db2data(b)
            if kwargs.get('graphql'):
                # let the graphql engine manage the properties
                del data['properties']
            else:
                # Avoid to request DB for Build's properties if not specified
                if filters:
                    props = yield self.master.db.builds.getBuildProperties(data["buildid"])
                    filtered_properties = self._generate_filtered_properties(props, filters)
                    if filtered_properties:
                        data["properties"] = filtered_properties

            buildscol.append(data)
        return buildscol


class Build(base.ResourceType):
    name = "build"
    plural = "builds"
    endpoints = [BuildEndpoint, BuildsEndpoint]
    keyField = "buildid"
    eventPathPatterns = """
        /builders/:builderid/builds/:number
        /builds/:buildid
        /workers/:workerid/builds/:buildid
    """
    subresources = ["Step", "Property"]

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
        locks_duration_s = types.Integer()
        results = types.NoneOk(types.Integer())
        state_string = types.String()
        properties = types.NoneOk(types.SourcedProperties())

    entityType = EntityType(name, 'Build')

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
            state_string='created',
        )
        return res

    @base.updateMethod
    def generateNewBuildEvent(self, buildid):
        return self.generateEvent(buildid, "new")

    @base.updateMethod
    @defer.inlineCallbacks
    def setBuildStateString(self, buildid, state_string):
        res = yield self.master.db.builds.setBuildStateString(
            buildid=buildid, state_string=state_string
        )
        yield self.generateEvent(buildid, "update")
        return res

    @base.updateMethod
    @defer.inlineCallbacks
    def add_build_locks_duration(self, buildid, duration_s):
        yield self.master.db.builds.add_build_locks_duration(buildid=buildid, duration_s=duration_s)
        yield self.generateEvent(buildid, "update")

    @base.updateMethod
    @defer.inlineCallbacks
    def finishBuild(self, buildid, results):
        res = yield self.master.db.builds.finishBuild(buildid=buildid, results=results)
        yield self.generateEvent(buildid, "finished")
        return res
