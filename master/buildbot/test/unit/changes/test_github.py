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

import json

from twisted.trial import unittest

from buildbot.changes.github import GitHubPullrequestPoller
from buildbot.config import ConfigErrors
from buildbot.process.properties import Properties
from buildbot.process.properties import Secret
from buildbot.secrets.manager import SecretManager
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.reactor import TestReactorMixin
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

gitJsonPayloadAuthors = """
[
  {
    "commit": {
      "author": {
        "name": "defunkt",
        "email": "defunkt@defunkt.null"
      }
    }
  }
]
"""

gitJsonPayloadCommitters = """
[
  {
    "commit": {
      "committer": {
        "name": "defunktc",
        "email": "defunktc@defunkt.null"
      }
    }
  }
]
"""

git_json_not_found = """
{
  "message": "Not Found",
  "documentation_url": "https://docs.github.com/rest/reference/pulls#list-pull-requests"
}
"""

_CT_ENCODED = b'application/x-www-form-urlencoded'
_CT_JSON = b'application/json'

_GH_PARSED_PROPS = {
    'pullrequesturl': 'https://github.com/buildbot/buildbot/pull/4242',
    'github.head.sha': '4c9a7f03e04e551a5e012064b581577f949dd3a4',
    'github.state': 'open',
    'github.number': 4242,
    'github.merged': False,
    'github.base.repo.full_name': 'buildbot/buildbot',
    'github.base.ref': 'master',
    'github.base.sha': '4c9a7f03e04e551a5e012064b581577f949dd3a4',
    'github.head.repo.full_name': 'defunkt/buildbot',
    'github.mergeable_state': 'clean',
    'github.mergeable': True,
    'github.head.ref': 'defunkt/change',
    'github.title': 'Update the README with new information',
    'github.merged_by': None,
}


class TestGitHubPullrequestPoller(
    changesource.ChangeSourceMixin, TestReactorMixin, unittest.TestCase
):
    async def setUp(self):
        self.setup_test_reactor()
        await self.setUpChangeSource()

        fake_storage_service = FakeSecretStorage()

        secret_service = SecretManager()
        secret_service.services = [fake_storage_service]
        await secret_service.setServiceParent(self.master)

        await self.master.startService()

        fake_storage_service.reconfigService(secretdict={"token": "1234"})

    async def tearDown(self):
        await self.master.stopService()
        await self.tearDownChangeSource()

    async def newChangeSource(self, owner, repo, endpoint='https://api.github.com', **kwargs):
        http_headers = {'User-Agent': 'Buildbot'}
        token = kwargs.get('token', None)
        if token:
            p = Properties()
            p.master = self.master
            token = await p.render(token)
            http_headers.update({'Authorization': 'token ' + token})
        self._http = await fakehttpclientservice.HTTPClientService.getService(
            self.master, self, endpoint, headers=http_headers
        )
        self.changesource = GitHubPullrequestPoller(owner, repo, **kwargs)

    async def startChangeSource(self):
        await self.changesource.setServiceParent(self.master)
        await self.attachChangeSource(self.changesource)

    def assertDictSubset(self, expected_dict, response_dict):
        expected = {}
        for key in expected_dict.keys():
            self.assertIn(key, set(response_dict.keys()))
            expected[key] = response_dict[key]
        self.assertDictEqual(expected_dict, expected)

    async def test_describe(self):
        await self.newChangeSource('defunkt', 'defunkt')
        await self.startChangeSource()
        self.assertEqual(
            f"GitHubPullrequestPoller watching the GitHub repository {'defunkt'}/{'defunkt'}",
            self.changesource.describe(),
        )

    async def test_default_name(self):
        await self.newChangeSource('defunkt', 'defunkt')
        await self.startChangeSource()
        self.assertEqual(f"GitHubPullrequestPoller:{'defunkt'}/{'defunkt'}", self.changesource.name)

    async def test_custom_name(self):
        await self.newChangeSource('defunkt', 'defunkt', name="MyName")
        await self.startChangeSource()
        self.assertEqual("MyName", self.changesource.name)

    async def test_SimplePR(self):
        await self.newChangeSource(
            'defunkt', 'defunkt', token='1234', github_property_whitelist=["github.*"]
        )
        await self.simple_pr()

    async def test_project(self):
        await self.newChangeSource(
            'defunkt',
            'defunkt',
            token='1234',
            project='tst_project',
            github_property_whitelist=["github.*"],
        )
        await self.simple_pr(project='tst_project')

    async def test_secret_token(self):
        await self.newChangeSource(
            'defunkt', 'defunkt', token=Secret('token'), github_property_whitelist=["github.*"]
        )
        await self.simple_pr()

    async def simple_pr(self, project=None):
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads(gitJsonPayloadAuthors),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads(gitJsonPayloadCommitters),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads(gitJsonPayloadFiles),
        )
        await self.startChangeSource()
        await self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['author'], 'defunkt <defunkt@defunkt.null>')
        self.assertEqual(change['revision'], '4c9a7f03e04e551a5e012064b581577f949dd3a4')
        self.assertEqual(change['revlink'], 'https://github.com/buildbot/buildbot/pull/4242')
        self.assertEqual(change['branch'], 'defunkt/change')
        self.assertEqual(change['repository'], 'https://github.com/defunkt/buildbot.git')
        self.assertEqual(change['files'], ['README.md'])
        self.assertEqual(change['committer'], 'defunktc <defunktc@defunkt.null>')
        self.assertEqual(change['project'], project if project is not None else 'buildbot/buildbot')

        self.assertDictSubset(_GH_PARSED_PROPS, change['properties'])
        self.assertEqual(
            change["comments"],
            "GitHub Pull Request #4242 (42 commits)\n"
            "Update the README with new information\n"
            "This is a pretty simple change that we need to pull into master.",
        )

    async def test_wrongBranch(self):
        await self.newChangeSource('defunkt', 'defunkt', token='1234', branches=['wrongBranch'])
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests),
        )

        await self.startChangeSource()
        await self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    async def test_http_error(self):
        await self.newChangeSource('defunkt', 'defunkt', token='1234')
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(git_json_not_found),
            code=404,
        )
        await self.startChangeSource()
        await self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    async def test_baseURL(self):
        await self.newChangeSource(
            'defunkt',
            'defunkt',
            endpoint='https://my.other.endpoint',
            token='1234',
            baseURL='https://my.other.endpoint/',
            github_property_whitelist=["github.*"],
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads(gitJsonPayloadAuthors),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads(gitJsonPayloadCommitters),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads(gitJsonPayloadFiles),
        )
        await self.startChangeSource()
        await self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['author'], 'defunkt <defunkt@defunkt.null>')
        self.assertEqual(change['revision'], '4c9a7f03e04e551a5e012064b581577f949dd3a4')
        self.assertEqual(change['revlink'], 'https://github.com/buildbot/buildbot/pull/4242')
        self.assertEqual(change['branch'], 'defunkt/change')
        self.assertEqual(change['repository'], 'https://github.com/defunkt/buildbot.git')
        self.assertEqual(change['files'], ['README.md'])
        self.assertEqual(change['committer'], 'defunktc <defunktc@defunkt.null>')
        self.assertDictSubset(_GH_PARSED_PROPS, change['properties'])
        self.assertEqual(
            change["comments"],
            "GitHub Pull Request #4242 (42 commits)\n"
            "Update the README with new information\n"
            "This is a pretty simple change that we need to pull into master.",
        )

    async def test_PRfilter(self):
        await self.newChangeSource(
            'defunkt', 'defunkt', token='1234', pullrequest_filter=lambda pr: pr['number'] == 1337
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests),
        )
        await self.startChangeSource()
        await self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    async def test_failCommitters(self):
        await self.newChangeSource('defunkt', 'defunkt', token='1234')
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads("[{}]"),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads("[{}]"),
        )
        await self.startChangeSource()
        await self.assertFailure(self.changesource.poll(), KeyError)

    async def test_failFiles(self):
        await self.newChangeSource('defunkt', 'defunkt', token='1234')
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads("[{}]"),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads("[{}]"),
        )
        await self.startChangeSource()
        await self.assertFailure(self.changesource.poll(), KeyError)

    async def test_wrongRepoLink(self):
        with self.assertRaises(ConfigErrors):
            await self.newChangeSource(
                'defunkt', 'defunkt', token='1234', repository_type='defunkt'
            )

    async def test_magicLink(self):
        await self.newChangeSource(
            'defunkt',
            'defunkt',
            magic_link=True,
            token='1234',
            github_property_whitelist=["github.*"],
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads(gitJsonPayloadAuthors),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads(gitJsonPayloadCommitters),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads(gitJsonPayloadFiles),
        )
        await self.startChangeSource()
        await self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['author'], 'defunkt <defunkt@defunkt.null>')
        self.assertEqual(change['revision'], '4c9a7f03e04e551a5e012064b581577f949dd3a4')
        self.assertEqual(change['revlink'], 'https://github.com/buildbot/buildbot/pull/4242')
        self.assertEqual(change['branch'], 'refs/pull/4242/merge')
        self.assertEqual(change['repository'], 'https://github.com/buildbot/buildbot.git')
        self.assertEqual(change['files'], ['README.md'])
        self.assertEqual(change['committer'], 'defunktc <defunktc@defunkt.null>')
        self.assertDictSubset(_GH_PARSED_PROPS, change['properties'])
        self.assertEqual(
            change["comments"],
            "GitHub Pull Request #4242 (42 commits)\n"
            "Update the README with new information\n"
            "This is a pretty simple change that we need to pull into master.",
        )

    async def test_AuthormissingEmail(self):
        await self.newChangeSource(
            'defunkt', 'defunkt', token='1234', github_property_whitelist=["github.*"]
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls',
            content_json=json.loads(gitJsonPayloadPullRequests),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242',
            content_json=json.loads(gitJsonPayloadSinglePullrequest),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads(gitJsonPayloadAuthors),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/commits',
            content_json=json.loads(gitJsonPayloadCommitters),
        )
        self._http.expect(
            method='get',
            ep='/repos/defunkt/defunkt/pulls/4242/files',
            content_json=json.loads(gitJsonPayloadFiles),
        )
        await self.startChangeSource()
        await self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['author'], 'defunkt <defunkt@defunkt.null>')
        self.assertEqual(change['revision'], '4c9a7f03e04e551a5e012064b581577f949dd3a4')
        self.assertEqual(change['revlink'], 'https://github.com/buildbot/buildbot/pull/4242')
        self.assertEqual(change['branch'], 'defunkt/change')
        self.assertEqual(change['repository'], 'https://github.com/defunkt/buildbot.git')
        self.assertEqual(change['files'], ['README.md'])
        self.assertEqual(change['committer'], 'defunktc <defunktc@defunkt.null>')
        self.assertDictSubset(_GH_PARSED_PROPS, change['properties'])
        self.assertEqual(
            change["comments"],
            "GitHub Pull Request #4242 (42 commits)\n"
            "Update the README with new information\n"
            "This is a pretty simple change that we need to pull into master.",
        )
