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
from buildbot.test.util import compat
from buildbot.test.fake.web import FakeRequest

from twisted.trial import unittest

class TestChangeHookUnconfigured(unittest.TestCase):
    def setUp(self):
        self.request = FakeRequest()
        self.changeHook = change_hook.ChangeHookResource()

    # A bad URI should cause an exception inside check_hook.
    # After writing the test, it became apparent this can't happen.
    # I'll leave the test anyway
    def testDialectReMatchFail(self):
        self.request.uri = "/garbage/garbage"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)
        def check(ret):
            expected = "URI doesn't match change_hook regex: /garbage/garbage"
            self.assertEqual(self.request.written, expected)
            self.request.setResponseCode.assert_called_with(400, expected)
        d.addCallback(check)
        return d

    def testUnkownDialect(self):
        self.request.uri = "/change_hook/garbage"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)
        def check(ret):
            expected = "The dialect specified, 'garbage', wasn't whitelisted in change_hook"
            self.assertEqual(self.request.written, expected)
            self.request.setResponseCode.assert_called_with(400, expected)
        d.addCallback(check)
        return d

    def testDefaultDialect(self):
        self.request.uri = "/change_hook/"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)
        def check(ret):
            expected = "The dialect specified, 'base', wasn't whitelisted in change_hook"
            self.assertEqual(self.request.written, expected)
            self.request.setResponseCode.assert_called_with(400, expected)
        d.addCallback(check)
        return d

class TestChangeHookConfigured(unittest.TestCase):
    def setUp(self):
        self.request = FakeRequest()
        self.changeHook = change_hook.ChangeHookResource(dialects={'base' : True})

    def testDefaultDialectGetNullChange(self):
        self.request.uri = "/change_hook/"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)
        def check_changes(r):
            self.assertEquals(len(self.request.addedChanges), 1)
            change = self.request.addedChanges[0]
            self.assertEquals(change["category"], None)
            self.assertEquals(len(change["files"]), 0)
            self.assertEquals(change["repository"], None)
            self.assertEquals(change["when"], None)
            self.assertEquals(change["author"], None)
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
        self.request.method = "GET"
        self.request.args = { "category" : ["mycat"],
                       "files" : [json.dumps(['file1', 'file2'])],
                       "repository" : ["myrepo"],
                       "when" : [1234],
                       "author" : ["Santa Claus"],
                       "number" : [2],
                       "comments" : ["a comment"],
                       "project" : ["a project"],
                       "at" : ["sometime"],
                       "branch" : ["a branch"],
                       "revlink" : ["a revlink"],
                       "properties" : [json.dumps( { "prop1" : "val1", "prop2" : "val2" })],
                       "revision" : [99] }
        d = self.request.test_render(self.changeHook)
        def check_changes(r):
            self.assertEquals(len(self.request.addedChanges), 1)
            change = self.request.addedChanges[0]
            self.assertEquals(change["category"], "mycat")
            self.assertEquals(change["repository"], "myrepo")
            self.assertEquals(change["when"], 1234)
            self.assertEquals(change["author"], "Santa Claus")
            self.assertEquals(change["src"], None)
            self.assertEquals(change["revision"], 99)
            self.assertEquals(change["comments"], "a comment")
            self.assertEquals(change["project"], "a project")
            self.assertEquals(change["branch"], "a branch")
            self.assertEquals(change["revlink"], "a revlink")
            self.assertEquals(change['properties'], dict(prop1='val1', prop2='val2'))
            self.assertEquals(change['files'], ['file1', 'file2'])
        d.addCallback(check_changes)
        return d

    @compat.usesFlushLoggedErrors
    def testDefaultWithNoChange(self):
        self.request = FakeRequest()
        self.request.uri = "/change_hook/"
        self.request.method = "GET"
        def namedModuleMock(name):
            if name == 'buildbot.status.web.hooks.base':
                class mock_hook_module(object):
                    def getChanges(self, request, options):
                        raise AssertionError
                return mock_hook_module()
        self.patch(change_hook, "namedModule", namedModuleMock)

        d = self.request.test_render(self.changeHook)
        def check_changes(r):
            expected = "Error processing changes."
            self.assertEquals(len(self.request.addedChanges), 0)
            self.assertEqual(self.request.written, expected)
            self.request.setResponseCode.assert_called_with(500, expected)
            self.assertEqual(len(self.flushLoggedErrors(AssertionError)), 1)

        d.addCallback(check_changes)
        return d

class TestChangeHookConfiguredBogus(unittest.TestCase):
    def setUp(self):
        self.request = FakeRequest()
        self.changeHook = change_hook.ChangeHookResource(dialects={'garbage' : True})

    @compat.usesFlushLoggedErrors
    def testBogusDialect(self):
        self.request.uri = "/change_hook/garbage"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)
        def check(ret):
            expected = "Error processing changes."
            self.assertEqual(self.request.written, expected)
            self.request.setResponseCode.assert_called_with(500, expected)
            self.assertEqual(len(self.flushLoggedErrors()), 1)
        d.addCallback(check)
        return d
