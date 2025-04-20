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
    from typing import Literal


class SchedulerAlreadyClaimedError(Exception):
    pass


@dataclass
class SchedulerModel:
    id: int
    name: str
    enabled: bool = True

    masterid: int | None = None

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'SchedulersConnectorComponent '
                'getScheduler, and getSchedulers '
                'no longer return Scheduler as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


class SchedulersConnectorComponent(base.DBConnectorComponent):
    def enable(self, schedulerid: int, v: bool) -> defer.Deferred[None]:
        def thd(conn) -> None:
            tbl = self.db.model.schedulers
            q = tbl.update().where(tbl.c.id == schedulerid)
            conn.execute(q.values(enabled=int(v)))

        return self.db.pool.do_with_transaction(thd)

    def classifyChanges(
        self, schedulerid: int, classifications: dict[int, bool]
    ) -> defer.Deferred[None]:
        def thd(conn) -> None:
            tbl = self.db.model.scheduler_changes
            for changeid, important in classifications.items():
                # convert the 'important' value into an integer, since that
                # is the column type
                imp_int = int(bool(important))

                self.db.upsert(
                    conn,
                    tbl,
                    where_values=(
                        (tbl.c.schedulerid, schedulerid),
                        (tbl.c.changeid, changeid),
                    ),
                    update_values=((tbl.c.important, imp_int),),
                    _race_hook=None,
                )
                conn.commit()

        return self.db.pool.do(thd)

    def flushChangeClassifications(
        self, schedulerid: int, less_than: int | None = None
    ) -> defer.Deferred[None]:
        def thd(conn) -> None:
            sch_ch_tbl = self.db.model.scheduler_changes
            wc = sch_ch_tbl.c.schedulerid == schedulerid
            if less_than is not None:
                wc = wc & (sch_ch_tbl.c.changeid < less_than)
            q = sch_ch_tbl.delete().where(wc)
            conn.execute(q).close()

        return self.db.pool.do_with_transaction(thd)

    def getChangeClassifications(
        self,
        schedulerid: int,
        branch: str | None | Literal[-1] = -1,
        repository: str | None | Literal[-1] = -1,
        project: str | None | Literal[-1] = -1,
        codebase: str | None | Literal[-1] = -1,
    ) -> defer.Deferred[dict[int, bool]]:
        # -1 here stands for "argument not given", since None has meaning
        # as a branch
        def thd(conn) -> dict[int, bool]:
            sch_ch_tbl = self.db.model.scheduler_changes
            ch_tbl = self.db.model.changes

            wc = sch_ch_tbl.c.schedulerid == schedulerid

            # may need to filter further based on branch, etc
            extra_wheres = []
            if branch != -1:
                extra_wheres.append(ch_tbl.c.branch == branch)
            if repository != -1:
                extra_wheres.append(ch_tbl.c.repository == repository)
            if project != -1:
                extra_wheres.append(ch_tbl.c.project == project)
            if codebase != -1:
                extra_wheres.append(ch_tbl.c.codebase == codebase)

            # if we need to filter further append those, as well as a join
            # on changeid (but just once for that one)
            if extra_wheres:
                wc &= sch_ch_tbl.c.changeid == ch_tbl.c.changeid
                for w in extra_wheres:
                    wc &= w

            q = sa.select(sch_ch_tbl.c.changeid, sch_ch_tbl.c.important).where(wc)
            return {r.changeid: bool(r.important) for r in conn.execute(q)}

        return self.db.pool.do(thd)

    def findSchedulerId(self, name: str) -> defer.Deferred[int]:
        tbl = self.db.model.schedulers
        name_hash = hash_columns(name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name_hash == name_hash),
            insert_values={"name": name, "name_hash": name_hash},
        )

    def setSchedulerMaster(self, schedulerid: int, masterid: int | None) -> defer.Deferred[None]:
        def thd(conn) -> None:
            sch_mst_tbl = self.db.model.scheduler_masters

            # handle the masterid=None case to get it out of the way
            if masterid is None:
                q = sch_mst_tbl.delete().where(sch_mst_tbl.c.schedulerid == schedulerid)
                conn.execute(q).close()
                conn.commit()
                return None

            # try a blind insert..
            try:
                q = sch_mst_tbl.insert()
                conn.execute(q, {"schedulerid": schedulerid, "masterid": masterid}).close()
                conn.commit()
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError) as e:
                conn.rollback()
                # someone already owns this scheduler, but who?
                join = self.db.model.masters.outerjoin(
                    sch_mst_tbl, (self.db.model.masters.c.id == sch_mst_tbl.c.masterid)
                )

                q = (
                    sa.select(
                        self.db.model.masters.c.name,
                        sch_mst_tbl.c.masterid,
                    )
                    .select_from(join)
                    .where(sch_mst_tbl.c.schedulerid == schedulerid)
                )
                row = conn.execute(q).fetchone()
                # ok, that was us, so we just do nothing
                if row.masterid == masterid:
                    return None
                raise SchedulerAlreadyClaimedError(f"already claimed by {row.name}") from e
            return None

        return self.db.pool.do(thd)

    def get_scheduler_master(self, schedulerid):
        def thd(conn):
            q = sa.select(self.db.model.scheduler_masters.c.masterid).where(
                self.db.model.scheduler_masters.c.schedulerid == schedulerid
            )
            r = conn.execute(q)
            row = r.fetchone()
            conn.close()
            if row:
                return row.masterid
            return None

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getScheduler(self, schedulerid: int):
        sch = yield self.getSchedulers(_schedulerid=schedulerid)
        if sch:
            return sch[0]
        return None

    def getSchedulers(
        self,
        active: bool | None = None,
        masterid: int | None = None,
        _schedulerid: int | None = None,
    ) -> defer.Deferred[list[SchedulerModel]]:
        def thd(conn) -> list[SchedulerModel]:
            sch_tbl = self.db.model.schedulers
            sch_mst_tbl = self.db.model.scheduler_masters

            # handle the trivial case of masterid=xx and active=False
            if masterid is not None and active is not None and not active:
                return []

            join = sch_tbl.outerjoin(sch_mst_tbl, (sch_tbl.c.id == sch_mst_tbl.c.schedulerid))

            # if we're given a _schedulerid, select only that row
            wc = None
            if _schedulerid:
                wc = sch_tbl.c.id == _schedulerid
            else:
                # otherwise, filter with active, if necessary
                if masterid is not None:
                    wc = sch_mst_tbl.c.masterid == masterid
                elif active:
                    wc = sch_mst_tbl.c.masterid != NULL
                elif active is not None:
                    wc = sch_mst_tbl.c.masterid == NULL

            q = sa.select(
                sch_tbl.c.id,
                sch_tbl.c.name,
                sch_tbl.c.enabled,
                sch_mst_tbl.c.masterid,
            ).select_from(join)
            if wc is not None:
                q = q.where(wc)

            return [self._model_from_row(row) for row in conn.execute(q).fetchall()]

        return self.db.pool.do(thd)

    def _model_from_row(self, row):
        return SchedulerModel(
            id=row.id,
            name=row.name,
            enabled=bool(row.enabled),
            masterid=row.masterid,
        )
