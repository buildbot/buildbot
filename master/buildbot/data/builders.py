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

if TYPE_CHECKING:
    from buildbot.db.builders import BuilderModel


def _db2data(builder: BuilderModel):
    return {
        "builderid": builder.id,
        "name": builder.name,
        "masterids": builder.masterids,
        "description": builder.description,
        "description_format": builder.description_format,
        "description_html": builder.description_html,
        "projectid": builder.projectid,
        "tags": builder.tags,
    }


class BuilderEndpoint(base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/builders/n:builderid",
        "/builders/s:buildername",
        "/masters/n:masterid/builders/n:builderid",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        builderid = yield self.getBuilderId(kwargs)
        if builderid is None:
            return None

        builder = yield self.master.db.builders.getBuilder(builderid)
        if not builder:
            return None
        if 'masterid' in kwargs:
            if kwargs['masterid'] not in builder.masterids:
                return None
        return _db2data(builder)


class BuildersEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    rootLinkName = 'builders'
    pathPatterns = [
        "/builders",
        "/masters/n:masterid/builders",
        "/projects/n:projectid/builders",
        "/workers/n:workerid/builders",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        bdicts = yield self.master.db.builders.getBuilders(
            masterid=kwargs.get('masterid', None),
            projectid=kwargs.get('projectid', None),
            workerid=kwargs.get('workerid', None),
        )
        return [_db2data(bd) for bd in bdicts]


class Builder(base.ResourceType):
    name = "builder"
    plural = "builders"
    endpoints = [BuilderEndpoint, BuildersEndpoint]
    eventPathPatterns = [
        "/builders/:builderid",
    ]

    class EntityType(types.Entity):
        builderid = types.Integer()
        name = types.String()
        masterids = types.List(of=types.Integer())
        description = types.NoneOk(types.String())
        description_format = types.NoneOk(types.String())
        description_html = types.NoneOk(types.String())
        projectid = types.NoneOk(types.Integer())
        tags = types.List(of=types.String())

    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, _id, event):
        builder = yield self.master.data.get(('builders', str(_id)))
        self.produceEvent(builder, event)

    @base.updateMethod
    def findBuilderId(self, name: str) -> defer.Deferred[int]:
        return self.master.db.builders.findBuilderId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def updateBuilderInfo(
        self,
        builderid: int,
        description: str | None,
        description_format: str | None,
        description_html: str | None,
        projectid: int,
        tags: list[int | str],
    ):
        ret = yield self.master.db.builders.updateBuilderInfo(
            builderid, description, description_format, description_html, projectid, tags
        )
        yield self.generateEvent(builderid, "update")
        return ret

    @base.updateMethod
    @defer.inlineCallbacks
    def updateBuilderList(self, masterid: int, builderNames: list[str]):
        # get the "current" list of builders for this master, so we know what
        # changes to make.  Race conditions here aren't a great worry, as this
        # is the only master inserting or deleting these records.
        builders = yield self.master.db.builders.getBuilders(masterid=masterid)

        # figure out what to remove and remove it
        builderNames_set = set(builderNames)
        for bldr in builders:
            if bldr.name not in builderNames_set:
                builderid = bldr.id
                yield self.master.db.builders.removeBuilderMaster(
                    masterid=masterid, builderid=builderid
                )
                self.master.mq.produce(
                    ('builders', str(builderid), 'stopped'),
                    {"builderid": builderid, "masterid": masterid, "name": bldr.name},
                )
            else:
                builderNames_set.remove(bldr.name)

        # now whatever's left in builderNames_set is new
        for name in builderNames_set:
            builderid = yield self.master.db.builders.findBuilderId(name)
            yield self.master.db.builders.addBuilderMaster(masterid=masterid, builderid=builderid)
            self.master.mq.produce(
                ('builders', str(builderid), 'started'),
                {"builderid": builderid, "masterid": masterid, "name": name},
            )

    # returns a Deferred that returns None
    def _masterDeactivated(self, masterid):
        # called from the masters rtype to indicate that the given master is
        # deactivated
        return self.updateBuilderList(masterid, [])
