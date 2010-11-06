from buildbot.status.web import change_hook
from buildbot.util import json
from buildbot.test.fake.web import MockRequest
from mock import Mock

from twisted.trial import unittest

class TestChangeHookUnconfigured(unittest.TestCase):
    def setUp(self):
        self.request = Mock()
        self.changeHook = change_hook.ChangeHookResource()

    # A bad URI should cause an exception inside check_hook.
    # After writing the test, it became apparent this can't happen.
    # I'll leave the test anyway
    def testDialectReMatchFail(self):
        self.request.uri = "/garbage/garbage"
        ret = self.changeHook.render_GET(self.request)
        expected = "URI doesn't match change_hook regex: /garbage/garbage"
        self.assertEquals(ret, expected)
        self.request.mockCheckCall(self, 0, "setResponseCode", 400, expected)

    def testUnkownDialect(self):
        self.request.uri = "/change_hook/garbage"
        ret = self.changeHook.render_GET(self.request)
        expected = "The dialect specified, 'garbage', wasn't whitelisted in change_hook"
        self.assertEquals(ret, expected )
        self.request.mockCheckCall(self, 0, "setResponseCode", 400, expected)

    def testDefaultDialect(self):
        self.request.uri = "/change_hook/"
        ret = self.changeHook.render_GET(self.request)
        expected = "The dialect specified, 'base', wasn't whitelisted in change_hook"
        self.assertEquals(ret, expected)
        self.request.mockCheckCall(self, 0, "setResponseCode", 400, expected)

class TestChangeHookConfigured(unittest.TestCase):
    def setUp(self):
        self.request = MockRequest()
        self.changeHook = change_hook.ChangeHookResource(dialects={'base' : True})

    # Test base hook with no attributes. We should get a json string representing
    # a Change object as a dictionary. All values except 'when' and 'at' will be null.
    def testDefaultDialectNullChange(self):
        self.request.uri = "/change_hook/"
        ret = self.changeHook.render_GET(self.request)
        # Change is an array of dicts holding changes. There will normally only be one
        # changes, thus only one dictionary
        changeArray = json.loads(ret)
        change = changeArray[0]
        self.assertEquals(change["category"], None)
        self.assertEquals(len(change["files"]), 0)
        self.assertEquals(change["repository"], None)
        self.assertNotEquals(change["when"], None)
        self.assertEquals(change["who"], None)
        self.assertEquals(change["rev"], None)
        self.assertEquals(change["number"], None)
        self.assertEquals(change["comments"], None)
        self.assertEquals(change["project"], None)
        self.assertNotEquals(change["at"], None)
        self.assertEquals(change["branch"], None)
        self.assertEquals(change["revlink"], None)
        self.assertEquals(len(change["properties"]), 0)
        self.assertEquals(change["revision"], None)


class TestChangeHookConfiguredWithChange(unittest.TestCase):
    def setUp(self):
        changeDict = { "category" : ["mycat"],
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
        self.request = MockRequest(changeDict)
        self.changeHook = change_hook.ChangeHookResource(dialects={'base' : True})

    # Test 'base' hook with attributes. We should get a json string representing
    # a Change object as a dictionary. All values show be set.
    def testDefaultDialectWithChange(self):
        self.request.uri = "/change_hook/"
        ret = self.changeHook.render_GET(self.request)
        # Change is an array of dicts holding changes. There will normally only be one
        # changes, thus only one dictionary
        changeArray = json.loads(ret)
        change = changeArray[0]
        self.assertEquals(change["category"], "mycat")
        files = change["files"]
        self.assertEquals(len(files), 2)
        self.assertEquals(files[0]["name"], "file1")
        self.assertEquals(files[1]["name"], "file2")
        self.assertEquals(change["repository"], "myrepo")
        self.assertEquals(change["when"], 1234)
        self.assertEquals(change["who"], "Santa Claus")
        self.assertEquals(change["rev"], '99')
        self.assertEquals(change["number"], None)
        self.assertEquals(change["comments"], "a comment")
        self.assertEquals(change["project"], "a project")
        self.assertNotEquals(change["at"], "sometime")
        self.assertEquals(change["branch"], "a branch")
        self.assertEquals(change["revlink"], "a revlink")
        properties = change["properties"]
        self.assertEquals(len(properties), 2)
        self.assertEquals(properties[0][0], "prop1")
        self.assertEquals(properties[0][1], "val1")
        self.assertEquals(properties[0][2], "Change")
        self.assertEquals(properties[1][0], "prop2")
        self.assertEquals(properties[1][1], "val2")
        self.assertEquals(properties[1][2], "Change")
        self.assertEquals(change["revision"], '99')
