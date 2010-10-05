#import buildbot.status.web.base as wb
import buildbot.status.web.change_hook as ch
from buildbot.util import json
#import re
from mock import Mock

from twisted.trial import unittest

class TestChangeHookUnconfigured(unittest.TestCase):
    def setUp(self):
        self.request = Mock()
        self.changeHook = ch.ChangeHookResource()

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

class MockRequest(Mock):
    def __init__(self, args={}):
        self.args = args
        self.site = Mock()
        self.site.buildbot_service = Mock()
        self.site.buildbot_service.master = Mock()
        self.site.buildbot_service.master.change_svc = Mock()
        Mock.__init__(self)

class TestChangeHookConfigured(unittest.TestCase):
    def setUp(self):
        self.request = MockRequest()
        self.changeHook = ch.ChangeHookResource(dialects={'base' : True})

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
        #print changeDict
        self.request = MockRequest(changeDict)
        self.changeHook = ch.ChangeHookResource(dialects={'base' : True})

    # Test 'base' hook with attributes. We should get a json string representing
    # a Change object as a dictionary. All values show be set.
    def testDefaultDialectWithChange(self):
        self.request.uri = "/change_hook/"
        ret = self.changeHook.render_GET(self.request)
        # Change is an array of dicts holding changes. There will normally only be one
        # changes, thus only one dictionary
        #print ret
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

# Sample GITHUB commit payload from http://help.github.com/post-receive-hooks/
# Added "modfied" and "removed", and change email

gitJsonPayload = """
{
  "before": "5aef35982fb2d34e9d9d4502f6ede1072793222d",
  "repository": {
    "url": "http://github.com/defunkt/github",
    "name": "github",
    "description": "You're lookin' at it.",
    "watchers": 5,
    "forks": 2,
    "private": 1,
    "owner": {
      "email": "fred@flinstone.org",
      "name": "defunkt"
    }
  },
  "commits": [
    {
      "id": "41a212ee83ca127e3c8cf465891ab7216a705f59",
      "url": "http://github.com/defunkt/github/commit/41a212ee83ca127e3c8cf465891ab7216a705f59",
      "author": {
        "email": "fred@flinstone.org",
        "name": "Fred Flinstone"
      },
      "message": "okay i give in",
      "timestamp": "2008-02-15T14:57:17-08:00",
      "added": ["filepath.rb"]
    },
    {
      "id": "de8251ff97ee194a289832576287d6f8ad74e3d0",
      "url": "http://github.com/defunkt/github/commit/de8251ff97ee194a289832576287d6f8ad74e3d0",
      "author": {
        "email": "fred@flinstone.org",
        "name": "Fred Flinstone"
      },
      "message": "update pricing a tad",
      "timestamp": "2008-02-15T14:36:34-08:00",
      "modified": ["modfile"],
      "removed": ["removedFile"]
    }
  ],
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/heads/master"
}
"""
class TestChangeHookConfiguredWithGitChange(unittest.TestCase):
    def setUp(self):
        changeDict={"payload" : [gitJsonPayload]}
        self.request = MockRequest(changeDict)
        self.changeHook = ch.ChangeHookResource(dialects={'github' : True})

    # Test 'base' hook with attributes. We should get a json string representing
    # a Change object as a dictionary. All values show be set.
    def testGitWithChange(self):
        self.request.uri = "/change_hook/github"
        ret = self.changeHook.render_GET(self.request)
        # Change is an array of dicts holding changes. There may be multiple entries for github
        changeArray = json.loads(ret)
        change = changeArray[0]
        self.assertEquals(change["category"], None)
        files = change["files"]
        self.assertEquals(len(files), 1)
        self.assertEquals(files[0]["name"], "filepath.rb")
        self.assertEquals(change["repository"], "http://github.com/defunkt/github")
        self.assertEquals(change["when"], 1203116237)
        self.assertEquals(change["who"], "Fred Flinstone <fred@flinstone.org>")
        self.assertEquals(change["rev"], '41a212ee83ca127e3c8cf465891ab7216a705f59')
        self.assertEquals(change["number"], None)
        self.assertEquals(change["comments"], "okay i give in")
        self.assertEquals(change["project"], '')
        self.assertNotEquals(change["at"], "sometime")
        self.assertEquals(change["branch"], "master")
        self.assertEquals(change["revlink"], "http://github.com/defunkt/github/commit/41a212ee83ca127e3c8cf465891ab7216a705f59")
        properties = change["properties"]
        self.assertEquals(len(properties), 0)
        self.assertEquals(change["revision"], '41a212ee83ca127e3c8cf465891ab7216a705f59')
        # Second change
        change = changeArray[1]
        self.assertEquals(change["category"], None)
        files = change["files"]
        self.assertEquals(len(files), 2)
        self.assertEquals(files[0]["name"], "modfile")
        self.assertEquals(files[1]["name"], "removedFile")
        self.assertEquals(change["repository"], "http://github.com/defunkt/github")
        self.assertEquals(change["when"], 1203114994)
        self.assertEquals(change["who"], "Fred Flinstone <fred@flinstone.org>")
        self.assertEquals(change["rev"], 'de8251ff97ee194a289832576287d6f8ad74e3d0')
        self.assertEquals(change["number"], None)
        self.assertEquals(change["comments"], "update pricing a tad")
        self.assertEquals(change["project"], '')
        self.assertNotEquals(change["at"], "sometime")
        self.assertEquals(change["branch"], "master")
        self.assertEquals(change["revlink"], "http://github.com/defunkt/github/commit/de8251ff97ee194a289832576287d6f8ad74e3d0")
        properties = change["properties"]
        self.assertEquals(len(properties), 0)
        self.assertEquals(change["revision"], 'de8251ff97ee194a289832576287d6f8ad74e3d0')
