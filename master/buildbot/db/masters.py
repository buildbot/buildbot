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

import hashlib
import sqlalchemy as sa
from twisted.internet import reactor
from buildbot.util import epoch2datetime
from buildbot.db import base

class MasterDict(dict):
    pass

class MastersConnectorComponent(base.DBConnectorComponent):

    def findMasterId(self, master_name, _race_hook=None, _reactor=reactor):
        def thd(conn, no_recurse=False):
            tbl = self.db.model.masters

            # try to find the master
            q = sa.select([ tbl.c.id ],
                    whereclause=(tbl.c.master_name == master_name))
            rows = conn.execute(q).fetchall()

            # found it!
            if rows:
                return rows[0].id

            _race_hook and _race_hook(conn)

            try:
                r = conn.execute(tbl.insert(), dict(
                    master_name=master_name,
                    master_name_hash=hashlib.sha1(master_name).hexdigest(),
                    active=0, # initially inactive
                    last_active=_reactor.seconds()
                    ))
                return r.inserted_primary_key[0]
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                # try it all over again, in case there was an overlapping,
                # identical call, but only retry once.
                if no_recurse:
                    raise
                return thd(conn, no_recurse=True)
        return self.db.pool.do(thd)

    def setMasterState(self, masterid, active, _reactor=reactor):
        def thd(conn):
            tbl = self.db.model.masters
            whereclause=(tbl.c.id == masterid)

            # get the old state
            r = conn.execute(sa.select([tbl.c.active],
                                whereclause=whereclause))
            rows = r.fetchall()
            if not rows:
                return False # can't change a row that doesn't exist..
            was_active = bool(rows[0].active)

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
                for row in conn.execute(tbl.select()).fetchall() ]
        return self.db.pool.do(thd)

    def _masterdictFromRow(self, row):
        return MasterDict(id=row.id, master_name=row.master_name,
                    active=bool(row.active),
                    last_active=epoch2datetime(row.last_active))
