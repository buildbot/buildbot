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
# Copyright Manba Team

import calendar

from twisted.internet.defer import inlineCallbacks
from twisted.trial import unittest

import buildbot.status.web.change_hook as change_hook

from buildbot.test.fake.web import FakeRequest
from buildbot.test.util import compat


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


class TestChangeHookConfiguredWithBitbucketChange(unittest.TestCase):

    """Unit tests for BitBucket Change Hook
    """

    def setUp(self):
        self.change_hook = change_hook.ChangeHookResource(
            dialects={'bitbucket': True})

    @inlineCallbacks
    def testGitWithChange(self):
        change_dict = {'payload': [gitJsonPayload]}

        request = FakeRequest(change_dict)
        request.uri = '/change_hook/bitbucket'
        request.method = 'POST'

        yield request.test_render(self.change_hook)

        self.assertEqual(len(request.addedChanges), 1)
        commit = request.addedChanges[0]

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
        change_dict = {'payload': [gitJsonNoCommitsPayload]}

        request = FakeRequest(change_dict)
        request.uri = '/change_hook/bitbucket'
        request.method = 'POST'

        yield request.test_render(self.change_hook)

        self.assertEqual(len(request.addedChanges), 0)
        self.assertEqual(request.written, 'no changes found')

    @inlineCallbacks
    def testMercurialWithChange(self):
        change_dict = {'payload': [mercurialJsonPayload]}

        request = FakeRequest(change_dict)
        request.uri = '/change_hook/bitbucket'
        request.method = 'POST'

        yield request.test_render(self.change_hook)

        self.assertEqual(len(request.addedChanges), 1)
        commit = request.addedChanges[0]

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
        change_dict = {'payload': [mercurialJsonNoCommitsPayload]}

        request = FakeRequest(change_dict)
        request.uri = '/change_hook/bitbucket'
        request.method = 'POST'

        yield request.test_render(self.change_hook)

        self.assertEqual(len(request.addedChanges), 0)
        self.assertEqual(request.written, 'no changes found')

    @inlineCallbacks
    @compat.usesFlushLoggedErrors
    def testWithNoJson(self):
        request = FakeRequest()
        request.uri = '/change_hook/bitbucket'
        request.method = 'POST'

        yield request.test_render(self.change_hook)
        self.assertEqual(len(request.addedChanges), 0)
        self.assertEqual(request.written, 'Error processing changes.')
        request.setResponseCode.assert_called_with(
            500, 'Error processing changes.')
        self.assertEqual(len(self.flushLoggedErrors()), 1)

    @inlineCallbacks
    def testGitWithChangeAndProject(self):
        change_dict = {
            'payload': [gitJsonPayload],
            'project': ['project-name']}

        request = FakeRequest(change_dict)
        request.uri = '/change_hook/bitbucket'
        request.method = 'POST'

        yield request.test_render(self.change_hook)

        self.assertEqual(len(request.addedChanges), 1)
        commit = request.addedChanges[0]

        self.assertEqual(commit['project'], 'project-name')
