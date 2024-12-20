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

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types

if TYPE_CHECKING:
    from buildbot.db.test_result_sets import TestResultSetModel


class Db2DataMixin:
    def db2data(self, model: TestResultSetModel):
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


class TestResultSetsEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = """
        /test_result_sets
        /builders/n:builderid/test_result_sets
        /builders/s:buildername/test_result_sets
        /builds/n:buildid/test_result_sets
        /steps/n:stepid/test_result_sets
        """

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

        return [self.db2data(model) for model in sets]


class TestResultSetEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = """
        /test_result_sets/n:test_result_setid
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        model = yield self.master.db.test_result_sets.getTestResultSet(kwargs['test_result_setid'])
        return self.db2data(model) if model else None


class TestResultSet(base.ResourceType):
    name = "test_result_set"
    plural = "test_result_sets"
    endpoints = [TestResultSetsEndpoint, TestResultSetEndpoint]
    eventPathPatterns = """
        /test_result_sets/:test_result_setid
    """

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
    def addTestResultSet(self, builderid, buildid, stepid, description, category, value_unit):
        test_result_setid = yield self.master.db.test_result_sets.addTestResultSet(
            builderid, buildid, stepid, description, category, value_unit
        )
        yield self.generateEvent(test_result_setid, 'new')
        return test_result_setid

    @base.updateMethod
    @defer.inlineCallbacks
    def completeTestResultSet(self, test_result_setid, tests_passed=None, tests_failed=None):
        yield self.master.db.test_result_sets.completeTestResultSet(
            test_result_setid, tests_passed, tests_failed
        )
        yield self.generateEvent(test_result_setid, 'completed')
