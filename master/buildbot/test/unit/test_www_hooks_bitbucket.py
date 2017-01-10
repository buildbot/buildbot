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
# Copyright Mamba Team
import calendar
import os
from StringIO import StringIO

from dateutil.parser import parse as dateparse

from twisted.internet.defer import inlineCallbacks
from twisted.python import util
from twisted.trial import unittest

import buildbot.www.change_hook as change_hook
from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.www.hooks.bitbucket import _HEADER_CT
from buildbot.www.hooks.bitbucket import _HEADER_EVENT


def get_fixture(filename):
    with open(util.sibpath(__file__, os.path.join("fixtures", filename))) as f:
        return f.read()


_CT_ENCODED = 'application/x-www-form-urlencoded'
_CT_JSON = 'application/json'


gitJsonPayload = """{
    "canon_url": "https://bitbucket.org",
    "commits": [
        {
            "author": "marcus",
            "branch": "master",
            "files": [
                {
                    "file": "somefile.py",
                    "type": "modified"
                }
            ],
            "message": "Added some more things to somefile.py",
            "node": "620ade18607a",
            "parents": [
                "702c70160afc"
            ],
            "raw_author": "Marcus Bertrand <marcus@somedomain.com>",
            "raw_node": "620ade18607ac42d872b568bb92acaa9a28620e9",
            "revision": null,
            "size": -1,
            "timestamp": "2012-05-30 05:58:56",
            "utctimestamp": "2012-05-30 03:58:56+00:00"
        }
    ],
    "repository": {
        "absolute_url": "/marcus/project-x/",
        "fork": false,
        "is_private": true,
        "name": "Project X",
        "owner": "marcus",
        "scm": "git",
        "slug": "project-x",
        "website": "https://atlassian.com/"
    },
    "user": "marcus"
}"""

mercurialJsonPayload = """{
    "canon_url": "https://bitbucket.org",
    "commits": [
        {
            "author": "marcus",
            "branch": "master",
            "files": [
                {
                    "file": "somefile.py",
                    "type": "modified"
                }
            ],
            "message": "Added some more things to somefile.py",
            "node": "620ade18607a",
            "parents": [
                "702c70160afc"
            ],
            "raw_author": "Marcus Bertrand <marcus@somedomain.com>",
            "raw_node": "620ade18607ac42d872b568bb92acaa9a28620e9",
            "revision": null,
            "size": -1,
            "timestamp": "2012-05-30 05:58:56",
            "utctimestamp": "2012-05-30 03:58:56+00:00"
        }
    ],
    "repository": {
        "absolute_url": "/marcus/project-x/",
        "fork": false,
        "is_private": true,
        "name": "Project X",
        "owner": "marcus",
        "scm": "hg",
        "slug": "project-x",
        "website": "https://atlassian.com/"
    },
    "user": "marcus"
}"""

gitJsonNoCommitsPayload = """{
    "canon_url": "https://bitbucket.org",
    "commits": [
    ],
    "repository": {
        "absolute_url": "/marcus/project-x/",
        "fork": false,
        "is_private": true,
        "name": "Project X",
        "owner": "marcus",
        "scm": "git",
        "slug": "project-x",
        "website": "https://atlassian.com/"
    },
    "user": "marcus"
}"""

mercurialJsonNoCommitsPayload = """{
    "canon_url": "https://bitbucket.org",
    "commits": [
    ],
    "repository": {
        "absolute_url": "/marcus/project-x/",
        "fork": false,
        "is_private": true,
        "name": "Project X",
        "owner": "marcus",
        "scm": "hg",
        "slug": "project-x",
        "website": "https://atlassian.com/"
    },
    "user": "marcus"
}"""


# Bitbucket POST service sends content header as 'application/x-www-form-urlencoded':
# https://confluence.atlassian.com/bitbucket/post-service-management-223216518.html
#
# POST service is deprecated and replaced by Bitbucket webook events
def _prepare_request(payload, headers=None, change_dict=None):
    headers = {} if headers is None else headers
    request = FakeRequest(change_dict)
    request.uri = "/change_hook/bitbucket"
    request.method = "POST"

    if isinstance(payload, str):
        request.content = StringIO(payload)
        request.received_headers[_HEADER_CT] = _CT_JSON
    else:
        request.args['payload'] = payload
        request.received_headers[_HEADER_CT] = _CT_ENCODED

    request.received_headers.update(headers)
    return request


class TestChangeHookConfiguredWithBitbucketChange(unittest.TestCase):

    """Unit tests for BitBucket Change Hook
    """

    def setUp(self):
        self.change_hook = change_hook.ChangeHookResource(
            dialects={'bitbucket': True}, master=fakeMasterForHooks())

    @inlineCallbacks
    def testGitWithChange(self):
        request = _prepare_request([gitJsonPayload])

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['files'], ['somefile.py'])
        self.assertEqual(
            commit['repository'], 'https://bitbucket.org/marcus/project-x/')
        self.assertEqual(
            calendar.timegm(commit['when_timestamp'].utctimetuple()),
            1338350336
        )
        self.assertEqual(
            commit['author'], 'Marcus Bertrand <marcus@somedomain.com>')
        self.assertEqual(
            commit['revision'], '620ade18607ac42d872b568bb92acaa9a28620e9')
        self.assertEqual(
            commit['comments'], 'Added some more things to somefile.py')
        self.assertEqual(commit['branch'], 'master')
        self.assertEqual(
            commit['revlink'],
            'https://bitbucket.org/marcus/project-x/commits/'
            '620ade18607ac42d872b568bb92acaa9a28620e9'
        )

    @inlineCallbacks
    def testGitWithNoCommitsPayload(self):
        request = _prepare_request([gitJsonNoCommitsPayload])

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 0)
        self.assertEqual(request.written, 'no changes found')

    @inlineCallbacks
    def testMercurialWithChange(self):
        request = _prepare_request([mercurialJsonPayload])

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['files'], ['somefile.py'])
        self.assertEqual(
            commit['repository'], 'https://bitbucket.org/marcus/project-x/')
        self.assertEqual(
            calendar.timegm(commit['when_timestamp'].utctimetuple()),
            1338350336
        )
        self.assertEqual(
            commit['author'], 'Marcus Bertrand <marcus@somedomain.com>')
        self.assertEqual(
            commit['revision'], '620ade18607ac42d872b568bb92acaa9a28620e9')
        self.assertEqual(
            commit['comments'], 'Added some more things to somefile.py')
        self.assertEqual(commit['branch'], 'master')
        self.assertEqual(
            commit['revlink'],
            'https://bitbucket.org/marcus/project-x/commits/'
            '620ade18607ac42d872b568bb92acaa9a28620e9'
        )

    @inlineCallbacks
    def testMercurialWithNoCommitsPayload(self):
        request = _prepare_request([mercurialJsonNoCommitsPayload])

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 0)
        self.assertEqual(request.written, 'no changes found')

    @inlineCallbacks
    def testWithNoJson(self):
        request = _prepare_request([])

        yield request.test_render(self.change_hook)
        self.assertEqual(len(self.change_hook.master.addedChanges), 0)
        self.assertEqual(request.written, 'Error processing changes.')
        request.setResponseCode.assert_called_with(
            500, 'Error processing changes.')
        self.assertEqual(len(self.flushLoggedErrors()), 1)

    @inlineCallbacks
    def testGitWithChangeAndProject(self):
        change_dict = {'project': ['project-name']}
        request = _prepare_request([gitJsonPayload], change_dict=change_dict)

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['project'], 'project-name')


class TestWebHookEvent(unittest.TestCase):

    """Unit tests for BitBucket webhook event
    """

    def setUp(self):
        self.change_hook = change_hook.ChangeHookResource(
            dialects={'bitbucket': True}, master=fakeMasterForHooks())

    @inlineCallbacks
    def testGitRepoPush(self):
        gitRepoPushJsonPayload = get_fixture("www_hooks_bitbucket_git_repo_push_payload.json")
        request = _prepare_request(gitRepoPushJsonPayload, headers={_HEADER_EVENT: "repo:push"})
        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['repository'], 'git@bitbucket.org:team_name/repo_name.git')
        self.assertEqual(commit['project'], 'repo_name')
        self.assertEqual(commit['when_timestamp'], dateparse("2015-06-09T03:34:49+00:00"))
        self.assertEqual(commit['author'], 'Emma <emmap1>')
        self.assertEqual(commit['revision'], '03f4a7270240708834de475bcf21532d6134777e')
        self.assertEqual(commit['comments'], 'commit message')
        self.assertEqual(commit['branch'], 'master')
        self.assertEqual(
            commit['revlink'],
            'https://bitbucket.org/user/repo/commits/03f4a7270240708834de475bcf21532d6134777e'
        )

    @inlineCallbacks
    def testGitPullRequestCreated(self):
        gitRepoPullRequestCreatedJsonPayload = get_fixture("www_hooks_bitbucket_git_repo_pull_request_created_payload.json")
        request = _prepare_request(gitRepoPullRequestCreatedJsonPayload, headers={_HEADER_EVENT: "pullrequest:created"})
        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['repository'], 'git@bitbucket.org:team_name/repo_name.git')
        self.assertEqual(commit['project'], 'repo_name')
        self.assertEqual(commit['when_timestamp'], dateparse("2016-12-06T15:34:56.496384+00:00"))
        self.assertEqual(commit['author'], 'Emma <emmap1>')
        self.assertEqual(commit['revision'], 'af319f4c0f50')
        self.assertEqual(commit['comments'], 'Bitbucket Pull Request #2')
        self.assertEqual(commit['branch'], 'refs/pull/2/merge')
        self.assertEqual(
            commit['revlink'],
            'https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/commits'
        )

    @inlineCallbacks
    def testGitPullRequestUpdated(self):
        gitRepoPullRequestUpdatedJsonPayload = get_fixture("www_hooks_bitbucket_git_repo_pull_request_updated_payload.json")
        request = _prepare_request(gitRepoPullRequestUpdatedJsonPayload, headers={_HEADER_EVENT: "pullrequest:updated"})
        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['repository'], 'git@bitbucket.org:team_name/repo_name.git')
        self.assertEqual(commit['project'], 'Project name')
        self.assertEqual(commit['when_timestamp'], dateparse("2016-12-06T16:51:28.027419+00:00"))
        self.assertEqual(commit['author'], 'Emma <emmap1>')
        self.assertEqual(commit['revision'], 'df98dc8f0f53')
        self.assertEqual(commit['comments'], 'Bitbucket Pull Request #2')
        self.assertEqual(commit['branch'], 'refs/pull/2/merge')
        self.assertEqual(
            commit['revlink'],
            'https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/commits'
        )
