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
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.test.reactor import TestReactorMixin
from buildbot.www import change_hook

# Sample Gitorious commit payload
# source: http://gitorious.org/gitorious/pages/WebHooks
gitJsonPayload = b"""
{
  "after": "df5744f7bc8663b39717f87742dc94f52ccbf4dd",
  "before": "b4ca2d38e756695133cbd0e03d078804e1dc6610",
  "commits": [
    {
      "author": {
        "email": "jason@nospam.org",
        "name": "jason"
      },
      "committed_at": "2012-01-10T11:02:27-07:00",
      "id": "df5744f7bc8663b39717f87742dc94f52ccbf4dd",
      "message": "added a place to put the docstring for Book",
      "timestamp": "2012-01-10T11:02:27-07:00",
      "url": "http://gitorious.org/q/mainline/commit/df5744f7bc8663b39717f87742dc94f52ccbf4dd"
    }
  ],
  "project": {
    "description": "a webapp to organize your ebook collectsion.",
    "name": "q"
  },
  "pushed_at": "2012-01-10T11:09:25-07:00",
  "pushed_by": "jason",
  "ref": "new_look",
  "repository": {
    "clones": 4,
    "description": "",
    "name": "mainline",
    "owner": {
      "name": "jason"
    },
    "url": "http://gitorious.org/q/mainline"
  }
}
"""


class TestChangeHookConfiguredWithGitChange(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        dialects = {'gitorious': True}
        master = yield fakeMasterForHooks(self)
        self.changeHook = change_hook.ChangeHookResource(dialects=dialects, master=master)

    # Test 'base' hook with attributes. We should get a json string
    # representing a Change object as a dictionary. All values show be set.
    @defer.inlineCallbacks
    def testGitWithChange(self):
        changeDict = {b"payload": [gitJsonPayload]}
        self.request = FakeRequest(changeDict)
        self.request.uri = b"/change_hook/gitorious"
        self.request.method = b"POST"
        yield self.request.test_render(self.changeHook)

        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 1)
        change = self.changeHook.master.data.updates.changesAdded[0]

        # Gitorious doesn't send changed files
        self.assertEqual(change['files'], [])
        self.assertEqual(change["repository"], "http://gitorious.org/q/mainline")
        self.assertEqual(change["when_timestamp"], 1326218547)
        self.assertEqual(change["author"], "jason <jason@nospam.org>")
        self.assertEqual(change["revision"], 'df5744f7bc8663b39717f87742dc94f52ccbf4dd')
        self.assertEqual(change["comments"], "added a place to put the docstring for Book")
        self.assertEqual(change["branch"], "new_look")
        revlink = "http://gitorious.org/q/mainline/commit/df5744f7bc8663b39717f87742dc94f52ccbf4dd"
        self.assertEqual(change["revlink"], revlink)

    @defer.inlineCallbacks
    def testGitWithNoJson(self):
        self.request = FakeRequest()
        self.request.uri = b"/change_hook/gitorious"
        self.request.method = b"GET"
        yield self.request.test_render(self.changeHook)

        expected = b"Error processing changes."
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 0)
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(500, expected)
        self.assertEqual(len(self.flushLoggedErrors()), 1)
