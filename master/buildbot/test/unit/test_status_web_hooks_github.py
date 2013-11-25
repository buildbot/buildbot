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

import calendar

import buildbot.status.web.change_hook as change_hook

from buildbot.test.fake.web import FakeRequest
from buildbot.test.util import compat

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
      "distinct": true,
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

gitJsonPayloadNonBranch = """
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
      "distinct": true,
      "url": "http://github.com/defunkt/github/commit/41a212ee83ca127e3c8cf465891ab7216a705f59",
      "author": {
        "email": "fred@flinstone.org",
        "name": "Fred Flinstone"
      },
      "message": "okay i give in",
      "timestamp": "2008-02-15T14:57:17-08:00",
      "added": ["filepath.rb"]
    }
  ],
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/garbage/master"
}
"""

gitJsonPayloadEmpty = """
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
  ],
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/heads/master"
}
"""


class TestChangeHookConfiguredWithGitChange(unittest.TestCase):

    def setUp(self):
        self.changeHook = change_hook.ChangeHookResource(
            dialects={'github': True})

    # Test 'base' hook with attributes. We should get a json string
    # representing a Change object as a dictionary. All values show be set.
    def testGitWithChange(self):
        changeDict = {"payload": [gitJsonPayload]}
        self.request = FakeRequest(changeDict)
        self.request.uri = "/change_hook/github"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)

        def check_changes(r):
            self.assertEquals(len(self.request.addedChanges), 2)
            change = self.request.addedChanges[0]

            self.assertEquals(change['files'], ['filepath.rb'])
            self.assertEquals(
                change["repository"], "http://github.com/defunkt/github")
            self.assertEquals(
                calendar.timegm(change["when_timestamp"].utctimetuple()),
                1203116237
            )
            self.assertEquals(
                change["author"], "Fred Flinstone <fred@flinstone.org>")
            self.assertEquals(
                change["revision"], '41a212ee83ca127e3c8cf465891ab7216a705f59')
            self.assertEquals(
                change["comments"], "okay i give in")
            self.assertEquals(
                change["branch"], "master")
            self.assertEquals(
                change["revlink"],
                "http://github.com/defunkt/github/commit/"
                "41a212ee83ca127e3c8cf465891ab7216a705f59"
            )

            change = self.request.addedChanges[1]
            self.assertEquals(change['files'], ['modfile', 'removedFile'])
            self.assertEquals(
                change["repository"], "http://github.com/defunkt/github")
            self.assertEquals(
                calendar.timegm(change["when_timestamp"].utctimetuple()),
                1203114994
            )
            self.assertEquals(
                change["author"], "Fred Flinstone <fred@flinstone.org>")
            self.assertEquals(change["src"], "git")
            self.assertEquals(
                change["revision"], 'de8251ff97ee194a289832576287d6f8ad74e3d0')
            self.assertEquals(change["comments"], "update pricing a tad")
            self.assertEquals(change["branch"], "master")
            self.assertEquals(
                change["revlink"],
                "http://github.com/defunkt/github/commit/"
                "de8251ff97ee194a289832576287d6f8ad74e3d0"
            )

        d.addCallback(check_changes)
        return d

    def testGitWithDistinctFalse(self):
        changeDict = {"payload": [gitJsonPayload.replace(
            '"distinct": true,', '"distinct": false,')]
        }
        self.request = FakeRequest(changeDict)
        self.request.uri = "/change_hook/github"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)

        def check_changes(r):
            self.assertEqual(len(self.request.addedChanges), 1)
            change = self.request.addedChanges[0]

            self.assertEqual(
                change['files'], ['modfile', 'removedFile'])
            self.assertEqual(
                change["repository"], "http://github.com/defunkt/github")
            self.assertEqual(
                calendar.timegm(change["when_timestamp"].utctimetuple()),
                1203114994
            )
            self.assertEqual(
                change["author"], "Fred Flinstone <fred@flinstone.org>")
            self.assertEqual(
                change["src"], "git")
            self.assertEqual(
                change["revision"], 'de8251ff97ee194a289832576287d6f8ad74e3d0')
            self.assertEqual(change["comments"], "update pricing a tad")
            self.assertEqual(change["branch"], "master")
            self.assertEqual(
                change["revlink"],
                "http://github.com/defunkt/github/commit/"
                "de8251ff97ee194a289832576287d6f8ad74e3d0"
            )

        d.addCallback(check_changes)
        return d

    @compat.usesFlushLoggedErrors
    def testGitWithNoJson(self):
        self.request = FakeRequest()
        self.request.uri = "/change_hook/github"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)

        def check_changes(r):
            expected = "Error processing changes."
            self.assertEquals(len(self.request.addedChanges), 0)
            self.assertEqual(self.request.written, expected)
            self.request.setResponseCode.assert_called_with(500, expected)
            self.assertEqual(len(self.flushLoggedErrors()), 1)

        d.addCallback(check_changes)
        return d

    def testGitWithNoChanges(self):
        changeDict = {"payload": [gitJsonPayloadEmpty]}
        self.request = FakeRequest(changeDict)
        self.request.uri = "/change_hook/github"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)

        def check_changes(r):
            expected = "no changes found"
            self.assertEquals(len(self.request.addedChanges), 0)
            self.assertEqual(self.request.written, expected)

        d.addCallback(check_changes)
        return d

    def testGitWithNonBranchChanges(self):
        changeDict = {"payload": [gitJsonPayloadNonBranch]}
        self.request = FakeRequest(changeDict)
        self.request.uri = "/change_hook/github"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)

        def check_changes(r):
            expected = "no changes found"
            self.assertEquals(len(self.request.addedChanges), 0)
            self.assertEqual(self.request.written, expected)

        d.addCallback(check_changes)
        return d
