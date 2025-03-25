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

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.internet import defer

from buildbot.db import NULL
from buildbot.db import base
from buildbot.util import epoch2datetime
from buildbot.util.twisted import async_to_deferred
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    import datetime
    from typing import Sequence

    from buildbot.data.resultspec import ResultSpec
    from buildbot.db.sourcestamps import SourceStampModel


@dataclass
class BuildModel:
    id: int
    number: int
    builderid: int
    buildrequestid: int
    workerid: int | None
    masterid: int
    started_at: datetime.datetime
    complete_at: datetime.datetime | None
    locks_duration_s: int | None
    state_string: str
    results: int | None

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'BuildsConnectorComponent getBuild, '
                'getBuildByNumber, getPrevSuccessfulBuild, '
                'getBuildsForChange, getBuilds, '
                '_getRecentBuilds, and _getBuild '
                'no longer return Build as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


class BuildsConnectorComponent(base.DBConnectorComponent):
    def _getBuild(self, whereclause) -> defer.Deferred[BuildModel | None]:
        def thd(conn) -> BuildModel | None:
            q = self.db.model.builds.select()
            if whereclause is not None:
                q = q.where(whereclause)
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._model_from_row(row)
            res.close()
            return rv

        return self.db.pool.do(thd)

    def getBuild(self, buildid: int) -> defer.Deferred[BuildModel | None]:
        return self._getBuild(self.db.model.builds.c.id == buildid)

    def getBuildByNumber(self, builderid: int, number: int) -> defer.Deferred[BuildModel | None]:
        return self._getBuild(
            (self.db.model.builds.c.builderid == builderid)
            & (self.db.model.builds.c.number == number)
        )

    def _getRecentBuilds(self, whereclause, offset=0, limit=1) -> defer.Deferred[list[BuildModel]]:
        def thd(conn) -> list[BuildModel]:
            tbl = self.db.model.builds

            q = tbl.select()
            if whereclause is not None:
                q = q.where(
                    whereclause,
                )

            q = (
                q.order_by(
                    sa.desc(tbl.c.complete_at),
                )
                .offset(offset)
                .limit(limit)
            )

            res = conn.execute(q)
            return list(self._model_from_row(row) for row in res.fetchall())

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getPrevSuccessfulBuild(
        self, builderid: int, number: int, ssBuild: Sequence[SourceStampModel]
    ):
        gssfb = self.master.db.sourcestamps.getSourceStampsForBuild
        rv = None
        tbl = self.db.model.builds
        offset = 0
        increment = 1000
        matchssBuild = {(ss.repository, ss.branch, ss.codebase) for ss in ssBuild}
        while rv is None:
            # Get some recent successful builds on the same builder
            prevBuilds = yield self._getRecentBuilds(
                whereclause=(
                    (tbl.c.builderid == builderid) & (tbl.c.number < number) & (tbl.c.results == 0)
                ),
                offset=offset,
                limit=increment,
            )
            if not prevBuilds:
                break
            for prevBuild in prevBuilds:
                prevssBuild = {
                    (ss.repository, ss.branch, ss.codebase) for ss in (yield gssfb(prevBuild.id))
                }
                if prevssBuild == matchssBuild:
                    # A successful build with the same
                    # repository/branch/codebase was found !
                    rv = prevBuild
                    break
            offset += increment

        return rv

    def getBuildsForChange(self, changeid: int) -> defer.Deferred[list[BuildModel]]:
        assert changeid > 0

        def thd(conn) -> list[BuildModel]:
            # Get builds for the change
            changes_tbl = self.db.model.changes
            bsets_tbl = self.db.model.buildsets
            bsss_tbl = self.db.model.buildset_sourcestamps
            reqs_tbl = self.db.model.buildrequests
            builds_tbl = self.db.model.builds

            from_clause = changes_tbl.join(
                bsss_tbl, changes_tbl.c.sourcestampid == bsss_tbl.c.sourcestampid
            )
            from_clause = from_clause.join(bsets_tbl, bsss_tbl.c.buildsetid == bsets_tbl.c.id)
            from_clause = from_clause.join(reqs_tbl, bsets_tbl.c.id == reqs_tbl.c.buildsetid)
            from_clause = from_clause.join(builds_tbl, reqs_tbl.c.id == builds_tbl.c.buildrequestid)

            q = (
                sa.select(builds_tbl)
                .select_from(from_clause)
                .where(changes_tbl.c.changeid == changeid)
            )
            res = conn.execute(q)
            return [self._model_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    def getBuilds(
        self,
        builderid: int | None = None,
        buildrequestid: int | None = None,
        workerid: int | None = None,
        complete: bool | None = None,
        resultSpec: ResultSpec | None = None,
    ) -> defer.Deferred[list[BuildModel]]:
        def thd(conn) -> list[BuildModel]:
            tbl = self.db.model.builds
            q = tbl.select()
            if builderid is not None:
                q = q.where(tbl.c.builderid == builderid)
            if buildrequestid is not None:
                q = q.where(tbl.c.buildrequestid == buildrequestid)
            if workerid is not None:
                q = q.where(tbl.c.workerid == workerid)
            if complete is not None:
                if complete:
                    q = q.where(tbl.c.complete_at != NULL)
                else:
                    q = q.where(tbl.c.complete_at == NULL)

            if resultSpec is not None:
                return resultSpec.thd_execute(conn, q, self._model_from_row)

            res = conn.execute(q)
            return [self._model_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    @async_to_deferred
    async def get_triggered_builds(self, buildid: int) -> list[BuildModel]:
        def thd(conn) -> list[BuildModel]:
            j = self.db.model.buildsets
            j = j.join(self.db.model.buildrequests)
            j = j.join(self.db.model.builds)

            q = (
                sa.select(self.db.model.builds)
                .select_from(j)
                .where(self.db.model.buildsets.c.parent_buildid == buildid)
            )

            res = conn.execute(q)
            return [self._model_from_row(row) for row in res.fetchall()]

        return await self.db.pool.do(thd)

    # returns a Deferred that returns a value
    def addBuild(
        self, builderid, buildrequestid, workerid, masterid, state_string, _race_hook=None
    ):
        started_at = int(self.master.reactor.seconds())

        def thd(conn):
            tbl = self.db.model.builds
            # get the highest current number
            r = conn.execute(
                sa.select(sa.func.max(tbl.c.number)).where(tbl.c.builderid == builderid)
            )
            number = r.scalar()
            new_number = 1 if number is None else number + 1
            # insert until we are successful..
            while True:
                if _race_hook:
                    _race_hook(conn)

                try:
                    r = conn.execute(
                        self.db.model.builds.insert(),
                        {
                            "number": new_number,
                            "builderid": builderid,
                            "buildrequestid": buildrequestid,
                            "workerid": workerid,
                            "masterid": masterid,
                            "started_at": started_at,
                            "complete_at": None,
                            "locks_duration_s": 0,
                            "state_string": state_string,
                        },
                    )
                    conn.commit()
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError) as e:
                    conn.rollback()
                    # pg 9.5 gives this error which makes it pass some build
                    # numbers
                    if 'duplicate key value violates unique constraint "builds_pkey"' not in str(e):
                        new_number += 1
                    continue
                return r.inserted_primary_key[0], new_number

        return self.db.pool.do(thd)

    # returns a Deferred that returns None
    def setBuildStateString(self, buildid, state_string):
        def thd(conn):
            tbl = self.db.model.builds

            q = tbl.update().where(tbl.c.id == buildid)
            conn.execute(q.values(state_string=state_string))

        return self.db.pool.do_with_transaction(thd)

    # returns a Deferred that returns None
    def finishBuild(self, buildid, results):
        def thd(conn):
            tbl = self.db.model.builds
            q = tbl.update().where(tbl.c.id == buildid)
            conn.execute(q.values(complete_at=int(self.master.reactor.seconds()), results=results))

        return self.db.pool.do_with_transaction(thd)

    # returns a Deferred that returns a value
    def getBuildProperties(self, bid, resultSpec=None):
        def thd(conn):
            bp_tbl = self.db.model.build_properties
            q = sa.select(
                bp_tbl.c.name,
                bp_tbl.c.value,
                bp_tbl.c.source,
            ).where(bp_tbl.c.buildid == bid)
            props = []
            if resultSpec is not None:
                data = resultSpec.thd_execute(conn, q, lambda x: x)
            else:
                data = conn.execute(q)
            for row in data:
                prop = (json.loads(row.value), row.source)
                props.append((row.name, prop))
            return dict(props)

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def setBuildProperty(self, bid, name, value, source):
        """A kind of create_or_update, that's between one or two queries per
        call"""

        def thd(conn):
            bp_tbl = self.db.model.build_properties
            self.checkLength(bp_tbl.c.name, name)
            self.checkLength(bp_tbl.c.source, source)
            whereclause = sa.and_(bp_tbl.c.buildid == bid, bp_tbl.c.name == name)
            q = sa.select(bp_tbl.c.value, bp_tbl.c.source).where(whereclause)
            prop = conn.execute(q).fetchone()
            value_js = json.dumps(value)
            if prop is None:
                conn.execute(
                    bp_tbl.insert(),
                    {"buildid": bid, "name": name, "value": value_js, "source": source},
                )
            elif (prop.value != value_js) or (prop.source != source):
                conn.execute(
                    bp_tbl.update().where(whereclause), {"value": value_js, "source": source}
                )

        yield self.db.pool.do_with_transaction(thd)

    @defer.inlineCallbacks
    def add_build_locks_duration(self, buildid, duration_s):
        def thd(conn):
            builds_tbl = self.db.model.builds
            conn.execute(
                builds_tbl.update()
                .where(builds_tbl.c.id == buildid)
                .values(locks_duration_s=builds_tbl.c.locks_duration_s + duration_s)
            )

        yield self.db.pool.do_with_transaction(thd)

    def _model_from_row(self, row):
        return BuildModel(
            id=row.id,
            number=row.number,
            builderid=row.builderid,
            buildrequestid=row.buildrequestid,
            workerid=row.workerid,
            masterid=row.masterid,
            started_at=epoch2datetime(row.started_at),
            complete_at=epoch2datetime(row.complete_at),
            locks_duration_s=row.locks_duration_s,
            state_string=row.state_string,
            results=row.results,
        )
