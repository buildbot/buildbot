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

import json

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes.github import GitHubPullrequestPoller
from buildbot.config import ConfigErrors
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util import changesource

gitJsonPayloadSinglePullrequest = """
{
  "html_url": "https://github.com/buildbot/buildbot/pull/4242",
  "number": 4242,
  "state": "open",
  "locked": false,
  "title": "Update the README with new information",
  "user": {
    "login": "defunkt"
  },
  "body": "This is a pretty simple change that we need to pull into master.",
  "updated_at": "2017-01-25T22:36:21Z",
  "head": {
    "ref": "defunkt/change",
    "sha": "4c9a7f03e04e551a5e012064b581577f949dd3a4",
    "repo": {
      "name": "buildbot",
      "full_name": "defunkt/buildbot",
      "fork": true,
      "private": false,
      "git_url": "git://github.com/defunkt/buildbot.git",
      "ssh_url": "git@github.com:defunkt/buildbot.git",
      "clone_url": "https://github.com/defunkt/buildbot.git",
      "svn_url": "https://github.com/defunkt/buildbot"
    }
  },
  "base": {
    "ref": "master",
    "sha": "4c9a7f03e04e551a5e012064b581577f949dd3a4",
    "name": "buildbot",
    "repo": {
      "full_name": "buildbot/buildbot",
      "fork": false,
      "private": false,
      "git_url": "git://github.com/buildbot/buildbot.git",
      "ssh_url": "git@github.com:buildbot/buildbot.git",
      "clone_url": "https://github.com/buildbot/buildbot.git",
      "svn_url": "https://github.com/buildbot/buildbot"
    }
  },
  "merged": false,
  "commits": 42,
  "mergeable": true,
  "mergeable_state": "clean",
  "merged_by": null
}
"""

gitJsonPayloadPullRequests = """
[
  {
    "html_url": "https://github.com/buildbot/buildbot/pull/4242",
    "number": 4242,
    "locked": false,
    "title": "Update the README with new information",
    "user": {
      "login": "defunkt"
    },
    "body": "This is a pretty simple change that we need to pull into master.",
    "updated_at": "2017-01-25T22:36:21Z",
    "head": {
      "ref": "defunkt/change",
      "sha": "4c9a7f03e04e551a5e012064b581577f949dd3a4",
      "repo": {
        "name": "buildbot",
        "git_url": "git://github.com/defunkt/buildbot.git",
        "ssh_url": "git@github.com:defunkt/buildbot.git",
        "clone_url": "https://github.com/defunkt/buildbot.git",
        "svn_url": "https://github.com/defunkt/buildbot"
      }
    },
    "base": {
      "ref": "master",
      "name": "buildbot",
      "repo": {
        "git_url": "git://github.com/buildbot/buildbot.git",
        "ssh_url": "git@github.com:buildbot/buildbot.git",
        "clone_url": "https://github.com/buildbot/buildbot.git",
        "svn_url": "https://github.com/buildbot/buildbot"
      }
    }
  }
]
"""

gitJsonPayloadFiles = """
[
  {
    "filename": "README.md"
  }
]
"""

gitJsonUserPage = """
{
  "login": "defunkt",
  "email": "defunkt@defunkt.null"
}
"""

gitJsonUserPage_missingEmail = """
{
  "login": "defunkt",
  "email": null
}"""


_CT_ENCODED = 'application/x-www-form-urlencoded'
_CT_JSON = 'application/json'

_GH_PARSED_PROPS = {
    'github.head.sha': '4c9a7f03e04e551a5e012064b581577f949dd3a4',
    'github.state': 'open',
    'github.number': 4242,
    'github.merged': False,
    'github.base.repo.full_name': 'buildbot/buildbot',
    'github.base.ref': 'master',
    'github.base.sha': '4c9a7f03e04e551a5e012064b581577f949dd3a4',
    'github.head.repo.full_name': u'defunkt/buildbot',
    'github.mergeable_state': 'clean',
    'github.mergeable': True,
    'github.head.ref': 'defunkt/change',
    'github.title': 'Update the README with new information',
    'github.merged_by': None
}


class TestGitHubPullrequestPoller(changesource.ChangeSourceMixin,
                                  unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpChangeSource()
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()
        yield self.tearDownChangeSource()

    @defer.inlineCallbacks
    def newChangeSource(self,
                        owner,
                        repo,
                        endpoint='https://api.github.com',
                        **kwargs):
        http_headers = {'User-Agent': 'Buildbot'}
        token = kwargs.get('token', None)
        if token:
            http_headers.update({'Authorization': 'token ' + token})
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, endpoint, headers=http_headers)
        self.changesource = GitHubPullrequestPoller(owner, repo, **kwargs)

    @defer.inlineCallbacks
    def startChangeSource(self):
        yield self.changesource.setServiceParent(self.master)
        yield self.attachChangeSource(self.changesource)

    def assertDictSubset(self, expected_dict, response_dict):
        expected = {}
        for key in expected_dict.keys():
            self.assertIn(key, set(response_dict.keys()))
            expected[key] = response_dict[key]
        self.assertDictEqual(expected_dict, expected)

    @defer.inlineCallbacks
    def test_describe(self):
        yield self.newChangeSource('defunkt', 'defunkt')
        yield self.startChangeSource()
        self.assertEqual(
            "GitHubPullrequestPoller watching the GitHub repository {}/{}".
            format('defunkt', 'defunkt'), self.changesource.describe())

    @defer.inlineCallbacks
    def test_default_name(self):
        yield self.newChangeSource('defunkt', 'defunkt')
        yield self.startChangeSource()
        self.assertEqual("GitHubPullrequestPoller:{}/{}".format(
            'defunkt', 'defunkt'), self.changesource.name)

    @defer.inlineCallbacks
    def test_custom_name(self):
        yield self.newChangeSource('defunkt', 'defunkt', name="MyName")
        yield self.startChangeSource()
        self.assertEqual("MyName", self.changesource.name)

    @defer.inlineCallbacks
    def test_SimplePR(self):
        yield self.newChangeSource(
            'defunkt', 'defunkt', token='1234', github_property_whitelist=["github.*"])
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads(gitJsonPayloadFiles))
        self._http.expect(
            method='get',
            ep='/users/defunkt',
            content_json=json.loads(gitJsonUserPage))
        yield self.startChangeSource()
        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['author'], 'defunkt <defunkt@defunkt.null>')
        self.assertEqual(change['revision'],
                         '4c9a7f03e04e551a5e012064b581577f949dd3a4')
        self.assertEqual(change['revlink'],
                         'https://github.com/buildbot/buildbot/pull/4242')
        self.assertEqual(change['branch'], 'defunkt/change')
        self.assertEqual(change['repository'],
                         'https://github.com/defunkt/buildbot.git')
        self.assertEqual(change['files'], ['README.md'])

        self.assertDictSubset(_GH_PARSED_PROPS, change['properties'])
        self.assertEqual(change["comments"],
                         "GitHub Pull Request #4242 (42 commits)\n"
                         "Update the README with new information\n"
                         "This is a pretty simple change that we need to pull into master.")

    @defer.inlineCallbacks
    def test_wrongBranch(self):
        yield self.newChangeSource(
            'defunkt', 'defunkt', token='1234', branches=['wrongBranch'])
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests))

        yield self.startChangeSource()
        yield self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_baseURL(self):
        yield self.newChangeSource(
            'defunkt',
            'defunkt',
            endpoint='https://my.other.endpoint',
            token='1234',
            baseURL='https://my.other.endpoint/',
            github_property_whitelist=["github.*"])
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads(gitJsonPayloadFiles))
        self._http.expect(
            method='get',
            ep='/users/defunkt',
            content_json=json.loads(gitJsonUserPage))
        yield self.startChangeSource()
        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['author'], 'defunkt <defunkt@defunkt.null>')
        self.assertEqual(change['revision'],
                         '4c9a7f03e04e551a5e012064b581577f949dd3a4')
        self.assertEqual(change['revlink'],
                         'https://github.com/buildbot/buildbot/pull/4242')
        self.assertEqual(change['branch'], 'defunkt/change')
        self.assertEqual(change['repository'],
                         'https://github.com/defunkt/buildbot.git')
        self.assertEqual(change['files'], ['README.md'])
        self.assertDictSubset(_GH_PARSED_PROPS, change['properties'])
        self.assertEqual(change["comments"],
                         "GitHub Pull Request #4242 (42 commits)\n"
                         "Update the README with new information\n"
                         "This is a pretty simple change that we need to pull into master.")

    @defer.inlineCallbacks
    def test_PRfilter(self):
        yield self.newChangeSource(
            'defunkt',
            'defunkt',
            token='1234',
            pullrequest_filter=lambda pr: True if pr['number'] == 1337 else False
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests))
        yield self.startChangeSource()
        yield self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_failFiles(self):
        yield self.newChangeSource('defunkt', 'defunkt', token='1234')
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads("[{}]"))
        yield self.startChangeSource()
        d = self.changesource.poll()
        self.assertFailure(d, KeyError)

    @defer.inlineCallbacks
    def test_wrongRepoLink(self):
        yield self.assertFailure(
            self.newChangeSource(
                'defunkt', 'defunkt', token='1234', repository_type='defunkt'),
            ConfigErrors)

    @defer.inlineCallbacks
    def test_magicLink(self):
        yield self.newChangeSource(
            'defunkt', 'defunkt', magic_link=True,
            token='1234', github_property_whitelist=["github.*"])
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads(gitJsonPayloadFiles))
        self._http.expect(
            method='get',
            ep='/users/defunkt',
            content_json=json.loads(gitJsonUserPage))
        yield self.startChangeSource()
        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['author'], 'defunkt <defunkt@defunkt.null>')
        self.assertEqual(change['revision'],
                         '4c9a7f03e04e551a5e012064b581577f949dd3a4')
        self.assertEqual(change['revlink'],
                         'https://github.com/buildbot/buildbot/pull/4242')
        self.assertEqual(change['branch'], 'refs/pull/4242/merge')
        self.assertEqual(change['repository'],
                         'https://github.com/buildbot/buildbot.git')
        self.assertEqual(change['files'], ['README.md'])
        self.assertDictSubset(_GH_PARSED_PROPS, change['properties'])
        self.assertEqual(change["comments"],
                         "GitHub Pull Request #4242 (42 commits)\n"
                         "Update the README with new information\n"
                         "This is a pretty simple change that we need to pull into master.")

    @defer.inlineCallbacks
    def test_AuthormissingEmail(self):
        yield self.newChangeSource(
            'defunkt', 'defunkt', token='1234', github_property_whitelist=["github.*"])
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest))
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads(gitJsonPayloadFiles))
        self._http.expect(
            method='get',
            ep='/users/defunkt',
            content_json=json.loads(gitJsonUserPage_missingEmail))
        yield self.startChangeSource()
        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['author'], 'defunkt')
        self.assertEqual(change['revision'],
                         '4c9a7f03e04e551a5e012064b581577f949dd3a4')
        self.assertEqual(change['revlink'],
                         'https://github.com/buildbot/buildbot/pull/4242')
        self.assertEqual(change['branch'], 'defunkt/change')
        self.assertEqual(change['repository'],
                         'https://github.com/defunkt/buildbot.git')
        self.assertEqual(change['files'], ['README.md'])
        self.assertDictSubset(_GH_PARSED_PROPS, change['properties'])
        self.assertEqual(change["comments"],
                         "GitHub Pull Request #4242 (42 commits)\n"
                         "Update the README with new information\n"
                         "This is a pretty simple change that we need to pull into master.")
