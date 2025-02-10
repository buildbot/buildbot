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
from typing import Callable

import sqlalchemy as sa

from buildbot.db import base
from buildbot.util.sautils import hash_columns
from buildbot.util.twisted import async_to_deferred

if TYPE_CHECKING:
    from sqlalchemy.future.engine import Connection

    from buildbot.data.resultspec import ResultSpec


@dataclass
class CodebaseBranchModel:
    id: int
    codebaseid: int
    name: str
    commitid: int | None
    last_timestamp: int


class CodebaseBranchConnectorComponent(base.DBConnectorComponent):
    @async_to_deferred
    async def get_branch(self, id: int) -> CodebaseBranchModel | None:
        def thd(conn: Connection) -> CodebaseBranchModel | None:
            tbl = self.db.model.codebase_branches
            q = tbl.select().where(tbl.c.id == id)
            res = conn.execute(q)
            row = res.fetchone()
            rv = self._model_from_row(row) if row else None
            res.close()
            return rv

        return await self.db.pool.do(thd)

    @async_to_deferred
    async def get_branch_by_name(self, codebaseid: int, name: str) -> CodebaseBranchModel | None:
        def thd(conn: Connection) -> CodebaseBranchModel | None:
            tbl = self.db.model.codebase_branches
            q = tbl.select().where((tbl.c.codebaseid == codebaseid) & (tbl.c.name == name))
            res = conn.execute(q)
            row = res.fetchone()
            rv = self._model_from_row(row) if row else None
            res.close()
            return rv

        return await self.db.pool.do(thd)

    @async_to_deferred
    async def get_branches(
        self, codebaseid: int, result_spec: ResultSpec | None = None
    ) -> list[CodebaseBranchModel]:
        def thd(conn: Connection) -> list[CodebaseBranchModel]:
            tbl = self.db.model.codebase_branches
            q = tbl.select().where(tbl.c.codebaseid == codebaseid)

            if result_spec is not None:
                return result_spec.thd_execute(conn, q, self._model_from_row)

            res = conn.execute(q)
            rv = [self._model_from_row(row) for row in res.fetchall()]
            res.close()
            return rv

        return await self.db.pool.do(thd)

    @async_to_deferred
    async def update_branch(
        self,
        *,
        codebaseid: int,
        name: str,
        commitid: int | None = None,
        last_timestamp: int,
        _race_hook: Callable[[Connection], None] | None = None,
    ) -> None:
        tbl = self.db.model.codebase_branches
        self.checkLength(tbl.c.name, name)

        def thd(conn: Connection) -> None:
            try:
                self.db.upsert(
                    conn,
                    tbl,
                    where_values=(
                        (tbl.c.codebaseid, codebaseid),
                        (tbl.c.name_hash, hash_columns(name)),
                    ),
                    update_values=(
                        (tbl.c.commitid, commitid),
                        (tbl.c.name, name),
                        (tbl.c.last_timestamp, last_timestamp),
                    ),
                    _race_hook=_race_hook,
                )
                conn.commit()
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                # someone else beat us to the punch inserting this row;
                # let them win.
                conn.rollback()

        await self.db.pool.do_with_transaction(thd)

    def _model_from_row(self, row: sa.Row) -> CodebaseBranchModel:
        return CodebaseBranchModel(
            id=row.id,
            codebaseid=row.codebaseid,
            name=row.name,
            commitid=row.commitid,
            last_timestamp=row.last_timestamp,
        )
