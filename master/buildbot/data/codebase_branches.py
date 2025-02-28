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
    from buildbot.db.codebase_branches import CodebaseBranchModel


def branch_db_to_data(model: CodebaseBranchModel) -> dict[str, Any]:
    return {
        "branchid": model.id,
        "codebaseid": model.codebaseid,
        "name": model.name,
        "commitid": model.commitid,
        "last_timestamp": model.last_timestamp,
    }


branches_field_map = {
    'branchid': 'codebase_branches.id',
    'codebaseid': 'codebase_branches.codebaseid',
    'name': 'codebase_branches.name',
    'commitid': 'codebase_branches.commitid',
    'last_timestamp': 'codebase_branches.last_timestamp',
}


class CodebaseBranchEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/branches/n:branchid",
    ]

    @async_to_deferred
    async def get(self, result_spec: base.ResultSpec, kwargs: Any) -> dict[str, Any] | None:
        branch = await self.master.db.codebase_branches.get_branch(kwargs['branchid'])
        if not branch:
            return None
        return branch_db_to_data(branch)


class CodebaseBranchesEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/codebases/n:codebaseid/branches",
    ]

    @async_to_deferred
    async def get(self, result_spec: base.ResultSpec, kwargs: Any) -> list[dict[str, Any]]:
        result_spec.fieldMapping = branches_field_map
        branches = await self.master.db.codebase_branches.get_branches(
            kwargs['codebaseid'], result_spec=result_spec
        )
        return [branch_db_to_data(c) for c in branches]


class CodebaseBranch(base.ResourceType):
    name = "branch"
    plural = "branches"
    endpoints = [CodebaseBranchEndpoint, CodebaseBranchesEndpoint]
    eventPathPatterns = [
        "/branches/:branchid",
    ]

    class EntityType(types.Entity):
        branchid = types.Integer()
        codebaseid = types.Integer()
        name = types.String()
        commitid = types.Integer()
        last_timestamp = types.Integer()

    entityType = EntityType(name)

    @async_to_deferred
    async def generate_event(self, _id: int, event: str) -> None:
        branch = await self.master.data.get(('branches', _id))
        self.produceEvent(branch, event)

    @base.updateMethod
    @async_to_deferred
    async def update_branch(
        self,
        *,
        codebaseid: int,
        name: str,
        commitid: int | None = None,
        last_timestamp: int,
    ) -> None:
        await self.master.db.codebase_branches.update_branch(
            codebaseid=codebaseid,
            name=name,
            commitid=commitid,
            last_timestamp=last_timestamp,
        )
        branch = await self.master.db.codebase_branches.get_branch_by_name(
            codebaseid=codebaseid, name=name
        )
        assert branch is not None
        await self.generate_event(branch.id, 'update')
