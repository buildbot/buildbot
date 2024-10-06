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
    pathPatterns = """
        /builders/n:builderid
        /builders/s:buildername
        /masters/n:masterid/builders/n:builderid
    """

    async def get(self, resultSpec, kwargs):
        builderid = await self.getBuilderId(kwargs)
        if builderid is None:
            return None

        builder = await self.master.db.builders.getBuilder(builderid)
        if not builder:
            return None
        if 'masterid' in kwargs:
            if kwargs['masterid'] not in builder.masterids:
                return None
        return _db2data(builder)


class BuildersEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    rootLinkName = 'builders'
    pathPatterns = """
        /builders
        /masters/n:masterid/builders
        /projects/n:projectid/builders
    """

    async def get(self, resultSpec, kwargs):
        bdicts = await self.master.db.builders.getBuilders(
            masterid=kwargs.get('masterid', None), projectid=kwargs.get('projectid', None)
        )
        return [_db2data(bd) for bd in bdicts]

    def get_kwargs_from_graphql(self, parent, resolve_info, args):
        if parent is not None:
            return {'masterid': parent['masterid']}
        return {}


class Builder(base.ResourceType):
    name = "builder"
    plural = "builders"
    endpoints = [BuilderEndpoint, BuildersEndpoint]
    keyField = 'builderid'
    eventPathPatterns = """
        /builders/:builderid
    """
    subresources = ["Build", "Forcescheduler", "Scheduler", "Buildrequest"]

    class EntityType(types.Entity):
        builderid = types.Integer()
        name = types.String()
        masterids = types.List(of=types.Integer())
        description = types.NoneOk(types.String())
        description_format = types.NoneOk(types.String())
        description_html = types.NoneOk(types.String())
        projectid = types.NoneOk(types.Integer())
        tags = types.List(of=types.String())

    entityType = EntityType(name, 'Builder')

    async def generateEvent(self, _id, event):
        builder = await self.master.data.get(('builders', str(_id)))
        self.produceEvent(builder, event)

    @base.updateMethod
    def findBuilderId(self, name):
        return self.master.db.builders.findBuilderId(name)

    @base.updateMethod
    async def updateBuilderInfo(
        self, builderid, description, description_format, description_html, projectid, tags
    ):
        ret = await self.master.db.builders.updateBuilderInfo(
            builderid, description, description_format, description_html, projectid, tags
        )
        await self.generateEvent(builderid, "update")
        return ret

    @base.updateMethod
    async def updateBuilderList(self, masterid, builderNames):
        # get the "current" list of builders for this master, so we know what
        # changes to make.  Race conditions here aren't a great worry, as this
        # is the only master inserting or deleting these records.
        builders = await self.master.db.builders.getBuilders(masterid=masterid)

        # figure out what to remove and remove it
        builderNames_set = set(builderNames)
        for bldr in builders:
            if bldr.name not in builderNames_set:
                builderid = bldr.id
                await self.master.db.builders.removeBuilderMaster(
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
            builderid = await self.master.db.builders.findBuilderId(name)
            await self.master.db.builders.addBuilderMaster(masterid=masterid, builderid=builderid)
            self.master.mq.produce(
                ('builders', str(builderid), 'started'),
                {"builderid": builderid, "masterid": masterid, "name": name},
            )

    # returns a Deferred that returns None
    def _masterDeactivated(self, masterid):
        # called from the masters rtype to indicate that the given master is
        # deactivated
        return self.updateBuilderList(masterid, [])
