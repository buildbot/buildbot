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

from buildbot.db import base
from buildbot.util.sautils import hash_columns

if TYPE_CHECKING:
    import sqlalchemy as sa
    from twisted.internet import defer

    from buildbot.data.resultspec import ResultSpec


@dataclass
class CodebaseModel:
    id: int
    projectid: int
    name: str
    slug: str


class CodebasesConnectorComponent(base.DBConnectorComponent):
    def find_codebase_id(
        self, *, projectid: int, name: str, auto_create: bool = True
    ) -> defer.Deferred[int | None]:
        tbl = self.db.model.codebases
        name_hash = hash_columns(name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=((tbl.c.projectid == projectid) & (tbl.c.name_hash == name_hash)),
            insert_values={
                'name': name,
                'name_hash': name_hash,
                'slug': name,
                'projectid': projectid,
            },
            autoCreate=auto_create,
        )

    def get_codebase(self, codebaseid: int) -> defer.Deferred[CodebaseModel | None]:
        def thd(conn: sa.engine.Connection) -> CodebaseModel | None:
            q = self.db.model.codebases.select().where(
                self.db.model.codebases.c.id == codebaseid,
            )
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._model_from_row(row)
            res.close()
            return rv

        return self.db.pool.do(thd)

    def get_codebases(
        self, projectid: int | None = None, result_spec: ResultSpec | None = None
    ) -> defer.Deferred[list[CodebaseModel]]:
        def thd(conn: sa.engine.Connection) -> list[CodebaseModel]:
            tbl = self.db.model.codebases
            q = tbl.select()
            if projectid is not None:
                q = q.where(tbl.c.projectid == projectid)
            if result_spec is not None:
                return result_spec.thd_execute(conn, q, lambda row: self._model_from_row(row))
            res = conn.execute(q)
            return [self._model_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    def update_codebase_info(
        self,
        *,
        codebaseid: int,
        projectid: int,
        slug: str,
    ) -> defer.Deferred[None]:
        def thd(conn: sa.engine.Connection) -> None:
            q = self.db.model.codebases.update().where(self.db.model.codebases.c.id == codebaseid)
            conn.execute(
                q.values(
                    projectid=projectid,
                    slug=slug,
                )
            ).close()

        return self.db.pool.do_with_transaction(thd)

    def _model_from_row(self, row: sa.engine.Row) -> CodebaseModel:
        return CodebaseModel(
            id=row.id,
            projectid=row.projectid,
            name=row.name,
            slug=row.slug,
        )
