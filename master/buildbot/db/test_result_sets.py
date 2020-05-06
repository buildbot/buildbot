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

from twisted.internet import defer

from buildbot.db import base


class TestResultSetDict(dict):
    pass


class TestResultSetAlreadyCompleted(Exception):
    pass


class TestResultSetsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst

    @defer.inlineCallbacks
    def addTestResultSet(self, builderid, buildid, stepid, description, category, value_unit):
        # Returns the id of the new result set
        def thd(conn):
            sets_table = self.db.model.test_result_sets

            insert_values = {
                'builderid': builderid,
                'buildid': buildid,
                'stepid': stepid,
                'description': description,
                'category': category,
                'value_unit': value_unit,
                'complete': 0
            }

            q = sets_table.insert().values(insert_values)
            r = conn.execute(q)
            return r.inserted_primary_key[0]

        res = yield self.db.pool.do(thd)
        return res

    @defer.inlineCallbacks
    def getTestResultSet(self, test_result_setid):
        def thd(conn):
            sets_table = self.db.model.test_result_sets
            q = sets_table.select().where(sets_table.c.id == test_result_setid)
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            return self._thd_row2dict(conn, row)
        res = yield self.db.pool.do(thd)
        return res

    @defer.inlineCallbacks
    def getTestResultSets(self, builderid, buildid=None, stepid=None, complete=None,
                          result_spec=None):
        def thd(conn):
            sets_table = self.db.model.test_result_sets
            q = sets_table.select().where(sets_table.c.builderid == builderid)
            if buildid is not None:
                q = q.where(sets_table.c.buildid == buildid)
            if stepid is not None:
                q = q.where(sets_table.c.stepid == stepid)
            if complete is not None:
                q = q.where(sets_table.c.complete == (1 if complete else 0))
            if result_spec is not None:
                return result_spec.thd_execute(conn, q, lambda x: self._thd_row2dict(conn, x))
            res = conn.execute(q)
            return [self._thd_row2dict(conn, row) for row in res.fetchall()]
        res = yield self.db.pool.do(thd)
        return res

    @defer.inlineCallbacks
    def completeTestResultSet(self, test_result_setid, tests_passed=None, tests_failed=None):
        def thd(conn):
            sets_table = self.db.model.test_result_sets

            values = {'complete': 1}
            if tests_passed is not None:
                values['tests_passed'] = tests_passed
            if tests_failed is not None:
                values['tests_failed'] = tests_failed

            q = sets_table.update().values(values)
            q = q.where((sets_table.c.id == test_result_setid) &
                        (sets_table.c.complete == 0))

            res = conn.execute(q)
            if res.rowcount == 0:
                raise TestResultSetAlreadyCompleted(('Test result set {} is already completed '
                                                     'or does not exist').format(test_result_setid))
        yield self.db.pool.do(thd)

    def _thd_row2dict(self, conn, row):
        return TestResultSetDict(id=row.id,
                                 builderid=row.builderid,
                                 buildid=row.buildid,
                                 stepid=row.stepid,
                                 description=row.description,
                                 category=row.category,
                                 value_unit=row.value_unit,
                                 tests_passed=row.tests_passed,
                                 tests_failed=row.tests_failed,
                                 complete=bool(row.complete))
