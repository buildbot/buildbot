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
    from buildbot.db.codebase_commits import CodebaseCommitModel


def commit_db_to_data(model: CodebaseCommitModel) -> dict[str, Any]:
    return {
        "commitid": model.id,
        "codebaseid": model.codebaseid,
        'author': model.author,
        'committer': model.committer,
        'comments': model.comments,
        'when_timestamp': model.when_timestamp,
        'revision': model.revision,
        'parent_commitid': model.parent_commitid,
    }


commits_field_map = {
    'commitid': 'codebase_commits.id',
    'codebaseid': 'codebase_commits.codebaseid',
    'author': 'codebase_commits.author',
    'committer': 'codebase_commits.committer',
    'comments': 'codebase_commits.comments',
    'when_timestamp': 'codebase_commits.when_timestamp',
    'parent_commitid': 'codebase_commits.parent_commitid',
}


class CodebaseCommitEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/commits/n:commitid",
    ]

    @async_to_deferred
    async def get(self, result_spec: base.ResultSpec, kwargs: Any) -> dict[str, Any] | None:
        commit = await self.master.db.codebase_commits.get_commit(kwargs['commitid'])
        if not commit:
            return None
        return commit_db_to_data(commit)


class CodebaseCommitByRevisionEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/codebases/n:codebaseid/commits_by_revision/s:revision",
    ]

    @async_to_deferred
    async def get(self, result_spec: base.ResultSpec, kwargs: Any) -> dict[str, Any] | None:
        commit = await self.master.db.codebase_commits.get_commit_by_revision(
            codebaseid=kwargs['codebaseid'], revision=kwargs['revision']
        )
        if not commit:
            return None
        return commit_db_to_data(commit)


class CodebaseCommitsEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/codebases/n:codebaseid/commits",
    ]

    @async_to_deferred
    async def get(self, result_spec: base.ResultSpec, kwargs: Any) -> list[dict[str, Any]]:
        result_spec.fieldMapping = commits_field_map
        commits = await self.master.db.codebase_commits.get_commits(
            codebaseid=kwargs['codebaseid'], result_spec=result_spec
        )
        return [commit_db_to_data(c) for c in commits]


class CodebaseCommit(base.ResourceType):
    name = "commit"
    plural = "commits"
    endpoints = [CodebaseCommitEndpoint, CodebaseCommitByRevisionEndpoint, CodebaseCommitsEndpoint]
    eventPathPatterns = [
        "/commits/:commitid",
        "/codebases/:codebaseid/commits/:commitid",
    ]

    class EntityType(types.Entity):
        commitid = types.Integer()
        codebaseid = types.Integer()
        author = types.String()
        committer = types.NoneOk(types.String())
        comments = types.String()
        when_timestamp = types.Integer()
        revision = types.String()
        parent_commitid = types.NoneOk(types.Integer())

    entityType = EntityType(name)

    @async_to_deferred
    async def generate_event(self, _id: int, event: str) -> None:
        commit = await self.master.data.get(('commits', str(_id)))
        self.produceEvent(commit, event)

    @base.updateMethod
    @async_to_deferred
    async def add_commit(
        self,
        *,
        codebaseid: int,
        author: str,
        committer: str | None = None,
        files: list[str] | None = None,
        comments: str,
        when_timestamp: int,
        revision: str,
        parent_commitid: int | None = None,
    ) -> None:
        commitid = await self.master.db.codebase_commits.add_commit(
            codebaseid=codebaseid,
            author=author,
            committer=committer,
            files=files,
            comments=comments,
            when_timestamp=when_timestamp,
            revision=revision,
            parent_commitid=parent_commitid,
        )
        await self.generate_event(commitid, 'new')
        return commitid


class CodebaseCommitsGraphEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/codebases/n:codebaseid/commit_range/n:commitid1/n:commitid2/commits_common_parent",
    ]

    @async_to_deferred
    async def get(self, resultSpec: base.ResultSpec, kwargs: Any) -> dict[str, Any] | None:
        r = await self.master.db.codebase_commits.get_first_common_commit_with_ranges(
            int(kwargs.get('commitid1')), int(kwargs.get('commitid2'))
        )

        if r is None:
            return None
        return {
            'common': r.common_commit_id,
            'to1': r.to1_commit_ids,
            'to2': r.to2_commit_ids,
        }


class CodebaseCommitsGraph(base.ResourceType):
    name = "commit_graph"
    plural = "commit_graphs"
    endpoints = [CodebaseCommitsGraphEndpoint]

    class EntityType(types.Entity):
        common = types.Integer()
        to1 = types.List(of=types.Integer())
        to2 = types.List(of=types.Integer())

    entityType = EntityType(name)
