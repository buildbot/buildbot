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

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types
from buildbot.util.twisted import async_to_deferred

if TYPE_CHECKING:
    from buildbot.db.test_result_sets import TestResultSetModel
    from buildbot.util.twisted import InlineCallbacksType


def _db2data(model: TestResultSetModel):
    return {
        'test_result_setid': model.id,
        'builderid': model.builderid,
        'buildid': model.buildid,
        'stepid': model.stepid,
        'description': model.description,
        'category': model.category,
        'value_unit': model.value_unit,
        'tests_passed': model.tests_passed,
        'tests_failed': model.tests_failed,
        'complete': model.complete,
    }


class TestResultSetsEndpoint(base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/test_result_sets",
        "/builders/n:builderid/test_result_sets",
        "/builders/s:buildername/test_result_sets",
        "/builds/n:buildid/test_result_sets",
        "/steps/n:stepid/test_result_sets",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        complete = resultSpec.popBooleanFilter('complete')
        if 'stepid' in kwargs:
            step_dbdict = yield self.master.db.steps.getStep(kwargs['stepid'])
            build_dbdict = yield self.master.db.builds.getBuild(step_dbdict.buildid)

            sets = yield self.master.db.test_result_sets.getTestResultSets(
                build_dbdict.builderid,
                buildid=step_dbdict.buildid,
                stepid=kwargs['stepid'],
                complete=complete,
                result_spec=resultSpec,
            )
        elif 'buildid' in kwargs:
            build_dbdict = yield self.master.db.builds.getBuild(kwargs['buildid'])

            sets = yield self.master.db.test_result_sets.getTestResultSets(
                build_dbdict.builderid,
                buildid=kwargs['buildid'],
                complete=complete,
                result_spec=resultSpec,
            )

        elif 'buildername' in kwargs or 'builderid' in kwargs:
            builderid = yield self.getBuilderId(kwargs)
            sets = yield self.master.db.test_result_sets.getTestResultSets(
                builderid, complete=complete, result_spec=resultSpec
            )
        else:
            sets = yield self.master.db.test_result_sets.getTestResultSets(
                complete=complete, result_spec=resultSpec
            )

        return [_db2data(model) for model in sets]


class TestResultSetsFromCommitRangeEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/codebases/n:codebaseid/commit_range/n:commitid1/n:commitid2/test_result_sets",
    ]

    @async_to_deferred
    async def get(self, result_spec, kwargs) -> list[dict[str, Any]]:
        commit_from = int(kwargs.get('commitid1'))
        commit_to = int(kwargs.get('commitid2'))
        r = await self.master.db.codebase_commits.get_first_common_commit_with_ranges(
            commit_from, commit_to
        )
        if r is None:
            return []
        if r.to2_commit_ids[0] != commit_from:
            return []
        commit_ids = r.to2_commit_ids
        sets = await self.master.db.test_result_sets.get_test_result_sets_for_commits(
            commit_ids=commit_ids
        )
        return [_db2data(model) for model in sets]


class TestResultSetEndpoint(base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/test_result_sets/n:test_result_setid",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        model = yield self.master.db.test_result_sets.getTestResultSet(kwargs['test_result_setid'])
        return _db2data(model) if model else None


class TestResultSet(base.ResourceType):
    name = "test_result_set"
    plural = "test_result_sets"
    endpoints = [
        TestResultSetsEndpoint,
        TestResultSetsFromCommitRangeEndpoint,
        TestResultSetEndpoint,
    ]
    eventPathPatterns = [
        "/test_result_sets/:test_result_setid",
    ]

    class EntityType(types.Entity):
        test_result_setid = types.Integer()
        builderid = types.Integer()
        buildid = types.Integer()
        stepid = types.Integer()
        description = types.NoneOk(types.String())
        category = types.String()
        value_unit = types.String()
        tests_passed = types.NoneOk(types.Integer())
        tests_failed = types.NoneOk(types.Integer())
        complete = types.Boolean()

    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, test_result_setid, event):
        test_result_set = yield self.master.data.get(('test_result_sets', test_result_setid))
        self.produceEvent(test_result_set, event)

    @base.updateMethod
    @defer.inlineCallbacks
    def addTestResultSet(
        self,
        builderid: int,
        buildid: int,
        stepid: int,
        description: str,
        category: str,
        value_unit: str,
    ) -> InlineCallbacksType[int]:
        test_result_setid = yield self.master.db.test_result_sets.addTestResultSet(
            builderid, buildid, stepid, description, category, value_unit
        )
        yield self.generateEvent(test_result_setid, 'new')
        return test_result_setid

    @base.updateMethod
    @defer.inlineCallbacks
    def completeTestResultSet(
        self,
        test_result_setid: int,
        tests_passed: int | None = None,
        tests_failed: int | None = None,
    ) -> InlineCallbacksType[None]:
        yield self.master.db.test_result_sets.completeTestResultSet(
            test_result_setid, tests_passed, tests_failed
        )
        yield self.generateEvent(test_result_setid, 'completed')
