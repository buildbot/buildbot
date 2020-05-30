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

from buildbot.data import base
from buildbot.data import types


class Db2DataMixin:

    def db2data(self, dbdict):
        data = {
            'test_result_setid': dbdict['id'],
            'builderid': dbdict['builderid'],
            'buildid': dbdict['buildid'],
            'stepid': dbdict['stepid'],
            'description': dbdict['description'],
            'category': dbdict['category'],
            'value_unit': dbdict['value_unit'],
            'tests_passed': dbdict['tests_passed'],
            'tests_failed': dbdict['tests_failed'],
            'complete': bool(dbdict['complete']),
        }
        return defer.succeed(data)


class TestResultSetsEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /builders/n:builderid/test_result_sets
        /builders/i:buildername/test_result_sets
        /builds/n:buildid/test_result_sets
        /steps/n:stepid/test_result_sets
        """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):

        complete = resultSpec.popBooleanFilter('complete')
        if 'stepid' in kwargs:
            step_dbdict = yield self.master.db.steps.getStep(kwargs['stepid'])
            build_dbdict = yield self.master.db.builds.getBuild(step_dbdict['buildid'])

            sets = yield self.master.db.test_result_sets.getTestResultSets(
                    build_dbdict['builderid'],
                    buildid=step_dbdict['buildid'],
                    stepid=kwargs['stepid'],
                    complete=complete,
                    result_spec=resultSpec)
        elif 'buildid' in kwargs:
            build_dbdict = yield self.master.db.builds.getBuild(kwargs['buildid'])

            sets = yield self.master.db.test_result_sets.getTestResultSets(
                    build_dbdict['builderid'],
                    buildid=kwargs['buildid'],
                    complete=complete,
                    result_spec=resultSpec)

        else:
            # The following is true: 'buildername' in kwargs or 'builderid' in kwargs:
            builderid = yield self.getBuilderId(kwargs)
            sets = yield self.master.db.test_result_sets.getTestResultSets(
                    builderid, complete=complete, result_spec=resultSpec)

        results = []
        for dbdict in sets:
            results.append((yield self.db2data(dbdict)))
        return results


class TestResultSetEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /test_result_sets/n:test_result_setid
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        dbdict = yield self.master.db.test_result_sets.getTestResultSet(kwargs['test_result_setid'])
        return (yield self.db2data(dbdict)) if dbdict else None


class TestResultSet(base.ResourceType):

    name = "test_result_set"
    plural = "test_result_sets"
    endpoints = [TestResultSetsEndpoint, TestResultSetEndpoint]
    keyFields = ['test_result_setid']
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
        test_result_setid = \
            yield self.master.db.test_result_sets.addTestResultSet(builderid, buildid, stepid,
                                                                   description, category,
                                                                   value_unit)
        yield self.generateEvent(test_result_setid, 'new')
        return test_result_setid

    @base.updateMethod
    @defer.inlineCallbacks
    def completeTestResultSet(self, test_result_setid, tests_passed=None, tests_failed=None):
        yield self.master.db.test_result_sets.completeTestResultSet(test_result_setid,
                                                                    tests_passed, tests_failed)
        yield self.generateEvent(test_result_setid, 'completed')
