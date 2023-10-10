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


from twisted.internet import defer

from buildbot.db import base


class ProjectsConnectorComponent(base.DBConnectorComponent):

    def find_project_id(self, name, auto_create=True):
        name_hash = self.hashColumns(name)
        return self.findSomethingId(
            tbl=self.db.model.projects,
            whereclause=(self.db.model.projects.c.name_hash == name_hash),
            insert_values={
                "name": name,
                "slug": name,
                "name_hash": name_hash,
            }, autoCreate=auto_create)

    @defer.inlineCallbacks
    def get_project(self, projectid):
        def thd(conn):
            q = self.db.model.projects.select(
                whereclause=(self.db.model.projects.c.id == projectid)
            )
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._project_dict_from_row(row)
            res.close()
            return rv
        return (yield self.db.pool.do(thd))

    # returns a Deferred that returns a value
    def get_projects(self):
        def thd(conn):
            tbl = self.db.model.projects
            q = tbl.select()
            q = q.order_by(tbl.c.name)
            res = conn.execute(q)
            return [self._project_dict_from_row(row) for row in res.fetchall()]
        return self.db.pool.do(thd)

    # returns a Deferred that returns a value
    def get_active_projects(self):
        def thd(conn):
            projects_tbl = self.db.model.projects
            builders_tbl = self.db.model.builders
            bm_tbl = self.db.model.builder_masters

            q = projects_tbl.select() \
                .join(builders_tbl) \
                .join(bm_tbl) \
                .order_by(projects_tbl.c.name)
            res = conn.execute(q)
            return [self._project_dict_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    # returns a Deferred that returns a value
    def update_project_info(
        self,
        projectid,
        slug,
        description,
        description_format,
        description_html
    ):
        def thd(conn):
            q = self.db.model.projects.update(
                whereclause=(self.db.model.projects.c.id == projectid)
            )
            conn.execute(
                q,
                slug=slug,
                description=description,
                description_format=description_format,
                description_html=description_html,
            ).close()
        return self.db.pool.do(thd)

    def _project_dict_from_row(self, row):
        return {
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "description": row.description,
            "description_format": row.description_format,
            "description_html": row.description_html,
        }
