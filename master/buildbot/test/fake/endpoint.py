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

# This is a static resource type and set of endpoints used as common data by
# tests.
from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types

testData = {
    13: {'testid': 13, 'info': 'ok', 'success': True, 'tags': []},
    14: {'testid': 14, 'info': 'failed', 'success': False, 'tags': []},
    15: {'testid': 15, 'info': 'warned', 'success': True, 'tags': ['a', 'b', ]},
    16: {'testid': 16, 'info': 'skipped', 'success': True, 'tags': ['a']},
    17: {'testid': 17, 'info': 'ignored', 'success': True, 'tags': []},
    18: {'testid': 18, 'info': 'unexp', 'success': False, 'tags': []},
    19: {'testid': 19, 'info': 'todo', 'success': True, 'tags': []},
    20: {'testid': 20, 'info': 'error', 'success': False, 'tags': []},
}
stepData = {
    13: {'stepid': 13, 'testid': 13, 'info': 'ok'},
    14: {'stepid': 14, 'testid': 13, 'info': 'failed'},
    15: {'stepid': 15, 'testid': 14, 'info': 'failed'},
}


class TestsEndpoint(base.Endpoint):
    isCollection = True
    pathPatterns = """
    /tests
    /test
    """
    rootLinkName = 'tests'

    def get(self, resultSpec, kwargs):
        # results are sorted by ID for test stability
        return defer.succeed(sorted(testData.values(), key=lambda v: v['testid']))


class RawTestsEndpoint(base.Endpoint):
    isCollection = False
    isRaw = True
    pathPatterns = "/rawtest"

    def get(self, resultSpec, kwargs):
        return defer.succeed({
            "filename": "test.txt",
            "mime-type": "text/test",
            'raw': 'value'
        })


class FailEndpoint(base.Endpoint):
    isCollection = False
    pathPatterns = "/test/fail"

    def get(self, resultSpec, kwargs):
        return defer.fail(RuntimeError('oh noes'))


class TestEndpoint(base.Endpoint):
    isCollection = False
    pathPatterns = """
    /tests/n:testid
    /test/n:testid
    """

    def get(self, resultSpec, kwargs):
        if kwargs['testid'] == 0:
            return None
        return defer.succeed(testData[kwargs['testid']])

    def control(self, action, args, kwargs):
        if action == "fail":
            return defer.fail(RuntimeError("oh noes"))
        return defer.succeed({'action': action, 'args': args, 'kwargs': kwargs})


class StepsEndpoint(base.Endpoint):
    isCollection = True
    pathPatterns = "/tests/n:testid/steps"

    def get(self, resultSpec, kwargs):
        data = [step for step in stepData.values() if step['testid'] == kwargs['testid']]
        # results are sorted by ID for test stability
        return defer.succeed(sorted(data, key=lambda v: v['stepid']))


class StepEndpoint(base.Endpoint):
    isCollection = False
    pathPatterns = "/tests/n:testid/steps/n:stepid"

    def get(self, resultSpec, kwargs):
        if kwargs['testid'] == 0:
            return None
        return defer.succeed(testData[kwargs['testid']])


class Step(base.ResourceType):
    name = "step"
    plural = "steps"
    endpoints = [StepsEndpoint, StepEndpoint]
    keyField = "stepid"

    class EntityType(types.Entity):
        stepid = types.Integer()
        testid = types.Integer()
        info = types.String()
    entityType = EntityType(name, 'Step')


class Test(base.ResourceType):
    name = "test"
    plural = "tests"
    endpoints = [TestsEndpoint, TestEndpoint, FailEndpoint, RawTestsEndpoint]
    keyField = "testid"
    subresources = ["Step"]

    class EntityType(types.Entity):
        testid = types.Integer()
        info = types.String()
        success = types.Boolean()
        tags = types.List(of=types.String())
    entityType = EntityType(name, 'Test')


graphql_schema = """
# custom scalar types for buildbot data model
scalar Date   # stored as utc unix timestamp
scalar Binary # arbitrary data stored as base85
scalar JSON  # arbitrary json stored as string, mainly used for properties values
type Query {{
{queries}
}}
type Subscription {{
{queries}
}}
type Test {{
  testid: Int!
  info: String!
  success: Boolean!
  tags: [String]!
  steps(info: String,
   info__contains: String,
   info__eq: String,
   info__ge: String,
   info__gt: String,
   info__in: [String],
   info__le: String,
   info__lt: String,
   info__ne: String,
   info__notin: [String],
   stepid: Int,
   stepid__contains: Int,
   stepid__eq: Int,
   stepid__ge: Int,
   stepid__gt: Int,
   stepid__in: [Int],
   stepid__le: Int,
   stepid__lt: Int,
   stepid__ne: Int,
   stepid__notin: [Int],
   testid: Int,
   testid__contains: Int,
   testid__eq: Int,
   testid__ge: Int,
   testid__gt: Int,
   testid__in: [Int],
   testid__le: Int,
   testid__lt: Int,
   testid__ne: Int,
   testid__notin: [Int],
   order: String,
   limit: Int,
   offset: Int): [Step]!
  step(stepid: Int): Step
}}
type Step {{
  stepid: Int!
  testid: Int!
  info: String!
}}
""".format(queries="""  tests(info: String,
   info__contains: String,
   info__eq: String,
   info__ge: String,
   info__gt: String,
   info__in: [String],
   info__le: String,
   info__lt: String,
   info__ne: String,
   info__notin: [String],
   success: Boolean,
   success__contains: Boolean,
   success__eq: Boolean,
   success__ge: Boolean,
   success__gt: Boolean,
   success__le: Boolean,
   success__lt: Boolean,
   success__ne: Boolean,
   tags: String,
   tags__contains: String,
   tags__eq: String,
   tags__ge: String,
   tags__gt: String,
   tags__in: [String],
   tags__le: String,
   tags__lt: String,
   tags__ne: String,
   tags__notin: [String],
   testid: Int,
   testid__contains: Int,
   testid__eq: Int,
   testid__ge: Int,
   testid__gt: Int,
   testid__in: [Int],
   testid__le: Int,
   testid__lt: Int,
   testid__ne: Int,
   testid__notin: [Int],
   order: String,
   limit: Int,
   offset: Int): [Test]!
  test(testid: Int): Test""")
