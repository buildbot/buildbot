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
"""
Unit tests for GitHubStatus plugin.
"""
from __future__ import absolute_import

from mock import Mock
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.status.builder import SUCCESS, FAILURE
from buildbot.status.github import GitHubStatus
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.fake.sourcestamp import FakeSourceStamp


class TestGitHubStatus(unittest.TestCase):
    """
    Unit tests for `GitHubStatus`.
    """

    def setUp(self):
        super(TestGitHubStatus, self).setUp()
        self.build = FakeBuild()
        self.props = self.build.build_status.properties
        self.sourcestamp = FakeSourceStamp()
        self.status = GitHubStatus(
            token='token', repoOwner='owner', repoName='name')

    def test_initialization_required_arguments(self):
        """
        Status can be initialized by only specifying GitHub API token
        and interpolation for repository's owner and name.

        All other arguments are initialized with default values.
        """
        token = 'GitHub-API-Token'
        repoOwner = Interpolate('owner')
        repoName = Interpolate('name')
        status = GitHubStatus(
            token=token, repoOwner=repoOwner, repoName=repoName)

        self.assertEqual(token, status._token)
        self.assertEqual(repoOwner, status._repoOwner)
        self.assertEqual(repoName, status._repoName)

        # Check default values.
        self.assertEqual(status._sha, Interpolate("%(src::revision)s"))
        self.assertEqual(
            status._startDescription, Interpolate("Build started."))
        self.assertEqual(
            status._endDescription, Interpolate("Build done."))

    def test_startService(self):
        """
        When started, it will set parent as '_status' and subscribe to parent.
        """
        self.status.parent = Mock()

        self.status.startService()

        self.status._status.subscribe.assert_called_with(self.status)

    def test_builderAdded(self):
        """
        Status is attached to every builder.
        """
        result = self.status.builderAdded('builder-name', None)

        self.assertEqual(self.status, result)

    def test_buildStarted_no_properties(self):
        """
        Status sending for buildStarted is skipped if no GitHub specific
        properties are obtained from _getGitHubRepoProperties.
        """
        self.status._getGitHubRepoProperties = lambda build: {}

        d = self.status.buildStarted('builder-name', None)

        result = []
        d.addCallback(result.append)
        self.assertIsNone(result[0])

    def test_buildStarted_ok(self):
        """
        When _getGitHubRepoProperties return a dict with properties
        for this build, buildStarted will augment with details for
        start state and send a GitHub API request.
        """
        self.status._getGitHubRepoProperties = lambda build: {
            'repoOwner': 'repo-owner',
            'repoName': 'repo-name',
            'sha': '123',
            'targetURL': 'http://domain.tld',
            'buildNumber': '1',
            }
        self.status._sendGitHubStatus = Mock(return_value=defer.succeed(None))
        self.build.getTimes = lambda: (1, None)

        d = self.status.buildStarted('builder-name', self.build)

        result = []
        d.addCallback(result.append)
        self.assertIsNone(result[0])

        self.status._sendGitHubStatus.assert_called_with({
            'repoOwner': 'repo-owner',
            'repoName': 'repo-name',
            'sha': '123',
            'targetURL': 'http://domain.tld',
            'buildNumber': '1',
            # Augmented arguments.
            'state': 'pending',
            'description': 'Build started.',
            'builderName': 'builder-name',
            'startDateTime': '1970-01-01 02:00:01',
            'endDateTime': 'In progress',
            'duration': 'In progress',
            })

    def test_buildFinished_no_properties(self):
        """
        Status sending for buildFinished is skipped if no GitHub specific
        properties are obtained from _getGitHubRepoProperties.
        """
        self.status._getGitHubRepoProperties = lambda build: {}

        d = self.status.buildFinished('builder-name', None, None)

        result = []
        d.addCallback(result.append)
        self.assertIsNone(result[0])

    def test_buildFinished_ok(self):
        """
        When _getGitHubRepoProperties return a dict buildFinished will
        augment it with build result and sent status to GitHub API.
        """
        self.status._getGitHubRepoProperties = lambda build: {
            'repoOwner': 'repo-owner',
            'repoName': 'repo-name',
            'sha': '123',
            'targetURL': 'http://domain.tld',
            'buildNumber': '1',
            }
        self.status._sendGitHubStatus = Mock(return_value=defer.succeed(None))
        self.build.getTimes = lambda: (1, 3)

        d = self.status.buildFinished('builder-name', self.build, SUCCESS)

        result = []
        d.addCallback(result.append)
        self.assertIsNone(result[0])

        self.status._sendGitHubStatus.assert_called_with({
            'repoOwner': 'repo-owner',
            'repoName': 'repo-name',
            'sha': '123',
            'targetURL': 'http://domain.tld',
            'buildNumber': '1',
            # Augmented arguments.
            'state': 'success',
            'description': 'Build done.',
            'builderName': 'builder-name',
            'startDateTime': '1970-01-01 02:00:01',
            'endDateTime': '1970-01-01 02:00:03',
            'duration': '2 seconds',
            })

    def test_timeDeltaToHumanReadable(self):
        """
        It will return a human readable time difference.
        """
        result = self.status._timeDeltaToHumanReadable(1, 1)
        self.assertEqual('super fast', result)

        result = self.status._timeDeltaToHumanReadable(1, 2)
        self.assertEqual('1 seconds', result)

        result = self.status._timeDeltaToHumanReadable(1, 61)
        self.assertEqual('1 minutes', result)

        result = self.status._timeDeltaToHumanReadable(1, 62)
        self.assertEqual('1 minutes, 1 seconds', result)

        result = self.status._timeDeltaToHumanReadable(1, 60 * 60 + 1)
        self.assertEqual('1 hours', result)

        result = self.status._timeDeltaToHumanReadable(1, 60 * 60 + 61)
        self.assertEqual('1 hours, 1 minutes', result)

        result = self.status._timeDeltaToHumanReadable(1, 60 * 60 + 62)
        self.assertEqual('1 hours, 1 minutes, 1 seconds', result)

        result = self.status._timeDeltaToHumanReadable(1, 24 * 60 * 60 + 1)
        self.assertEqual('1 days', result)

    def test_getGitHubRepoProperties_skip_no_sha(self):
        """
        An empty dict is returned when any of the repo name, owner and sha
        interpolation returns an empty string or None.
        """
        self.build._repoOwner = Interpolate('owner')
        self.build._repoName = Interpolate('name')
        self.build._sha = Interpolate('')

        d = self.status._getGitHubRepoProperties(self.build)

        result = []
        d.addCallback(result.append)
        self.assertEqual({}, result[0])

    def test_getGitHubRepoProperties_skip_no_owner(self):
        self.status._repoOwner = Interpolate('')
        self.status._repoName = Interpolate('name')
        self.status._sha = Interpolate('sha')

        d = self.status._getGitHubRepoProperties(self.build)

        result = []
        d.addCallback(result.append)
        self.assertEqual({}, result[0])

    def test_getGitHubRepoProperties_skip_no_name(self):
        self.status._repoOwner = Interpolate('owner')
        self.status._repoName = Interpolate('')
        self.status._sha = Interpolate('sha')

        d = self.status._getGitHubRepoProperties(self.build)

        result = []
        d.addCallback(result.append)
        self.assertEqual({}, result[0])

    def test_getGitHubRepoProperties_ok(self):
        """
        A dictionary with build status properties is returned when
        required properties were rendered.
        """
        self.status._repoOwner = Interpolate('owner')
        self.status._repoName = Interpolate('name')
        self.status._sha = Interpolate('sha')
        self.status._status = Mock()
        self.status._status.getURLForThing = lambda build: 'http://thing'
        self.build.getNumber = lambda: 1
        d = self.status._getGitHubRepoProperties(self.build)

        result = []
        d.addCallback(result.append)
        self.assertEqual({
            'buildNumber': '1',
            'repoName': 'name',
            'repoOwner': 'owner',
            'sha': 'sha',
            'targetURL': 'http://thing',
            },
            result[0])

    def test_getGitHubState(self):
        """
        _getGitHubState will try to translate BuildBot status into GitHub
        status. For unknown values will fallback to 'error'.
        """
        self.assertEqual(
            'success', self.status._getGitHubState(SUCCESS))

        self.assertEqual(
            'failure', self.status._getGitHubState(FAILURE))

        self.assertEqual(
            'error', self.status._getGitHubState('anything-else'))

    def test_sendGitHubStatus(self):
        """
        sendGitHubStatus will call the txgithub createStatus and encode
        all data.
        """
        status = {
            'repoOwner': u'owner-resum\xe9',
            'repoName': u'name-resum\xe9',
            'sha': u'sha-resum\xe9',
            'state': u'state-resum\xe9',
            'targetURL': u'targetURL-resum\xe9',
            'description': u'description-resum\xe9',
            }
        self.status._github.repos.createStatus = Mock(
            return_value=defer.succeed(None))

        d = self.status._sendGitHubStatus(status)
        result = []
        d.addCallback(result.append)

        self.assertEqual(None, result[0])
        self.status._github.repos.createStatus.assert_called_with(
            repo_name='name-resum\xc3\xa9',
            repo_user='owner-resum\xc3\xa9',
            sha='sha-resum\xc3\xa9',
            state='state-resum\xc3\xa9',
            target_url='targetURL-resum\xc3\xa9',
            description='description-resum\xc3\xa9',
            )
