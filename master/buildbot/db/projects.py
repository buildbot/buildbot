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
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    from twisted.internet import defer


@dataclass
class ProjectModel:
    id: int
    name: str
    slug: str
    description: str | None
    description_format: str | None
    description_html: str | None

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'ProjectsConnectorComponent '
                'get_project, get_projects, and get_active_projects '
                'no longer return Project as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


class ProjectsConnectorComponent(base.DBConnectorComponent):
    def find_project_id(self, name: str, auto_create: bool = True) -> defer.Deferred[int | None]:
        name_hash = hash_columns(name)
        return self.findSomethingId(
            tbl=self.db.model.projects,
            whereclause=(self.db.model.projects.c.name_hash == name_hash),
            insert_values={
                "name": name,
                "slug": name,
                "name_hash": name_hash,
            },
            autoCreate=auto_create,
        )

    def get_project(self, projectid: int) -> defer.Deferred[ProjectModel | None]:
        def thd(conn) -> ProjectModel | None:
            q = self.db.model.projects.select().where(
                self.db.model.projects.c.id == projectid,
            )
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._model_from_row(row)
            res.close()
            return rv

        return self.db.pool.do(thd)

    def get_projects(self) -> defer.Deferred[list[ProjectModel]]:
        def thd(conn) -> list[ProjectModel]:
            tbl = self.db.model.projects
            q = tbl.select()
            q = q.order_by(tbl.c.name)
            res = conn.execute(q)
            return [self._model_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    def get_active_projects(self) -> defer.Deferred[list[ProjectModel]]:
        def thd(conn) -> list[ProjectModel]:
            projects_tbl = self.db.model.projects
            builders_tbl = self.db.model.builders
            bm_tbl = self.db.model.builder_masters

            q = projects_tbl.select().join(builders_tbl).join(bm_tbl).order_by(projects_tbl.c.name)
            res = conn.execute(q)
            return [self._model_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    # returns a Deferred that returns a value
    def update_project_info(
        self,
        projectid: int,
        slug: str,
        description: str | None,
        description_format: str | None,
        description_html: str | None,
    ) -> defer.Deferred[None]:
        def thd(conn) -> None:
            q = self.db.model.projects.update().where(self.db.model.projects.c.id == projectid)
            conn.execute(
                q.values(
                    slug=slug,
                    description=description,
                    description_format=description_format,
                    description_html=description_html,
                )
            ).close()

        return self.db.pool.do_with_transaction(thd)

    def _model_from_row(self, row):
        return ProjectModel(
            id=row.id,
            name=row.name,
            slug=row.slug,
            description=row.description,
            description_format=row.description_format,
            description_html=row.description_html,
        )
