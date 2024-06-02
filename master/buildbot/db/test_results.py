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

import sqlalchemy as sa
from twisted.internet import defer
from twisted.python import deprecate
from twisted.python import versions

from buildbot.db import base
from buildbot.warnings import warn_deprecated


@dataclass
class TestResultModel:
    id: int
    builderid: int
    test_result_setid: int
    test_name: str | None
    test_code_path: str | None
    line: int | None
    duration_ns: int | None
    value: str | None

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'TestResultsConnectorComponent '
                'getTestResult, and getTestResults '
                'no longer return TestResult as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


@deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), TestResultModel)
class TestResultDict(TestResultModel):
    pass


class TestResultsConnectorComponent(base.DBConnectorComponent):
    def _add_code_paths(self, builderid: int, paths: set[str]) -> defer.Deferred[dict[str, int]]:
        # returns a dictionary of path to id in the test_code_paths table.
        # For paths that already exist, the id of the row in the test_code_paths is retrieved.
        assert isinstance(paths, set)

        def thd(conn) -> dict[str, int]:
            paths_to_ids = {}
            paths_table = self.db.model.test_code_paths

            for path_batch in self.doBatch(paths, batch_n=3000):
                path_batch = set(path_batch)

                while path_batch:
                    # Use expanding bindparam, because performance of sqlalchemy is very slow
                    # when filtering large sets otherwise.
                    q = paths_table.select().where(
                        (paths_table.c.path.in_(sa.bindparam('paths', expanding=True)))
                        & (paths_table.c.builderid == builderid)
                    )

                    res = conn.execute(q, {'paths': list(path_batch)})
                    for row in res.fetchall():
                        paths_to_ids[row.path] = row.id
                        path_batch.remove(row.path)

                    # paths now contains all the paths that need insertion.
                    try:
                        insert_values = [
                            {'builderid': builderid, 'path': path} for path in path_batch
                        ]

                        q = paths_table.insert().values(insert_values)

                        if self.db.pool.engine.dialect.name in ['postgresql', 'mssql']:
                            # Use RETURNING, this way we won't need an additional select query
                            q = q.returning(paths_table.c.id, paths_table.c.path)

                            res = conn.execute(q)
                            conn.commit()
                            for row in res.fetchall():
                                paths_to_ids[row.path] = row.id
                                path_batch.remove(row.path)
                        else:
                            conn.execute(q)
                            conn.commit()

                    except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                        # There was a competing addCodePaths() call that added a path for the same
                        # builder. Depending on the DB driver, none or some rows were inserted, but
                        # we will re-check what's got inserted in the next iteration of the loop
                        conn.rollback()

            return paths_to_ids

        return self.db.pool.do(thd)

    def getTestCodePaths(
        self, builderid, path_prefix: str | None = None, result_spec=None
    ) -> defer.Deferred[list[str]]:
        def thd(conn) -> list[str]:
            paths_table = self.db.model.test_code_paths
            q = paths_table.select()
            if path_prefix is not None:
                q = q.where(paths_table.c.path.startswith(path_prefix))
            if result_spec is not None:
                return result_spec.thd_execute(conn, q, lambda x: x['path'])
            res = conn.execute(q)
            return [row.path for row in res.fetchall()]

        return self.db.pool.do(thd)

    def _add_names(self, builderid: int, names: set[str]) -> defer.Deferred[dict[str, int]]:
        # returns a dictionary of name to id in the test_names table.
        # For names that already exist, the id of the row in the test_names is retrieved.
        assert isinstance(names, set)

        def thd(conn) -> dict[str, int]:
            names_to_ids = {}
            names_table = self.db.model.test_names

            for name_batch in self.doBatch(names, batch_n=3000):
                name_batch = set(name_batch)
                while name_batch:
                    # Use expanding bindparam, because performance of sqlalchemy is very slow
                    # when filtering large sets otherwise.
                    q = names_table.select().where(
                        (names_table.c.name.in_(sa.bindparam('names', expanding=True)))
                        & (names_table.c.builderid == builderid)
                    )

                    res = conn.execute(q, {'names': list(name_batch)})
                    for row in res.fetchall():
                        names_to_ids[row.name] = row.id
                        name_batch.remove(row.name)

                    # names now contains all the names that need insertion.
                    try:
                        insert_values = [
                            {'builderid': builderid, 'name': name} for name in name_batch
                        ]

                        q = names_table.insert().values(insert_values)

                        if self.db.pool.engine.dialect.name in ['postgresql', 'mssql']:
                            # Use RETURNING, this way we won't need an additional select query
                            q = q.returning(names_table.c.id, names_table.c.name)

                            res = conn.execute(q)
                            conn.commit()
                            for row in res.fetchall():
                                names_to_ids[row.name] = row.id
                                name_batch.remove(row.name)
                        else:
                            conn.execute(q)
                            conn.commit()

                    except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                        # There was a competing addNames() call that added a name for the same
                        # builder. Depending on the DB driver, none or some rows were inserted, but
                        # we will re-check what's got inserted in the next iteration of the loop
                        conn.rollback()

            return names_to_ids

        return self.db.pool.do(thd)

    def getTestNames(
        self, builderid, name_prefix=None, result_spec=None
    ) -> defer.Deferred[list[str]]:
        def thd(conn) -> list[str]:
            names_table = self.db.model.test_names
            q = names_table.select().where(names_table.c.builderid == builderid)
            if name_prefix is not None:
                q = q.where(names_table.c.name.startswith(name_prefix))
            if result_spec is not None:
                return result_spec.thd_execute(conn, q, lambda x: x.name)
            res = conn.execute(q)
            return [row.name for row in res.fetchall()]

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def addTestResults(self, builderid, test_result_setid, result_values):
        # Adds multiple test results for a specific test result set.
        # result_values is a list of dictionaries each of which must contain 'value' key and at
        # least one of 'test_name', 'test_code_path'. 'line' key is optional.
        # The function returns nothing.

        # Build values list for insertion.
        insert_values = []

        insert_names = set()
        insert_code_paths = set()
        for result_value in result_values:
            if 'value' not in result_value:
                raise KeyError('Each of result_values must contain \'value\' key')

            if 'test_name' not in result_value and 'test_code_path' not in result_value:
                raise KeyError(
                    'Each of result_values must contain at least one of '
                    '\'test_name\' or \'test_code_path\' keys'
                )

            if 'test_name' in result_value:
                insert_names.add(result_value['test_name'])
            if 'test_code_path' in result_value:
                insert_code_paths.add(result_value['test_code_path'])

        code_path_to_id = yield self._add_code_paths(builderid, insert_code_paths)
        name_to_id = yield self._add_names(builderid, insert_names)

        for result_value in result_values:
            insert_value = {
                'value': result_value['value'],
                'builderid': builderid,
                'test_result_setid': test_result_setid,
                'test_nameid': None,
                'test_code_pathid': None,
                'line': None,
                'duration_ns': None,
            }

            if 'test_name' in result_value:
                insert_value['test_nameid'] = name_to_id[result_value['test_name']]
            if 'test_code_path' in result_value:
                insert_value['test_code_pathid'] = code_path_to_id[result_value['test_code_path']]
            if 'line' in result_value:
                insert_value['line'] = result_value['line']
            if 'duration_ns' in result_value:
                insert_value['duration_ns'] = result_value['duration_ns']

            insert_values.append(insert_value)

        def thd(conn):
            results_table = self.db.model.test_results
            q = results_table.insert().values(insert_values)
            conn.execute(q)

        yield self.db.pool.do_with_transaction(thd)

    def getTestResult(self, test_resultid: int) -> defer.Deferred[TestResultModel | None]:
        def thd(conn) -> TestResultModel | None:
            results_table = self.db.model.test_results
            code_paths_table = self.db.model.test_code_paths
            names_table = self.db.model.test_names

            j = results_table.outerjoin(code_paths_table).outerjoin(names_table)

            q = sa.select(results_table, code_paths_table.c.path, names_table.c.name)
            q = q.select_from(j).where(results_table.c.id == test_resultid)

            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            return self._mode_from_row(row)

        return self.db.pool.do(thd)

    def getTestResults(
        self, builderid: int, test_result_setid: int, result_spec=None
    ) -> defer.Deferred[list[TestResultModel]]:
        def thd(conn) -> list[TestResultModel]:
            results_table = self.db.model.test_results
            code_paths_table = self.db.model.test_code_paths
            names_table = self.db.model.test_names

            # specify join ON clauses manually to force filtering of code_paths_table and
            # names_table before join

            j = results_table.outerjoin(
                code_paths_table,
                (results_table.c.test_code_pathid == code_paths_table.c.id)
                & (code_paths_table.c.builderid == builderid),
            )

            j = j.outerjoin(
                names_table,
                (results_table.c.test_nameid == names_table.c.id)
                & (names_table.c.builderid == builderid),
            )

            q = sa.select(results_table, code_paths_table.c.path, names_table.c.name)
            q = q.select_from(j).where(
                (results_table.c.builderid == builderid)
                & (results_table.c.test_result_setid == test_result_setid)
            )

            if result_spec is not None:
                return result_spec.thd_execute(conn, q, self._mode_from_row)
            res = conn.execute(q)
            return [self._mode_from_row(row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    def _mode_from_row(self, row):
        return TestResultModel(
            id=row.id,
            builderid=row.builderid,
            test_result_setid=row.test_result_setid,
            test_name=row.name,
            test_code_path=row.path,
            line=row.line,
            duration_ns=row.duration_ns,
            value=row.value,
        )
