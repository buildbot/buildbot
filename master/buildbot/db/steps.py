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

from buildbot.db import base
from buildbot.util import epoch2datetime
from buildbot.util.twisted import async_to_deferred
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    import datetime


@dataclass
class UrlModel:
    name: str
    url: str

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'StepsConnectorComponent '
                'getStep, and getSteps '
                'no longer return Step as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


@dataclass
class StepModel:
    id: int
    number: int
    name: str
    buildid: int
    started_at: datetime.datetime | None
    locks_acquired_at: datetime.datetime | None
    complete_at: datetime.datetime | None
    state_string: str
    results: int | None
    urls: list[UrlModel]
    hidden: bool = False

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'StepsConnectorComponent '
                'getStep, and getSteps '
                'no longer return Step as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


class StepsConnectorComponent(base.DBConnectorComponent):
    url_lock: defer.DeferredLock | None = None

    @async_to_deferred
    async def getStep(
        self,
        stepid: int | None = None,
        buildid: int | None = None,
        number: int | None = None,
        name: str | None = None,
    ) -> StepModel | None:
        tbl = self.db.model.steps
        if stepid is not None:
            wc = tbl.c.id == stepid
        else:
            if buildid is None:
                raise RuntimeError('must supply either stepid or buildid')
            if number is not None:
                wc = tbl.c.number == number
            elif name is not None:
                wc = tbl.c.name == name
            else:
                raise RuntimeError('must supply either number or name')
            wc = wc & (tbl.c.buildid == buildid)

        def thd(conn) -> StepModel | None:
            q = self.db.model.steps.select().where(wc)
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._model_from_row(row)
            res.close()
            return rv

        return await self.db.pool.do(thd)

    def getSteps(self, buildid: int) -> defer.Deferred[list[StepModel]]:
        def thd(conn) -> list[StepModel]:
            tbl = self.db.model.steps
            q = tbl.select()
            q = q.where(tbl.c.buildid == buildid)
            q = q.order_by(tbl.c.number)
            res = conn.execute(q)
            return [self._model_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    def addStep(
        self, buildid: int, name: str, state_string: str
    ) -> defer.Deferred[tuple[int, int, str]]:
        def thd(conn) -> tuple[int, int, str]:
            tbl = self.db.model.steps
            # get the highest current number
            r = conn.execute(sa.select(sa.func.max(tbl.c.number)).where(tbl.c.buildid == buildid))
            number = r.scalar()
            number = 0 if number is None else number + 1

            # note that there is no chance for a race condition here,
            # since only one master is inserting steps.  If there is a
            # conflict, then the name is likely already taken.
            insert_row = {
                "buildid": buildid,
                "number": number,
                "started_at": None,
                "locks_acquired_at": None,
                "complete_at": None,
                "state_string": state_string,
                "urls_json": '[]',
                "name": name,
            }
            try:
                r = conn.execute(self.db.model.steps.insert(), insert_row)
                conn.commit()
                got_id = r.inserted_primary_key[0]
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                conn.rollback()
                got_id = None

            if got_id:
                return (got_id, number, name)

            # we didn't get an id, so calculate a unique name and use that
            # instead.  Because names are truncated at the right to fit in a
            # 50-character identifier, this isn't a simple query.
            res = conn.execute(sa.select(tbl.c.name).where(tbl.c.buildid == buildid))
            names = {row[0] for row in res}
            num = 1
            while True:
                numstr = f'_{num}'
                newname = name[: 50 - len(numstr)] + numstr
                if newname not in names:
                    break
                num += 1
            insert_row['name'] = newname
            r = conn.execute(self.db.model.steps.insert(), insert_row)
            conn.commit()
            got_id = r.inserted_primary_key[0]
            return (got_id, number, newname)

        return self.db.pool.do(thd)

    def startStep(self, stepid: int, started_at: int, locks_acquired: bool) -> defer.Deferred[None]:
        def thd(conn) -> None:
            tbl = self.db.model.steps
            q = tbl.update().where(tbl.c.id == stepid)
            if locks_acquired:
                conn.execute(q.values(started_at=started_at, locks_acquired_at=started_at))
            else:
                conn.execute(q.values(started_at=started_at))

        return self.db.pool.do_with_transaction(thd)

    def set_step_locks_acquired_at(
        self, stepid: int, locks_acquired_at: int
    ) -> defer.Deferred[None]:
        def thd(conn) -> None:
            tbl = self.db.model.steps
            q = tbl.update().where(tbl.c.id == stepid)
            conn.execute(q.values(locks_acquired_at=locks_acquired_at))

        return self.db.pool.do_with_transaction(thd)

    def setStepStateString(self, stepid: int, state_string: str) -> defer.Deferred[None]:
        def thd(conn) -> None:
            tbl = self.db.model.steps
            q = tbl.update().where(tbl.c.id == stepid)
            conn.execute(q.values(state_string=state_string))

        return self.db.pool.do_with_transaction(thd)

    def addURL(self, stepid: int, name: str, url: str, _racehook=None) -> defer.Deferred[None]:
        # This methods adds an URL to the db
        # This is a read modify write and thus there is a possibility
        # that several urls are added at the same time (e.g with a deferredlist
        # at the end of a step)
        # this race condition is only inside the same master, as only one master
        # is supposed to add urls to a buildstep.
        # so threading.lock is used, as we are in the thread pool
        if self.url_lock is None:
            # this runs in reactor thread, so no race here..
            self.url_lock = defer.DeferredLock()

        def thd(conn) -> None:
            tbl = self.db.model.steps
            wc = tbl.c.id == stepid
            q = sa.select(tbl.c.urls_json).where(wc)
            res = conn.execute(q)
            row = res.fetchone()
            if _racehook is not None:
                _racehook()
            urls = json.loads(row.urls_json)

            url_item = {"name": name, "url": url}

            if url_item not in urls:
                urls.append(url_item)
                q2 = tbl.update().where(wc)
                conn.execute(q2.values(urls_json=json.dumps(urls)))
                conn.commit()

        return self.url_lock.run(self.db.pool.do, thd)

    def finishStep(self, stepid: int, results: int, hidden: bool) -> defer.Deferred[None]:
        def thd(conn) -> None:
            tbl = self.db.model.steps
            q = tbl.update().where(tbl.c.id == stepid)
            conn.execute(
                q.values(
                    complete_at=int(self.master.reactor.seconds()),
                    results=results,
                    hidden=1 if hidden else 0,
                )
            )

        return self.db.pool.do_with_transaction(thd)

    def _model_from_row(self, row):
        return StepModel(
            id=row.id,
            number=row.number,
            name=row.name,
            buildid=row.buildid,
            started_at=epoch2datetime(row.started_at),
            locks_acquired_at=epoch2datetime(row.locks_acquired_at),
            complete_at=epoch2datetime(row.complete_at),
            state_string=row.state_string,
            results=row.results,
            urls=[UrlModel(item['name'], item['url']) for item in json.loads(row.urls_json)],
            hidden=bool(row.hidden),
        )
