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
from dataclasses import field
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.internet import defer

from buildbot.db import base
from buildbot.util import identifiers
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    from typing import Any


@dataclass
class BuilderMasterModel:
    builderid: int
    masterid: int

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'WorkersConnectorComponent '
                'getWorker, and getWorkers '
                'no longer return Worker as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


@dataclass
class WorkerModel:
    id: int
    name: str
    workerinfo: dict[str, Any]
    paused: bool = False
    pause_reason: str | None = None
    graceful: bool = False

    configured_on: list[BuilderMasterModel] = field(default_factory=list)
    connected_to: list[int] = field(default_factory=list)

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'WorkersConnectorComponent '
                'getWorker, and getWorkers '
                'no longer return Worker as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


class WorkersConnectorComponent(base.DBConnectorComponent):
    def findWorkerId(self, name):
        tbl = self.db.model.workers
        # callers should verify this and give good user error messages
        assert identifiers.isIdentifier(50, name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name == name),
            insert_values={
                "name": name,
                "info": {},
                "paused": 0,
                "pause_reason": None,
                "graceful": 0,
            },
        )

    def _deleteFromConfiguredWorkers_thd(self, conn, buildermasterids, workerid=None):
        cfg_tbl = self.db.model.configured_workers
        # batch deletes to avoid using too many variables
        for batch in self.doBatch(buildermasterids, 100):
            q = cfg_tbl.delete()
            q = q.where(cfg_tbl.c.buildermasterid.in_(batch))
            if workerid:
                q = q.where(cfg_tbl.c.workerid == workerid)
            conn.execute(q).close()

    # returns a Deferred which returns None
    def deconfigureAllWorkersForMaster(self, masterid):
        def thd(conn):
            # first remove the old configured buildermasterids for this master and worker
            # as sqlalchemy does not support delete with join, we need to do
            # that in 2 queries
            cfg_tbl = self.db.model.configured_workers
            bm_tbl = self.db.model.builder_masters
            j = cfg_tbl
            j = j.outerjoin(bm_tbl)
            q = sa.select(cfg_tbl.c.buildermasterid).select_from(j).distinct()
            q = q.where(bm_tbl.c.masterid == masterid)
            res = conn.execute(q)
            buildermasterids = [row.buildermasterid for row in res]
            res.close()
            self._deleteFromConfiguredWorkers_thd(conn, buildermasterids)

        return self.db.pool.do_with_transaction(thd)

    # returns a Deferred that returns None
    def workerConfigured(self, workerid, masterid, builderids):
        def thd(conn):
            cfg_tbl = self.db.model.configured_workers
            bm_tbl = self.db.model.builder_masters

            # get the buildermasterids that are configured
            if builderids:
                q = sa.select(bm_tbl.c.id).select_from(bm_tbl)
                q = q.where(bm_tbl.c.masterid == masterid)
                q = q.where(bm_tbl.c.builderid.in_(builderids))
                res = conn.execute(q)
                buildermasterids = {row.id for row in res}
                res.close()
            else:
                buildermasterids = set([])

            j = cfg_tbl
            j = j.outerjoin(bm_tbl)
            q = sa.select(cfg_tbl.c.buildermasterid).select_from(j).distinct()
            q = q.where(bm_tbl.c.masterid == masterid)
            q = q.where(cfg_tbl.c.workerid == workerid)
            res = conn.execute(q)
            oldbuildermasterids = {row.buildermasterid for row in res}
            res.close()

            todeletebuildermasterids = oldbuildermasterids - buildermasterids
            toinsertbuildermasterids = buildermasterids - oldbuildermasterids
            self._deleteFromConfiguredWorkers_thd(conn, todeletebuildermasterids, workerid)

            # and insert the new ones
            if toinsertbuildermasterids:
                q = cfg_tbl.insert()
                conn.execute(
                    q,
                    [
                        {'workerid': workerid, 'buildermasterid': buildermasterid}
                        for buildermasterid in toinsertbuildermasterids
                    ],
                ).close()

        return self.db.pool.do_with_transaction(thd)

    @defer.inlineCallbacks
    def getWorker(
        self,
        workerid: int | None = None,
        name: str | None = None,
        masterid: int | None = None,
        builderid: int | None = None,
    ):
        if workerid is None and name is None:
            return None
        workers = yield self.getWorkers(
            _workerid=workerid, _name=name, masterid=masterid, builderid=builderid
        )
        if workers:
            return workers[0]
        return None

    def getWorkers(
        self,
        _workerid: int | None = None,
        _name: str | None = None,
        masterid: int | None = None,
        builderid: int | None = None,
        paused: bool | None = None,
        graceful: bool | None = None,
    ) -> defer.Deferred[list[WorkerModel]]:
        def thd(conn) -> list[WorkerModel]:
            workers_tbl = self.db.model.workers
            conn_tbl = self.db.model.connected_workers
            cfg_tbl = self.db.model.configured_workers
            bm_tbl = self.db.model.builder_masters

            # first, get the worker itself and the configured_on info
            j = workers_tbl
            j = j.outerjoin(cfg_tbl)
            j = j.outerjoin(bm_tbl)
            q = (
                sa.select(
                    workers_tbl.c.id,
                    workers_tbl.c.name,
                    workers_tbl.c.info,
                    workers_tbl.c.paused,
                    workers_tbl.c.pause_reason,
                    workers_tbl.c.graceful,
                    bm_tbl.c.builderid,
                    bm_tbl.c.masterid,
                )
                .select_from(j)
                .order_by(
                    workers_tbl.c.id,
                )
            )

            if _workerid is not None:
                q = q.where(workers_tbl.c.id == _workerid)
            if _name is not None:
                q = q.where(workers_tbl.c.name == _name)
            if masterid is not None:
                q = q.where(bm_tbl.c.masterid == masterid)
            if builderid is not None:
                q = q.where(bm_tbl.c.builderid == builderid)
            if paused is not None:
                q = q.where(workers_tbl.c.paused == int(paused))
            if graceful is not None:
                q = q.where(workers_tbl.c.graceful == int(graceful))

            rv: dict[int, WorkerModel] = {}
            res = None
            lastId = None
            for row in conn.execute(q):
                if row.id != lastId:
                    lastId = row.id
                    res = self._model_from_row(row)
                    rv[lastId] = res
                if row.builderid and row.masterid:
                    rv[lastId].configured_on.append(
                        BuilderMasterModel(builderid=row.builderid, masterid=row.masterid)
                    )

            # now go back and get the connection info for the same set of
            # workers
            j = conn_tbl
            if _name is not None:
                # note this is not an outer join; if there are unconnected
                # workers, they were captured in rv above
                j = j.join(workers_tbl)
            q = (
                sa.select(
                    conn_tbl.c.workerid,
                    conn_tbl.c.masterid,
                )
                .select_from(j)
                .order_by(conn_tbl.c.workerid)
                .where(conn_tbl.c.workerid.in_(rv.keys()))
            )

            if _name is not None:
                q = q.where(workers_tbl.c.name == _name)
            if masterid is not None:
                q = q.where(conn_tbl.c.masterid == masterid)

            for row in conn.execute(q):
                if row.workerid not in rv:
                    continue
                rv[row.workerid].connected_to.append(row.masterid)

            return list(rv.values())

        return self.db.pool.do(thd)

    # returns a Deferred that returns None
    def workerConnected(self, workerid, masterid, workerinfo):
        def thd(conn):
            conn_tbl = self.db.model.connected_workers
            q = conn_tbl.insert()
            try:
                conn.execute(q, {'workerid': workerid, 'masterid': masterid})
                conn.commit()
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                # if the row is already present, silently fail..
                conn.rollback()

            bs_tbl = self.db.model.workers
            q = bs_tbl.update().where(bs_tbl.c.id == workerid)
            conn.execute(q.values(info=workerinfo))
            conn.commit()

        return self.db.pool.do(thd)

    # returns a Deferred that returns None
    def workerDisconnected(self, workerid, masterid):
        def thd(conn):
            tbl = self.db.model.connected_workers
            q = tbl.delete().where(tbl.c.workerid == workerid, tbl.c.masterid == masterid)
            conn.execute(q)

        return self.db.pool.do_with_transaction(thd)

    # returns a Deferred that returns None
    def set_worker_paused(self, workerid, paused, pause_reason=None):
        def thd(conn):
            tbl = self.db.model.workers
            q = tbl.update().where(tbl.c.id == workerid)
            conn.execute(q.values(paused=int(paused), pause_reason=pause_reason))

        return self.db.pool.do_with_transaction(thd)

    # returns a Deferred that returns None
    def set_worker_graceful(self, workerid, graceful):
        def thd(conn):
            tbl = self.db.model.workers
            q = tbl.update().where(tbl.c.id == workerid)
            conn.execute(q.values(graceful=int(graceful)))

        return self.db.pool.do_with_transaction(thd)

    def _model_from_row(self, row):
        return WorkerModel(
            id=row.id,
            name=row.name,
            workerinfo=row.info,
            paused=bool(row.paused),
            pause_reason=row.pause_reason,
            graceful=bool(row.graceful),
        )
