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
from buildbot.db import NULL
from buildbot.util import epoch2datetime
from buildbot.util import json
from twisted.internet import reactor


class BuildsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst

    def _getBuild(self, whereclause):
        def thd(conn):
            q = self.db.model.builds.select(whereclause=whereclause)
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._builddictFromRow(row)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def getBuild(self, buildid):
        return self._getBuild(self.db.model.builds.c.id == buildid)

    def getBuildByNumber(self, builderid, number):
        return self._getBuild(
            (self.db.model.builds.c.builderid == builderid)
            & (self.db.model.builds.c.number == number))

    def getBuilds(self, builderid=None, buildrequestid=None):
        def thd(conn):
            tbl = self.db.model.builds
            q = tbl.select()
            if builderid:
                q = q.where(tbl.c.builderid == builderid)
            if buildrequestid:
                q = q.where(tbl.c.buildrequestid == buildrequestid)
            res = conn.execute(q)
            return [self._builddictFromRow(row) for row in res.fetchall()]
        return self.db.pool.do(thd)

    def addBuild(self, builderid, buildrequestid, buildslaveid, masterid,
                 state_strings, _reactor=reactor, _race_hook=None):
        started_at = _reactor.seconds()
        state_strings_json = json.dumps(state_strings)

        def thd(conn):
            tbl = self.db.model.builds
            # get the highest current number
            r = conn.execute(sa.select([sa.func.max(tbl.c.number)],
                                       whereclause=(tbl.c.builderid == builderid)))
            number = r.scalar()
            new_number = 1 if number is None else number + 1

            # insert until we are succesful..
            while True:
                if _race_hook:
                    _race_hook(conn)

                try:
                    r = conn.execute(self.db.model.builds.insert(),
                                     dict(number=new_number, builderid=builderid,
                                          buildrequestid=buildrequestid,
                                          buildslaveid=buildslaveid, masterid=masterid,
                                          started_at=started_at, complete_at=None,
                                          state_strings_json=state_strings_json))
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                    new_number += 1
                    continue
                return r.inserted_primary_key[0], new_number
        return self.db.pool.do(thd)

    def setBuildStateStrings(self, buildid, state_strings):
        def thd(conn):
            tbl = self.db.model.builds

            q = tbl.update(whereclause=(tbl.c.id == buildid))
            conn.execute(q, state_strings_json=json.dumps(state_strings))
        return self.db.pool.do(thd)

    def finishBuild(self, buildid, results, _reactor=reactor):
        def thd(conn):
            tbl = self.db.model.builds
            q = tbl.update(whereclause=(tbl.c.id == buildid))
            conn.execute(q,
                         complete_at=_reactor.seconds(),
                         results=results)
        return self.db.pool.do(thd)

    def finishBuildsFromMaster(self, masterid, results, _reactor=reactor):
        def thd(conn):
            tbl = self.db.model.builds
            q = tbl.update()
            q = q.where(tbl.c.masterid == masterid)
            q = q.where(tbl.c.results == NULL)

            conn.execute(q,
                         complete_at=_reactor.seconds(),
                         results=results)
        return self.db.pool.do(thd)

    def _builddictFromRow(self, row):
        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)

        return dict(
            id=row.id,
            number=row.number,
            builderid=row.builderid,
            buildrequestid=row.buildrequestid,
            buildslaveid=row.buildslaveid,
            masterid=row.masterid,
            started_at=mkdt(row.started_at),
            complete_at=mkdt(row.complete_at),
            state_strings=json.loads(row.state_strings_json),
            results=row.results)
