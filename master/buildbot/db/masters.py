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

import dataclasses
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.python import deprecate
from twisted.python import versions

from buildbot.db import base
from buildbot.util import epoch2datetime
from buildbot.util.sautils import hash_columns
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    import datetime

    from twisted.internet import defer


@dataclasses.dataclass
class MasterModel:
    id: int
    name: str
    active: bool
    last_active: datetime.datetime

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'MastersConnectorComponent '
                'getMaster, and getMasters '
                'no longer return Master as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


@deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), MasterModel)
class MasterDict(dict):
    pass


class MastersConnectorComponent(base.DBConnectorComponent):
    data2db = {"masterid": "id", "link": "id"}

    def findMasterId(self, name: str) -> defer.Deferred[int]:
        tbl = self.db.model.masters
        name_hash = hash_columns(name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name_hash == name_hash),
            insert_values={
                "name": name,
                "name_hash": name_hash,
                "active": 0,  # initially inactive
                "last_active": int(self.master.reactor.seconds()),
            },
        )

    def setMasterState(self, masterid: int, active: bool) -> defer.Deferred[bool]:
        def thd(conn) -> bool:
            tbl = self.db.model.masters
            whereclause = tbl.c.id == masterid

            # get the old state
            r = conn.execute(sa.select(tbl.c.active).where(whereclause))
            rows = r.fetchall()
            r.close()
            if not rows:
                return False  # can't change a row that doesn't exist..
            was_active = bool(rows[0].active)

            if not active:
                # if we're marking inactive, then delete any links to this
                # master
                sch_mst_tbl = self.db.model.scheduler_masters
                q = sch_mst_tbl.delete().where(sch_mst_tbl.c.masterid == masterid)
                conn.execute(q)
                conn.commit()

            # set the state (unconditionally, just to be safe)
            q = tbl.update().where(whereclause)
            q = q.values(active=1 if active else 0)
            if active:
                q = q.values(last_active=int(self.master.reactor.seconds()))
            conn.execute(q)
            conn.commit()

            # return True if there was a change in state
            return was_active != bool(active)

        return self.db.pool.do(thd)

    def getMaster(self, masterid: int) -> defer.Deferred[MasterModel | None]:
        def thd(conn) -> MasterModel | None:
            tbl = self.db.model.masters
            res = conn.execute(tbl.select().where(tbl.c.id == masterid))
            row = res.fetchone()

            rv = None
            if row:
                rv = self._model_from_row(row)
            res.close()
            return rv

        return self.db.pool.do(thd)

    def getMasters(self) -> defer.Deferred[list[MasterModel]]:
        def thd(conn) -> list[MasterModel]:
            tbl = self.db.model.masters
            return [self._model_from_row(row) for row in conn.execute(tbl.select()).fetchall()]

        return self.db.pool.do(thd)

    def setAllMastersActiveLongTimeAgo(self) -> defer.Deferred[None]:
        def thd(conn) -> None:
            tbl = self.db.model.masters
            q = tbl.update().values(active=1, last_active=0)
            conn.execute(q)

        return self.db.pool.do(thd)

    def _model_from_row(self, row):
        return MasterModel(
            id=row.id,
            name=row.name,
            active=bool(row.active),
            last_active=epoch2datetime(row.last_active),
        )
