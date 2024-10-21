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
"""
Support for buildsets in the database
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.internet import defer

from buildbot.db import NULL
from buildbot.db import base
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    import datetime


class BsProps(dict):
    pass


class AlreadyCompleteError(RuntimeError):
    pass


@dataclass
class BuildSetModel:
    bsid: int
    external_idstring: str | None
    reason: str | None
    submitted_at: datetime.datetime
    complete: bool = False
    complete_at: datetime.datetime | None = None
    results: int | None = None
    parent_buildid: int | None = None
    parent_relationship: str | None = None
    rebuilt_buildid: int | None = None

    sourcestamps: list[int] = field(default_factory=list)

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'BuildsetsConnectorComponent '
                'getBuildset, getBuildsets, and getRecentBuildsets '
                'no longer return BuildSet as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


class BuildsetsConnectorComponent(base.DBConnectorComponent):
    @defer.inlineCallbacks
    def addBuildset(
        self,
        sourcestamps,
        reason,
        properties,
        builderids,
        waited_for,
        external_idstring=None,
        submitted_at=None,
        rebuilt_buildid=None,
        parent_buildid=None,
        parent_relationship=None,
        priority=0,
    ):
        # We've gotten this wrong a couple times.
        assert isinstance(waited_for, bool), f'waited_for should be boolean: {waited_for!r}'

        if submitted_at is not None:
            submitted_at = datetime2epoch(submitted_at)
        else:
            submitted_at = int(self.master.reactor.seconds())

        # convert to sourcestamp IDs first, as necessary
        def toSsid(sourcestamp):
            if isinstance(sourcestamp, int):
                return defer.succeed(sourcestamp)
            ssConnector = self.master.db.sourcestamps
            return ssConnector.findSourceStampId(**sourcestamp)

        sourcestamps = yield defer.DeferredList(
            [toSsid(ss) for ss in sourcestamps], fireOnOneErrback=True, consumeErrors=True
        )
        sourcestampids = [r[1] for r in sourcestamps]

        def thd(conn):
            buildsets_tbl = self.db.model.buildsets

            self.checkLength(buildsets_tbl.c.reason, reason)
            self.checkLength(buildsets_tbl.c.external_idstring, external_idstring)

            transaction = conn.begin()

            # insert the buildset itself
            r = conn.execute(
                buildsets_tbl.insert(),
                {
                    "submitted_at": submitted_at,
                    "reason": reason,
                    "rebuilt_buildid": rebuilt_buildid,
                    "complete": 0,
                    "complete_at": None,
                    "results": -1,
                    "external_idstring": external_idstring,
                    "parent_buildid": parent_buildid,
                    "parent_relationship": parent_relationship,
                },
            )
            bsid = r.inserted_primary_key[0]

            # add any properties
            if properties:
                bs_props_tbl = self.db.model.buildset_properties

                inserts = [
                    {"buildsetid": bsid, "property_name": k, "property_value": json.dumps([v, s])}
                    for k, (v, s) in properties.items()
                ]
                for i in inserts:
                    self.checkLength(bs_props_tbl.c.property_name, i['property_name'])

                conn.execute(bs_props_tbl.insert(), inserts)

            # add sourcestamp ids
            r = conn.execute(
                self.db.model.buildset_sourcestamps.insert(),
                [{"buildsetid": bsid, "sourcestampid": ssid} for ssid in sourcestampids],
            )

            # and finish with a build request for each builder.  Note that
            # sqlalchemy and the Python DBAPI do not provide a way to recover
            # inserted IDs from a multi-row insert, so this is done one row at
            # a time.
            brids = {}
            br_tbl = self.db.model.buildrequests
            ins = br_tbl.insert()
            for builderid in builderids:
                r = conn.execute(
                    ins,
                    {
                        "buildsetid": bsid,
                        "builderid": builderid,
                        "priority": priority,
                        "claimed_at": 0,
                        "claimed_by_name": None,
                        "claimed_by_incarnation": None,
                        "complete": 0,
                        "results": -1,
                        "submitted_at": submitted_at,
                        "complete_at": None,
                        "waited_for": 1 if waited_for else 0,
                    },
                )

                brids[builderid] = r.inserted_primary_key[0]

            transaction.commit()

            return (bsid, brids)

        bsid, brids = yield self.db.pool.do(thd)

        # Seed the buildset property cache.
        self.getBuildsetProperties.cache.put(bsid, BsProps(properties))

        return (bsid, brids)

    @defer.inlineCallbacks
    def completeBuildset(self, bsid, results, complete_at=None):
        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = int(self.master.reactor.seconds())

        def thd(conn):
            tbl = self.db.model.buildsets

            q = tbl.update().where(
                (tbl.c.id == bsid) & ((tbl.c.complete == NULL) | (tbl.c.complete != 1))
            )
            res = conn.execute(q.values(complete=1, results=results, complete_at=complete_at))
            conn.commit()

            if res.rowcount != 1:
                # happens when two buildrequests finish at the same time
                raise AlreadyCompleteError()

        yield self.db.pool.do(thd)

    def getBuildset(self, bsid) -> defer.Deferred[BuildSetModel | None]:
        def thd(conn) -> BuildSetModel | None:
            bs_tbl = self.db.model.buildsets
            q = bs_tbl.select().where(bs_tbl.c.id == bsid)
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            return self._thd_model_from_row(conn, row)

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getBuildsets(self, complete=None, resultSpec=None):
        def thd(conn) -> list[BuildSetModel]:
            bs_tbl = self.db.model.buildsets
            q = bs_tbl.select()
            if complete is not None:
                if complete:
                    q = q.where(bs_tbl.c.complete != 0)
                else:
                    q = q.where((bs_tbl.c.complete == 0) | (bs_tbl.c.complete == NULL))
            if resultSpec is not None:
                return resultSpec.thd_execute(conn, q, lambda x: self._thd_model_from_row(conn, x))
            res = conn.execute(q)
            return [self._thd_model_from_row(conn, row) for row in res.fetchall()]

        res = yield self.db.pool.do(thd)
        return res

    def getRecentBuildsets(
        self,
        count: int | None = None,
        branch: str | None = None,
        repository: str | None = None,
        complete: bool | None = None,
    ) -> defer.Deferred[list[BuildSetModel]]:
        def thd(conn) -> list[BuildSetModel]:
            bs_tbl = self.db.model.buildsets
            ss_tbl = self.db.model.sourcestamps
            j = self.db.model.buildsets
            j = j.join(self.db.model.buildset_sourcestamps)
            j = j.join(self.db.model.sourcestamps)
            q = sa.select(bs_tbl).select_from(j).distinct()
            q = q.order_by(sa.desc(bs_tbl.c.submitted_at))
            q = q.limit(count)

            if complete is not None:
                if complete:
                    q = q.where(bs_tbl.c.complete != 0)
                else:
                    q = q.where((bs_tbl.c.complete == 0) | (bs_tbl.c.complete == NULL))
            if branch:
                q = q.where(ss_tbl.c.branch == branch)
            if repository:
                q = q.where(ss_tbl.c.repository == repository)
            res = conn.execute(q)
            return list(reversed([self._thd_model_from_row(conn, row) for row in res.fetchall()]))

        return self.db.pool.do(thd)

    @base.cached("BuildsetProperties")
    def getBuildsetProperties(self, bsid) -> defer.Deferred[BsProps]:
        def thd(conn) -> BsProps:
            bsp_tbl = self.db.model.buildset_properties
            q = sa.select(
                bsp_tbl.c.property_name,
                bsp_tbl.c.property_value,
            ).where(bsp_tbl.c.buildsetid == bsid)
            ret = []
            for row in conn.execute(q):
                try:
                    properties = json.loads(row.property_value)
                    ret.append((row.property_name, tuple(properties)))
                except ValueError:
                    pass
            return BsProps(ret)

        return self.db.pool.do(thd)

    def _thd_model_from_row(self, conn, row):
        # get sourcestamps
        tbl = self.db.model.buildset_sourcestamps
        sourcestamps = [
            r.sourcestampid
            for r in conn.execute(
                sa.select(tbl.c.sourcestampid).where(tbl.c.buildsetid == row.id)
            ).fetchall()
        ]

        return BuildSetModel(
            bsid=row.id,
            external_idstring=row.external_idstring,
            reason=row.reason,
            submitted_at=epoch2datetime(row.submitted_at),
            complete=bool(row.complete),
            complete_at=epoch2datetime(row.complete_at),
            results=row.results,
            parent_buildid=row.parent_buildid,
            parent_relationship=row.parent_relationship,
            rebuilt_buildid=row.rebuilt_buildid,
            sourcestamps=sourcestamps,
        )
