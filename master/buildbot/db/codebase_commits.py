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

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any
from typing import Awaitable
from typing import Callable

from buildbot.db import base
from buildbot.util.twisted import async_to_deferred

if TYPE_CHECKING:
    import sqlalchemy as sa
    from twisted.internet import defer

    from buildbot.data.resultspec import ResultSpec


@dataclass
class CodebaseCommitModel:
    id: int
    codebaseid: int
    author: str
    committer: str | None
    comments: str
    when_timestamp: int
    revision: str
    parent_commitid: int | None


UNKNOWN_COMMIT_ID = -1


@dataclass
class CommonCommitInfo:
    common_commit_id: int
    to1_commit_ids: list[int]
    to2_commit_ids: list[int]


class CodebaseCommitCache:
    def __init__(self) -> None:
        self._parents: dict[int, int] = {}

    def add_parent(self, id: int, parent_id: int) -> None:
        self._parents[id] = parent_id

    def get_parent(self, id: int) -> int:
        return self._parents.get(id, UNKNOWN_COMMIT_ID)

    async def get_parent_with_fallback(
        self, id: int, get_parent_fallback: Callable[[int], Awaitable[int]], default: int | None
    ) -> int | None:
        parent_id: int | None = self.get_parent(id)
        if parent_id == UNKNOWN_COMMIT_ID:
            parent_id = await get_parent_fallback(id)
            if parent_id == UNKNOWN_COMMIT_ID:
                parent_id = default
            else:
                self.add_parent(id, parent_id)
        return parent_id

    async def first_common_parent_with_ranges(
        self,
        id1: int,
        id2: int,
        get_parent_fallback: Callable[[int], Awaitable[int]],
        depth: int = 100,
    ) -> CommonCommitInfo | None:
        """
        Evaluates the commit graph and finds first parent of both id1 and id2 commits.

        The function returns a tuple that consists of:
        - the parent commit id
        - list of commit IDs from the parent commit to id1 (including parent commit and id1)
        - list of commit IDs from the parent commit to id2 (including parent commit and id2)

        If no parent is found, returns None
        """
        if id1 == id2:
            parent1 = await self.get_parent_with_fallback(
                id1, get_parent_fallback, UNKNOWN_COMMIT_ID
            )
            if parent1 == UNKNOWN_COMMIT_ID:
                return None
            return CommonCommitInfo(id1, [id1], [id1])

        parent1 = id1
        parent2 = id2
        known1 = [id1]
        known2 = [id2]

        for i in range(depth):
            parent1 = await self.get_parent_with_fallback(parent1, get_parent_fallback, None)
            if parent1 is None:
                break
            known1.append(parent1)

        if parent2 in known1:
            return CommonCommitInfo(parent2, known1[known1.index(parent2) + 1 :: -1], known2)

        for i in range(depth):
            parent2_new = await self.get_parent_with_fallback(parent2, get_parent_fallback, None)
            if parent2_new is None:
                break
            parent2 = parent2_new
            known2.append(parent2)
            if parent2 in known1:
                return CommonCommitInfo(parent2, known1[known1.index(parent2) :: -1], known2[::-1])

        return None


class CodebaseCommitsConnectorComponent(base.DBConnectorComponent):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cache = CodebaseCommitCache()

    @async_to_deferred
    async def get_commit_by_revision(
        self, *, codebaseid: int, revision: str
    ) -> CodebaseCommitModel | None:
        def thd(conn: sa.engine.Connection) -> CodebaseCommitModel | None:
            tbl = self.db.model.codebase_commits
            q = tbl.select().where(
                (tbl.c.codebaseid == codebaseid) & (tbl.c.revision == revision),
            )
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._model_from_row(row)
            res.close()
            return rv

        commit = await self.db.pool.do(thd)
        if commit is not None:
            self._cache.add_parent(commit.id, commit.parent_commitid)
        return commit

    @async_to_deferred
    async def _get_commit_parent_commitid(self, id: int) -> int:
        def thd(conn: sa.engine.Connection) -> int | None:
            q = self.db.model.codebase_commits.select().where(
                self.db.model.codebase_commits.c.id == id,
            )
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = row.parent_commitid
            else:
                rv = UNKNOWN_COMMIT_ID
            res.close()
            return rv

        return await self.db.pool.do(thd)

    @async_to_deferred
    async def get_first_common_commit_with_ranges(
        self, first_commitid: int, last_commitid: int, depth: int = 100
    ) -> CommonCommitInfo | None:
        return await self._cache.first_common_parent_with_ranges(
            first_commitid, last_commitid, self._get_commit_parent_commitid, depth=depth
        )

    def get_commit(self, id: int) -> defer.Deferred[CodebaseCommitModel | None]:
        def thd(conn: sa.engine.Connection) -> CodebaseCommitModel | None:
            tbl = self.db.model.codebase_commits
            q = tbl.select().where(tbl.c.id == id)
            res = conn.execute(q)

            row = res.fetchone()
            rv = self._model_from_row(row) if row else None
            res.close()
            return rv

        return self.db.pool.do(thd)

    def get_commits_by_id(
        self, commit_ids: list[int]
    ) -> defer.Deferred[list[CodebaseCommitModel | None]]:
        def thd(conn: sa.engine.Connection) -> list[CodebaseCommitModel | None]:
            tbl = self.db.model.codebase_commits
            q = tbl.select().where(tbl.c.id.in_(commit_ids))
            res = conn.execute(q)
            commits = {row.id: self._model_from_row(row) for row in res.fetchall()}
            res.close()
            return [commits.get(id, None) for id in commit_ids]

        return self.db.pool.do(thd)

    def get_commits(
        self, *, codebaseid: int, result_spec: ResultSpec | None = None
    ) -> defer.Deferred[list[CodebaseCommitModel]]:
        def thd(conn: sa.engine.Connection) -> list[CodebaseCommitModel]:
            tbl = self.db.model.codebase_commits
            q = tbl.select().where(tbl.c.codebaseid == codebaseid)

            if result_spec is not None:
                return result_spec.thd_execute(conn, q, lambda row: self._model_from_row(row))

            res = conn.execute(q)
            rv = [self._model_from_row(row) for row in res.fetchall()]
            res.close()
            return rv

        return self.db.pool.do(thd)

    def _model_from_row(self, row: sa.engine.Row) -> CodebaseCommitModel:
        return CodebaseCommitModel(
            id=row.id,
            codebaseid=row.codebaseid,
            author=row.author,
            committer=row.committer,
            comments=row.comments,
            when_timestamp=row.when_timestamp,
            revision=row.revision,
            parent_commitid=row.parent_commitid,
        )

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
    ) -> int:
        self.checkLength(self.db.model.codebase_commits.c.author, author)
        self.checkLength(self.db.model.codebase_commits.c.committer, committer)
        self.checkLength(self.db.model.codebase_commits.c.revision, revision)

        # TODO: handle files

        def thd(conn: sa.engine.Connection) -> int:
            q = self.db.model.codebase_commits.insert()
            r = conn.execute(
                q.values(
                    codebaseid=codebaseid,
                    author=author,
                    committer=committer,
                    comments=comments,
                    when_timestamp=when_timestamp,
                    revision=revision,
                    parent_commitid=parent_commitid,
                )
            )
            conn.commit()
            got_id = r.inserted_primary_key[0]
            r.close()

            return got_id

        return await self.db.pool.do_with_transaction(thd)
