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

import sqlalchemy as sa

from buildbot.db import base


class BuildslavesConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def getBuildslaves(self):
        def thd(conn):
            tbl = self.db.model.buildslaves
            rows = conn.execute(tbl.select()).fetchall()

            dicts = []
            if rows:
                for row in rows:
                    dicts.append({
                        'slaveid': row.id,
                        'name': row.name
                    })
            return dicts
        d = self.db.pool.do(thd)
        return d

    def getBuildslaveByName(self, name):
        def thd(conn):
            tbl = self.db.model.buildslaves
            res = conn.execute(tbl.select(whereclause=(tbl.c.name == name)))
            row = res.fetchone()

            rv = None
            if row:
                rv = self._bdictFromRow(row)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def updateBuildslave(self, name, slaveinfo, _race_hook=None):
        def thd(conn):
            transaction = conn.begin()

            tbl = self.db.model.buildslaves

            # first try update, then try insert
            q = tbl.update(whereclause=(tbl.c.name == name))
            res = conn.execute(q, info=slaveinfo)

            if res.rowcount == 0:
                _race_hook and _race_hook(conn)

                # the update hit 0 rows, so try inserting a new one
                try:
                    q = tbl.insert()
                    res = conn.execute(q,
                                       name=name,
                                       info=slaveinfo)
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                    # someone else beat us to the punch inserting this row;
                    # let them win.
                    transaction.rollback()
                    return

            transaction.commit()
        return self.db.pool.do(thd)

    def _bdictFromRow(self, row):
        return {
            'slaveid': row.id,
            'name': row.name,
            'slaveinfo': row.info
        }
