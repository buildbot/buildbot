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

from __future__ import absolute_import
from __future__ import print_function
# This is a static resource type and set of endpoints used as common data by
# tests.
from future.utils import itervalues

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
    pathPatterns = "/test"

    def get(self, resultSpec, kwargs):
        # results are sorted by ID for test stability
        return defer.succeed(sorted(itervalues(testData), key=lambda v: v['id']))


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
    pathPatterns = "/test/n:testid"

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

    class EntityType(types.Entity):
        id = types.Integer()
        info = types.String()
        success = types.Boolean()
        tags = types.List(of=types.String())
    entityType = EntityType(name)
