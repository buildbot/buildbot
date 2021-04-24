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
    13: {'id': 13, 'info': 'ok', 'success': True, 'tags': []},
    14: {'id': 14, 'info': 'failed', 'success': False, 'tags': []},
    15: {'id': 15, 'info': 'warned', 'success': True, 'tags': ['a', 'b', ]},
    16: {'id': 16, 'info': 'skipped', 'success': True, 'tags': ['a']},
    17: {'id': 17, 'info': 'ignored', 'success': True, 'tags': []},
    18: {'id': 18, 'info': 'unexp', 'success': False, 'tags': []},
    19: {'id': 19, 'info': 'todo', 'success': True, 'tags': []},
    20: {'id': 20, 'info': 'error', 'success': False, 'tags': []},
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
        return defer.succeed(sorted(testData.values(), key=lambda v: v['id']))


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


class Test(base.ResourceType):
    name = "test"
    plural = "tests"
    endpoints = [TestsEndpoint, TestEndpoint, FailEndpoint, RawTestsEndpoint]
    keyFields = ["id"]

    class EntityType(types.Entity):
        id = types.Integer()
        info = types.String()
        success = types.Boolean()
        tags = types.List(of=types.String())
    entityType = EntityType(name)


graphql_schema = """
# custom scalar types for buildbot data model
scalar Date   # stored as utc unix timestamp
scalar Binary # arbitrary data stored as base85
scalar JSON  # arbitrary json stored as string, mainly used for properties values
type Query {
  tests(id: Int,
   id__contains: Int,
   id__eq: Int,
   id__ge: Int,
   id__gt: Int,
   id__le: Int,
   id__lt: Int,
   id__ne: Int,
   info: String,
   info__contains: String,
   info__eq: String,
   info__ge: String,
   info__gt: String,
   info__le: String,
   info__lt: String,
   info__ne: String,
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
   tags__le: String,
   tags__lt: String,
   tags__ne: String,
   order: String,
   limit: Int,
   offset: Int): [Test]!
  test(id: Int): Test
}
type Test {
  id: Int!
  info: String!
  success: Boolean!
  tags: [String]!
}
"""
