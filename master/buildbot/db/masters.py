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

from __future__ import absolute_import
from __future__ import print_function

import sqlalchemy as sa

from twisted.internet import reactor

from buildbot.db import base
from buildbot.util import epoch2datetime


class MasterDict(dict):
    pass


class MastersConnectorComponent(base.DBConnectorComponent):
    data2db = {"masterid": "id", "link": "id"}

    def findMasterId(self, name, _reactor=reactor):
        tbl = self.db.model.masters
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name == name),
            insert_values=dict(
                name=name,
                name_hash=self.hashColumns(name),
                active=0,  # initially inactive
                last_active=_reactor.seconds()
            ))

    def setMasterState(self, masterid, active, _reactor=reactor):
        def thd(conn):
            tbl = self.db.model.masters
            whereclause = (tbl.c.id == masterid)

            # get the old state
            r = conn.execute(sa.select([tbl.c.active],
                                       whereclause=whereclause))
            rows = r.fetchall()
            r.close()
            if not rows:
                return False  # can't change a row that doesn't exist..
            was_active = bool(rows[0].active)

            if not active:
                # if we're marking inactive, then delete any links to this
                # master
                sch_mst_tbl = self.db.model.scheduler_masters
                q = sch_mst_tbl.delete(
                    whereclause=(sch_mst_tbl.c.masterid == masterid))
                conn.execute(q)

            # set the state (unconditionally, just to be safe)
            q = tbl.update(whereclause=whereclause)
            q = q.values(active=1 if active else 0)
            if active:
                q = q.values(last_active=_reactor.seconds())
            conn.execute(q)

            # return True if there was a change in state
            return was_active != bool(active)
        return self.db.pool.do(thd)

    def getMaster(self, masterid):
        def thd(conn):
            tbl = self.db.model.masters
            res = conn.execute(tbl.select(
                whereclause=(tbl.c.id == masterid)))
            row = res.fetchone()

            rv = None
            if row:
                rv = self._masterdictFromRow(row)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def getMasters(self):
        def thd(conn):
            tbl = self.db.model.masters
            return [
                self._masterdictFromRow(row)
                for row in conn.execute(tbl.select()).fetchall()]
        return self.db.pool.do(thd)

    def setAllMastersActiveLongTimeAgo(self, _reactor=reactor):
        def thd(conn):
            tbl = self.db.model.masters
            q = tbl.update().values(active=1, last_active=0)
            conn.execute(q)
        return self.db.pool.do(thd)

    def _masterdictFromRow(self, row):
        return MasterDict(id=row.id, name=row.name,
                          active=bool(row.active),
                          last_active=epoch2datetime(row.last_active))
