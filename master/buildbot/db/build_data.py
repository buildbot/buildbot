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

from twisted.internet import defer

from buildbot.db import base


class BuildDataDict(dict):
    pass


class BuildDataConnectorComponent(base.DBConnectorComponent):

    def _insert_race_hook(self, conn):
        # called so tests can simulate a race condition during insertion
        pass

    @defer.inlineCallbacks
    def setBuildData(self, buildid, name, value, source):
        def thd(conn):
            build_data_table = self.db.model.build_data

            update_values = {
                'value': value,
                'source': source
            }

            insert_values = {
                'buildid': buildid,
                'name': name,
                'value': value,
                'source': source,
            }

            while True:
                q = build_data_table.update()
                q = q.where((build_data_table.c.buildid == buildid) &
                            (build_data_table.c.name == name))
                q = q.values(update_values)
                r = conn.execute(q)
                if r.rowcount > 0:
                    return
                r.close()

                self._insert_race_hook(conn)

                try:
                    q = build_data_table.insert().values(insert_values)
                    r = conn.execute(q)
                    return
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                    # there's been a competing insert, retry
                    pass

        yield self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getBuildData(self, buildid, name):
        def thd(conn):
            build_data_table = self.db.model.build_data

            q = build_data_table.select().where((build_data_table.c.buildid == buildid) &
                                                (build_data_table.c.name == name))
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            return self._row2dict(conn, row)
        res = yield self.db.pool.do(thd)
        return res

    @defer.inlineCallbacks
    def getBuildDataNoValue(self, buildid, name):
        def thd(conn):
            build_data_table = self.db.model.build_data

            q = sa.select([build_data_table.c.buildid,
                           build_data_table.c.name,
                           build_data_table.c.source])
            q = q.where((build_data_table.c.buildid == buildid) &
                        (build_data_table.c.name == name))
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            return self._row2dict_novalue(conn, row)
        res = yield self.db.pool.do(thd)
        return res

    @defer.inlineCallbacks
    def getAllBuildDataNoValues(self, buildid):
        def thd(conn):
            build_data_table = self.db.model.build_data

            q = sa.select([build_data_table.c.buildid,
                           build_data_table.c.name,
                           build_data_table.c.source])
            q = q.where(build_data_table.c.buildid == buildid)

            return [self._row2dict_novalue(conn, row)
                    for row in conn.execute(q).fetchall()]
        res = yield self.db.pool.do(thd)
        return res

    def _row2dict(self, conn, row):
        return BuildDataDict(buildid=row.buildid,
                             name=row.name,
                             value=row.value,
                             source=row.source)

    def _row2dict_novalue(self, conn, row):
        return BuildDataDict(buildid=row.buildid,
                             name=row.name,
                             value=None,
                             source=row.source)
