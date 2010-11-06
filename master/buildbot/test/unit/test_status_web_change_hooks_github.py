import buildbot.status.web.change_hook as change_hook
from buildbot.test.fake.web import MockRequest
from buildbot.util import json

from twisted.trial import unittest

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
        self.changeHook = change_hook.ChangeHookResource(dialects={'github' : True})

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
