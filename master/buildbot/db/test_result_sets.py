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
from twisted.python import deprecate
from twisted.python import versions

from buildbot.db import base
from buildbot.util.twisted import async_to_deferred
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    from twisted.internet import defer


@dataclass
class TestResultSetModel:
    id: int
    builderid: int
    buildid: int
    stepid: int
    description: str | None
    category: str
    value_unit: str
    tests_passed: int | None
    tests_failed: int | None
    complete: bool = False

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'TestResultSetsConnectorComponent '
                'getTestResultSet, and getTestResultSets '
                'no longer return TestResultSet as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


@deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), TestResultSetModel)
class TestResultSetDict(TestResultSetModel):
    pass


class TestResultSetAlreadyCompleted(Exception):
    pass


class TestResultSetsConnectorComponent(base.DBConnectorComponent):
    def addTestResultSet(
        self, builderid, buildid, stepid, description, category, value_unit
    ) -> defer.Deferred[int]:
        # Returns the id of the new result set
        def thd(conn) -> int:
            sets_table = self.db.model.test_result_sets

            insert_values = {
                'builderid': builderid,
                'buildid': buildid,
                'stepid': stepid,
                'description': description,
                'category': category,
                'value_unit': value_unit,
                'complete': 0,
            }

            q = sets_table.insert().values(insert_values)
            r = conn.execute(q)
            conn.commit()
            return r.inserted_primary_key[0]

        return self.db.pool.do(thd)

    def getTestResultSet(self, test_result_setid: int) -> defer.Deferred[TestResultSetModel | None]:
        def thd(conn) -> TestResultSetModel | None:
            sets_table = self.db.model.test_result_sets
            q = sets_table.select().where(sets_table.c.id == test_result_setid)
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            return self._model_from_row(row)

        return self.db.pool.do(thd)

    def getTestResultSets(
        self,
        builderid: int | None = None,
        buildid: int | None = None,
        stepid: int | None = None,
        complete: bool | None = None,
        result_spec=None,
    ) -> defer.Deferred[list[TestResultSetModel]]:
        def thd(conn) -> list[TestResultSetModel]:
            sets_table = self.db.model.test_result_sets
            q = sets_table.select()
            if builderid is not None:
                q = q.where(sets_table.c.builderid == builderid)
            if buildid is not None:
                q = q.where(sets_table.c.buildid == buildid)
            if stepid is not None:
                q = q.where(sets_table.c.stepid == stepid)
            if complete is not None:
                q = q.where(sets_table.c.complete == (1 if complete else 0))
            if result_spec is not None:
                return result_spec.thd_execute(conn, q, self._model_from_row)
            res = conn.execute(q)
            return [self._model_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    @async_to_deferred
    async def get_test_result_sets_for_commits(
        self, *, commit_ids: list[int]
    ) -> list[TestResultSetModel]:
        def thd(conn) -> list[TestResultSetModel]:
            # FIXME: the code below currently is not sufficiently robust because it relies on
            # revisions being sufficiently random so that they do not repeat across whole Buildbot
            # database. At least the following would be needed to resolve the ambiguities
            #  - attach sourcestamp to a codebase through a codebase ID
            #  - attach sourcestamp to a commit through a commit ID
            j = self.db.model.codebase_commits
            j = j.join(
                self.db.model.sourcestamps,
                self.db.model.codebase_commits.c.revision == self.db.model.sourcestamps.c.revision,
            )
            j = j.join(self.db.model.buildset_sourcestamps)
            j = j.join(self.db.model.buildsets)
            j = j.join(self.db.model.buildrequests)
            j = j.join(self.db.model.builds)
            j = j.join(self.db.model.test_result_sets)
            q = (
                sa.select(self.db.model.test_result_sets)
                .select_from(j)
                .where(self.db.model.codebase_commits.c.id.in_(commit_ids))
            )

            res = conn.execute(q)
            return [self._model_from_row(row) for row in res.fetchall()]

        return await self.db.pool.do(thd)

    def completeTestResultSet(
        self, test_result_setid, tests_passed=None, tests_failed=None
    ) -> defer.Deferred[None]:
        def thd(conn) -> None:
            sets_table = self.db.model.test_result_sets

            values = {'complete': 1}
            if tests_passed is not None:
                values['tests_passed'] = tests_passed
            if tests_failed is not None:
                values['tests_failed'] = tests_failed

            q = sets_table.update().values(values)
            q = q.where((sets_table.c.id == test_result_setid) & (sets_table.c.complete == 0))

            res = conn.execute(q)
            conn.commit()
            if res.rowcount == 0:
                raise TestResultSetAlreadyCompleted(
                    f'Test result set {test_result_setid} is already completed or does not exist'
                )

        return self.db.pool.do(thd)

    def _model_from_row(self, row):
        return TestResultSetModel(
            id=row.id,
            builderid=row.builderid,
            buildid=row.buildid,
            stepid=row.stepid,
            description=row.description,
            category=row.category,
            value_unit=row.value_unit,
            tests_passed=row.tests_passed,
            tests_failed=row.tests_failed,
            complete=bool(row.complete),
        )
