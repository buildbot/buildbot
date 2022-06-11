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
            'test_resultid': dbdict['id'],
            'builderid': dbdict['builderid'],
            'test_result_setid': dbdict['test_result_setid'],
            'test_name': dbdict['test_name'],
            'test_code_path': dbdict['test_code_path'],
            'line': dbdict['line'],
            'duration_ns': dbdict['duration_ns'],
            'value': dbdict['value'],
        }
        return defer.succeed(data)


class TestResultsEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /test_result_sets/n:test_result_setid/results
        """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        set_dbdict = \
            yield self.master.db.test_result_sets.getTestResultSet(kwargs['test_result_setid'])

        if set_dbdict is None:
            return []

        result_dbdicts = \
            yield self.master.db.test_results.getTestResults(set_dbdict['builderid'],
                                                             kwargs['test_result_setid'],
                                                             result_spec=resultSpec)

        results = []
        for dbdict in result_dbdicts:
            results.append((yield self.db2data(dbdict)))
        return results


class TestResult(base.ResourceType):

    name = "test_result"
    plural = "test_results"
    endpoints = [TestResultsEndpoint]
    keyField = 'test_resultid'
    eventPathPatterns = """
        /test_result_sets/:test_result_setid/results
    """

    class EntityType(types.Entity):
        test_resultid = types.Integer()
        builderid = types.Integer()
        test_result_setid = types.Integer()
        test_name = types.NoneOk(types.String())
        test_code_path = types.NoneOk(types.String())
        line = types.NoneOk(types.Integer())
        duration_ns = types.NoneOk(types.Integer())
        value = types.String()
    entityType = EntityType(name, 'TestResult')

    @base.updateMethod
    @defer.inlineCallbacks
    def addTestResults(self, builderid, test_result_setid, result_values):
        # We're not adding support for emitting any messages, because in all cases all test results
        # will be part of a test result set. The users should wait for a 'complete' event on a
        # test result set and only then fetch the test results, which won't change from that time
        # onward.
        yield self.master.db.test_results.addTestResults(builderid, test_result_setid,
                                                         result_values)
