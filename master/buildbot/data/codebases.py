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
from typing import Any

from buildbot.data import base
from buildbot.data import types
from buildbot.util.twisted import async_to_deferred

if TYPE_CHECKING:
    from buildbot.db.codebases import CodebaseModel


def codebase_db_to_data(model: CodebaseModel) -> dict[str, Any]:
    return {
        "codebaseid": model.id,
        "name": model.name,
        "slug": model.slug,
        "projectid": model.projectid,
    }


codebases_field_map = {
    'codebaseid': 'codebases.id',
    'name': 'codebases.name',
    'slug': 'codebases.slug',
    'projectid': 'codebases.projectid',
}


class CodebaseEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/codebases/n:codebaseid",
        "/projects/n:projectid/codebases/i:codebasename",
    ]

    @async_to_deferred
    async def get(self, result_spec: base.ResultSpec, kwargs: Any) -> dict[str, Any] | None:
        result_spec.fieldMapping = codebases_field_map
        if 'codebaseid' in kwargs:
            codebase = await self.master.db.codebases.get_codebase(kwargs['codebaseid'])
            if not codebase:
                return None
            return codebase_db_to_data(codebase)

        codebases = await self.master.db.codebases.get_codebases(kwargs['projectid'])
        codebases = [c for c in codebases if c.name == kwargs['codebasename']]
        if not codebases:
            return None
        return codebase_db_to_data(codebases[0])


class CodebasesEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    rootLinkName = 'codebases'
    pathPatterns = [
        "/codebases",
    ]

    @async_to_deferred
    async def get(self, result_spec: base.ResultSpec, kwargs: Any) -> list[dict[str, Any]]:
        result_spec.fieldMapping = codebases_field_map
        codebases = await self.master.db.codebases.get_codebases(result_spec=result_spec)
        return [codebase_db_to_data(c) for c in codebases]


class Codebase(base.ResourceType):
    name = "codebase"
    plural = "codebases"
    endpoints = [CodebaseEndpoint, CodebasesEndpoint]
    eventPathPatterns = [
        "/codebases/:codebaseid",
    ]

    class EntityType(types.Entity):
        codebaseid = types.Integer()
        projectid = types.Integer()
        name = types.Identifier(70)
        slug = types.Identifier(70)

    entityType = EntityType(name)

    @async_to_deferred
    async def generate_event(self, _id: int, event: str) -> None:
        codebase = await self.master.data.get(('codebases', str(_id)))
        self.produceEvent(codebase, event)

    @base.updateMethod
    def find_codebase_id(
        self, *, projectid: int, name: str, auto_create: bool = True
    ) -> int | None:
        return self.master.db.codebases.find_codebase_id(
            projectid=projectid, name=name, auto_create=auto_create
        )

    @base.updateMethod
    @async_to_deferred
    async def update_codebase_info(
        self,
        *,
        codebaseid: int,
        projectid: int,
        slug: str,
    ) -> None:
        await self.master.db.codebases.update_codebase_info(
            codebaseid=codebaseid, projectid=projectid, slug=slug
        )
        await self.generate_event(codebaseid, "update")
