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

import sqlalchemy as sa
from twisted.internet import defer

from buildbot.db import NULL
from buildbot.db import base
from buildbot.util.sautils import hash_columns
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class ChangeSourceAlreadyClaimedError(Exception):
    pass


@dataclass
class ChangeSourceModel:
    id: int
    name: str

    masterid: int | None = None

    # For backward compatibility
    def __getitem__(self, key: str) -> object:
        warn_deprecated(
            '4.1.0',
            (
                'ChangeSourcesConnectorComponent '
                'getChangeSource, and getChangeSources '
                'no longer return ChangeSource as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


class ChangeSourcesConnectorComponent(base.DBConnectorComponent):
    def findChangeSourceId(self, name: str) -> defer.Deferred[int]:
        tbl = self.db.model.changesources
        name_hash = hash_columns(name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name_hash == name_hash),
            insert_values={"name": name, "name_hash": name_hash},
        )

    # returns a Deferred that returns None
    def setChangeSourceMaster(
        self, changesourceid: int, masterid: int | None
    ) -> defer.Deferred[None]:
        def thd(conn: sa.engine.Connection) -> None:
            cs_mst_tbl = self.db.model.changesource_masters

            # handle the masterid=None case to get it out of the way
            if masterid is None:
                q = cs_mst_tbl.delete().where(cs_mst_tbl.c.changesourceid == changesourceid)
                conn.execute(q)
                conn.commit()
                return

            # try a blind insert..
            try:
                q_insert = cs_mst_tbl.insert()
                conn.execute(q_insert, {"changesourceid": changesourceid, "masterid": masterid})
                conn.commit()
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError) as e:
                conn.rollback()
                # someone already owns this changesource.
                raise ChangeSourceAlreadyClaimedError from e

        return self.db.pool.do(thd)

    def get_change_source_master(self, changesourceid: int) -> defer.Deferred[int | None]:
        def thd(conn: sa.engine.Connection) -> int | None:
            q = sa.select(self.db.model.changesource_masters.c.masterid).where(
                self.db.model.changesource_masters.c.changesourceid == changesourceid
            )
            r = conn.execute(q)
            row = r.fetchone()
            conn.close()
            if row:
                return row.masterid
            return None

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getChangeSource(self, changesourceid: int) -> InlineCallbacksType[ChangeSourceModel | None]:
        cs = yield self.getChangeSources(_changesourceid=changesourceid)
        if cs:
            return cs[0]
        return None

    # returns a Deferred that returns a value
    def getChangeSources(
        self,
        active: bool | None = None,
        masterid: int | None = None,
        _changesourceid: int | None = None,
    ) -> defer.Deferred[list[ChangeSourceModel]]:
        def thd(conn: sa.engine.Connection) -> list[ChangeSourceModel]:
            cs_tbl = self.db.model.changesources
            cs_mst_tbl = self.db.model.changesource_masters

            # handle the trivial case of masterid=xx and active=False
            if masterid is not None and active is not None and not active:
                return []

            join = cs_tbl.outerjoin(cs_mst_tbl, (cs_tbl.c.id == cs_mst_tbl.c.changesourceid))

            # if we're given a _changesourceid, select only that row
            wc = None
            if _changesourceid:
                wc = cs_tbl.c.id == _changesourceid
            else:
                # otherwise, filter with active, if necessary
                if masterid is not None:
                    wc = cs_mst_tbl.c.masterid == masterid
                elif active:
                    wc = cs_mst_tbl.c.masterid != NULL
                elif active is not None:
                    wc = cs_mst_tbl.c.masterid == NULL

            q = sa.select(
                cs_tbl.c.id,
                cs_tbl.c.name,
                cs_mst_tbl.c.masterid,
            ).select_from(join)
            if wc is not None:
                q = q.where(wc)

            return [self._model_from_row(row) for row in conn.execute(q).fetchall()]

        return self.db.pool.do(thd)

    def _model_from_row(self, row: sa.engine.Row) -> ChangeSourceModel:
        return ChangeSourceModel(id=row.id, name=row.name, masterid=row.masterid)
