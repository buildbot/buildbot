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

import mock
from twisted.internet import defer
from twisted.trial import unittest

import buildbot.www.change_hook as change_hook
from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks


# Sample GITHUB commit payload from http://help.github.com/post-receive-hooks/
# Added "modfied" and "removed", and change email
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


class TestChangeHookConfiguredWithGitChange(unittest.TestCase):

    def setUp(self):
        self.changeHook = change_hook.ChangeHookResource(
            dialects={'gitlab': True}, master=fakeMasterForHooks())

    def check_changes(self, r, project='', codebase=None):
        self.assertEquals(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]

        self.assertEquals(change["repository"], "git@localhost:diaspora.git")
        self.assertEquals(
            calendar.timegm(change["when_timestamp"].utctimetuple()),
            1323692851
        )
        self.assertEquals(
            change["author"], "Jordi Mallach <jordi@softcatala.org>")
        self.assertEquals(
            change["revision"], 'b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327')
        self.assertEquals(
            change["comments"], "Update Catalan translation to e38cb41.")
        self.assertEquals(change["branch"], "master")
        self.assertEquals(change[
                          "revlink"], "http://localhost/diaspora/commits/b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327")

        change = self.changeHook.master.addedChanges[1]
        self.assertEquals(change["repository"], "git@localhost:diaspora.git")
        self.assertEquals(
            calendar.timegm(change["when_timestamp"].utctimetuple()),
            1325626589
        )
        self.assertEquals(
            change["author"], "GitLab dev user <gitlabdev@dv6700.(none)>")
        self.assertEquals(change["src"], "git")
        self.assertEquals(
            change["revision"], 'da1560886d4f094c3e6c9ef40349f7d38b5d27d7')
        self.assertEquals(change["comments"], "fixed readme")
        self.assertEquals(change["branch"], "master")
        self.assertEquals(change[
                          "revlink"], "http://localhost/diaspora/commits/da1560886d4f094c3e6c9ef40349f7d38b5d27d7")

        self.assertEquals(change.get("project"), project)
        self.assertEquals(change.get("codebase"), codebase)

    # Test 'base' hook with attributes. We should get a json string representing
    # a Change object as a dictionary. All values show be set.
    @defer.inlineCallbacks
    def testGitWithChange(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.uri = "/change_hook/gitlab"
        self.request.method = "POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes(res)

    @defer.inlineCallbacks
    def testGitWithChange_WithProjectToo(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.uri = "/change_hook/gitlab"
        self.request.args = {'project': ['MyProject']}
        self.request.method = "POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes(res, project="MyProject")

    @defer.inlineCallbacks
    def testGitWithChange_WithCodebaseToo(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.uri = "/change_hook/gitlab"
        self.request.args = {'codebase': ['MyCodebase']}
        self.request.method = "POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes(res, codebase="MyCodebase")

    def testGitWithNoJson(self):
        self.request = FakeRequest()
        self.request.uri = "/change_hook/gitlab"
        self.request.method = "POST"
        d = self.request.test_render(self.changeHook)

        def check_changes(r):
            self.assertEquals(len(self.changeHook.master.addedChanges), 0)
            self.assertIn("Error loading JSON:", self.request.written)
            self.request.setResponseCode.assert_called_with(400, mock.ANY)

        d.addCallback(check_changes)
        return d
