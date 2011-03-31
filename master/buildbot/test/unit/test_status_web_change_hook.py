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

from buildbot.status.web import change_hook
from buildbot.util import json
from buildbot.test.fake.web import MockRequest
from mock import Mock

from twisted.trial import unittest
from twisted.internet import defer

class TestChangeHookUnconfigured(unittest.TestCase):
    def setUp(self):
        self.request = Mock()
        self.changeHook = change_hook.ChangeHookResource()

    # A bad URI should cause an exception inside check_hook.
    # After writing the test, it became apparent this can't happen.
    # I'll leave the test anyway
    def testDialectReMatchFail(self):
        self.request.uri = "/garbage/garbage"
        d = self.changeHook.render_GET(self.request)
        def check(ret):
            expected = "URI doesn't match change_hook regex: /garbage/garbage"
            self.assertEquals(ret, expected)
            self.request.mockCheckCall(self, 0, "setResponseCode", 400, expected)
        d.addCallback(check)
        return d

    def testUnkownDialect(self):
        self.request.uri = "/change_hook/garbage"
        d = self.changeHook.render_GET(self.request)
        def check(ret):
            expected = "The dialect specified, 'garbage', wasn't whitelisted in change_hook"
            self.assertEquals(ret, expected )
            self.request.mockCheckCall(self, 0, "setResponseCode", 400, expected)
        d.addCallback(check)
        return d

    def testDefaultDialect(self):
        self.request.uri = "/change_hook/"
        d = self.changeHook.render_GET(self.request)
        def check(ret):
            expected = "The dialect specified, 'base', wasn't whitelisted in change_hook"
            self.assertEquals(ret, expected)
            self.request.mockCheckCall(self, 0, "setResponseCode", 400, expected)
        d.addCallback(check)
        return d

class TestChangeHookConfigured(unittest.TestCase):
    def setUp(self):
        self.request = MockRequest()
        self.changeHook = change_hook.ChangeHookResource(dialects={'base' : True})

    def testDefaultDialectGetNullChange(self):
        self.request.uri = "/change_hook/"
        d = defer.maybeDeferred(lambda : self.changeHook.render_GET(self.request))
        def check_changes(r):
            self.assertEquals(len(self.request.addedChanges), 1)
            change = self.request.addedChanges[0]
            self.assertEquals(change["category"], None)
            self.assertEquals(len(change["files"]), 0)
            self.assertEquals(change["repository"], None)
            self.assertEquals(change["when"], None)
            self.assertEquals(change["who"], None)
            self.assertEquals(change["revision"], None)
            self.assertEquals(change["comments"], None)
            self.assertEquals(change["project"], None)
            self.assertEquals(change["branch"], None)
            self.assertEquals(change["revlink"], None)
            self.assertEquals(len(change["properties"]), 0)
            self.assertEquals(change["revision"], None)
        d.addCallback(check_changes)
        return d

    # Test 'base' hook with attributes. We should get a json string representing
    # a Change object as a dictionary. All values show be set.
    def testDefaultDialectWithChange(self):
        self.request.uri = "/change_hook/"
        self.request.args = { "category" : ["mycat"],
                       "files" : [json.dumps(['file1', 'file2'])],
                       "repository" : ["myrepo"],
                       "when" : [1234],
                       "who" : ["Santa Claus"],
                       "number" : [2],
                       "comments" : ["a comment"],
                       "project" : ["a project"],
                       "at" : ["sometime"],
                       "branch" : ["a branch"],
                       "revlink" : ["a revlink"],
                       "properties" : [json.dumps( { "prop1" : "val1", "prop2" : "val2" })],
                       "revision" : [99] }
        d = defer.maybeDeferred(lambda : self.changeHook.render_GET(self.request))
        def check_changes(r):
            self.assertEquals(len(self.request.addedChanges), 1)
            change = self.request.addedChanges[0]
            self.assertEquals(change["category"], "mycat")
            self.assertEquals(change["repository"], "myrepo")
            self.assertEquals(change["when"], 1234)
            self.assertEquals(change["who"], "Santa Claus")
            self.assertEquals(change["revision"], 99)
            self.assertEquals(change["comments"], "a comment")
            self.assertEquals(change["project"], "a project")
            self.assertEquals(change["branch"], "a branch")
            self.assertEquals(change["revlink"], "a revlink")
            self.assertEquals(change['properties'], dict(prop1='val1', prop2='val2'))
            self.assertEquals(change['files'], ['file1', 'file2'])
        d.addCallback(check_changes)
        return d
