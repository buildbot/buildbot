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
from __future__ import unicode_literals

import calendar

import mock

from twisted.internet import defer
from twisted.trial import unittest

import buildbot.www.change_hook as change_hook
from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.www.hooks.gitlab import _HEADER_EVENT
from buildbot.www.hooks.gitlab import _HEADER_GITLAB_TOKEN


# Sample GITHUB commit payload from http://help.github.com/post-receive-hooks/
# Added "modified" and "removed", and change email
gitJsonPayload = """
{
  "before": "95790bf891e76fee5e1747ab589903a6a1f80f22",
  "after": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
  "ref": "refs/heads/master",
  "user_id": 4,
  "user_name": "John Smith",
  "repository": {
    "name": "Diaspora",
    "url": "git@localhost:diaspora.git",
    "description": "",
    "homepage": "http://localhost/diaspora"
  },
  "commits": [
    {
      "id": "b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
      "message": "Update Catalan translation to e38cb41.",
      "timestamp": "2011-12-12T14:27:31+02:00",
      "url": "http://localhost/diaspora/commits/b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
      "author": {
        "name": "Jordi Mallach",
        "email": "jordi@softcatala.org"
      }
    },
    {
      "id": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
      "message": "fixed readme",
      "timestamp": "2012-01-03T23:36:29+02:00",
      "url": "http://localhost/diaspora/commits/da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
      "author": {
        "name": "GitLab dev user",
        "email": "gitlabdev@dv6700.(none)"
      }
    }
  ],
  "total_commits_count": 2
}
"""
gitJsonPayloadTag = """
{
  "object_kind": "tag_push",
  "before": "0000000000000000000000000000000000000000",
  "after": "82b3d5ae55f7080f1e6022629cdb57bfae7cccc7",
  "ref": "refs/tags/v1.0.0",
  "checkout_sha": "82b3d5ae55f7080f1e6022629cdb57bfae7cccc7",
  "user_id": 1,
  "user_name": "John Smith",
  "repository":{
    "name": "Example",
    "url": "git@localhost:diaspora.git",
    "description": "",
    "homepage": "http://example.com/jsmith/example",
    "git_http_url":"http://example.com/jsmith/example.git",
    "git_ssh_url":"git@example.com:jsmith/example.git",
    "visibility_level":0
  },
   "commits": [
     {
       "id": "b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
       "message": "Update Catalan translation to e38cb41.",
       "timestamp": "2011-12-12T14:27:31+02:00",
       "url": "http://localhost/diaspora/commits/b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
       "author": {
         "name": "Jordi Mallach",
         "email": "jordi@softcatala.org"
       }
     },
     {
       "id": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
       "message": "fixed readme",
       "timestamp": "2012-01-03T23:36:29+02:00",
       "url": "http://localhost/diaspora/commits/da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
       "author": {
         "name": "GitLab dev user",
         "email": "gitlabdev@dv6700.(none)"
       }
     }
   ],
   "total_commits_count": 2
}
"""


class TestChangeHookConfiguredWithGitChange(unittest.TestCase):

    def setUp(self):
        self.changeHook = change_hook.ChangeHookResource(
            dialects={'gitlab': True}, master=fakeMasterForHooks())

    def check_changes_tag_event(self, r, project='', codebase=None):
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]

        self.assertEqual(change["repository"], "git@localhost:diaspora.git")
        self.assertEqual(
            calendar.timegm(change["when_timestamp"].utctimetuple()),
            1323692851
        )
        self.assertEqual(change["branch"], "v1.0.0")

    def check_changes_push_event(self, r, project='', codebase=None):
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]

        self.assertEqual(change["repository"], "git@localhost:diaspora.git")
        self.assertEqual(
            calendar.timegm(change["when_timestamp"].utctimetuple()),
            1323692851
        )
        self.assertEqual(
            change["author"], "Jordi Mallach <jordi@softcatala.org>")
        self.assertEqual(
            change["revision"], 'b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327')
        self.assertEqual(
            change["comments"], "Update Catalan translation to e38cb41.")
        self.assertEqual(change["branch"], "master")
        self.assertEqual(change[
            "revlink"], "http://localhost/diaspora/commits/b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327")

        change = self.changeHook.master.addedChanges[1]
        self.assertEqual(change["repository"], "git@localhost:diaspora.git")
        self.assertEqual(
            calendar.timegm(change["when_timestamp"].utctimetuple()),
            1325626589
        )
        self.assertEqual(
            change["author"], "GitLab dev user <gitlabdev@dv6700.(none)>")
        self.assertEqual(change["src"], "git")
        self.assertEqual(
            change["revision"], 'da1560886d4f094c3e6c9ef40349f7d38b5d27d7')
        self.assertEqual(change["comments"], "fixed readme")
        self.assertEqual(change["branch"], "master")
        self.assertEqual(change[
            "revlink"], "http://localhost/diaspora/commits/da1560886d4f094c3e6c9ef40349f7d38b5d27d7")

        self.assertEqual(change.get("project"), project)
        self.assertEqual(change.get("codebase"), codebase)

    # Test 'base' hook with attributes. We should get a json string representing
    # a Change object as a dictionary. All values show be set.
    @defer.inlineCallbacks
    def testGitWithChange(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.uri = b"/change_hook/gitlab"
        self.request.method = b"POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_push_event(res)

    @defer.inlineCallbacks
    def testGitWithChange_WithProjectToo(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.uri = b"/change_hook/gitlab"
        self.request.args = {'project': ['MyProject']}
        self.request.method = b"POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_push_event(res, project="MyProject")

    @defer.inlineCallbacks
    def testGitWithChange_WithCodebaseToo(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.uri = b"/change_hook/gitlab"
        self.request.args = {'codebase': ['MyCodebase']}
        self.request.method = b"POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_push_event(res, codebase="MyCodebase")

    @defer.inlineCallbacks
    def testGitWithChange_WithPushTag(self):
        self.request = FakeRequest(content=gitJsonPayloadTag)
        self.request.uri = b"/change_hook/gitlab"
        self.request.args = {'codebase': ['MyCodebase']}
        self.request.method = b"POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_tag_event(res, codebase="MyCodebase")

    def testGitWithNoJson(self):
        self.request = FakeRequest()
        self.request.uri = b"/change_hook/gitlab"
        self.request.method = b"POST"
        d = self.request.test_render(self.changeHook)

        def check_changes(r):
            self.assertEqual(len(self.changeHook.master.addedChanges), 0)
            self.assertIn(b"Error loading JSON:", self.request.written)
            self.request.setResponseCode.assert_called_with(400, mock.ANY)

        d.addCallback(check_changes)
        return d

    @defer.inlineCallbacks
    def test_event_property(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.received_headers[_HEADER_EVENT] = "Push Hook"
        self.request.uri = b"/change_hook/gitlab"
        self.request.method = b"POST"
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change["properties"]["event"], "Push Hook")


class TestChangeHookConfiguredWithSecret(unittest.TestCase):

    _SECRET = 'thesecret'

    def setUp(self):
        self.changeHook = change_hook.ChangeHookResource(
            dialects={'gitlab': {'secret': self._SECRET}},
            master=fakeMasterForHooks())

    @defer.inlineCallbacks
    def test_missing_secret(self):
        self.request = FakeRequest(content=gitJsonPayloadTag)
        self.request.uri = b"/change_hook/gitlab"
        self.request.args = {'codebase': ['MyCodebase']}
        self.request.method = b"POST"
        yield self.request.test_render(self.changeHook)
        expected = b'Invalid secret'
        self.assertEqual(self.request.written, expected)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)

    @defer.inlineCallbacks
    def test_valid_secret(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.received_headers[_HEADER_GITLAB_TOKEN] = self._SECRET
        self.request.uri = b"/change_hook/gitlab"
        self.request.method = b"POST"
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
