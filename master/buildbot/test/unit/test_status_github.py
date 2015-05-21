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

import datetime


from mock import Mock
from mock import patch
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.status.builder import FAILURE
from buildbot.status.builder import SUCCESS
try:
    # Try to import txgithub and skip tests if we fail to import it.
    import txgithub
    txgithub  # Silence the linter.
except ImportError:
    txgithub = None
else:
    # Import fully qualified module for patching.
    import buildbot.status.github
    buildbot.status.github

    from buildbot.status.github import GitHubStatus
    from buildbot.status.github import _getGitHubState

from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.util import logging


class MarkerError(Exception):

    """
    An exceptions used as a marker in tests.
    """


class TestGitHubStatus(unittest.TestCase, logging.LoggingMixin):

    """
    Unit tests for `GitHubStatus`.
    """

    def setUp(self):
        super(TestGitHubStatus, self).setUp()
        if not txgithub:
            raise unittest.SkipTest("txgithub not found.")

        self.setUpLogging()
        self.build = FakeBuild()
        self.status = GitHubStatus(
            token='token', repoOwner='owner', repoName='name')

    def tearDown(self):
        self.assertEqual(
            0,
            len(self._logEvents),
            'There are still logs not validated:\n%s' % self._logEvents,
        )

        pending_errors = self.flushLoggedErrors()
        self.assertEqual(
            0,
            len(pending_errors),
            'There are still errors not validated:\n%s' % pending_errors,
        )

        super(TestGitHubStatus, self).tearDown()

    def assertLog(self, message):
        """
        Check that top of the log queue has message.
        """
        log_event = self._popLog()
        self.assertFalse(log_event['isError'], 'Log is an error.')
        self.assertEqual(
            (message, ), log_event['message'], 'Wrong log message')

    def assertLogError(self, error, message):
        """
        Pop log queue and validate error and error message.
        """
        log_event = self._popLog()
        self.assertTrue(log_event['isError'], 'Log is not an error.')
        self.assertEqual(message, log_event['why'], 'Wrong error message.')

        # The error is also checked in Twisted logged errors queue.
        errors = self.flushLoggedErrors(type(error))
        self.assertEqual(error, errors[0].value)

    def _popLog(self):
        try:
            return self._logEvents.pop()
        except IndexError:
            raise AssertionError('Log queue is empty.')

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

        self.assertEqual(repoOwner, status._repoOwner)
        self.assertEqual(repoName, status._repoName)

        # Check default values.
        self.assertEqual(status._sha, Interpolate("%(src::revision)s"))
        self.assertEqual(status._startDescription, "Build started.")
        self.assertEqual(status._endDescription, "Build done.")

    def test_custom_github_url(self):
        """
        Check that the custom URL is passed as it should be
        """
        with patch('buildbot.status.github.GitHubAPI') as mock:
            token = 'GitHub-API-Token'
            owner = Interpolate('owner')
            name = Interpolate('name')

            GitHubStatus(token, owner, name)

            mock.assert_called_once_with(oauth2_token=token, baseURL=None)

        with patch('buildbot.status.github.GitHubAPI') as mock:
            token = 'GitHub-API-Token'
            owner = Interpolate('owner')
            name = Interpolate('name')
            url = 'https://my.example.com/api'

            GitHubStatus(token, owner, name, baseURL=url)

            mock.assert_called_once_with(oauth2_token=token, baseURL=url)

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

    def test_buildStarted_success(self):
        """
        Will call _sendStartStatus and return `None`.
        """
        builder_name = 'builder-name'
        build = object()
        self.status._sendStartStatus = Mock()

        result = self.status.buildStarted(builder_name, build)

        self.assertIdentical(result, None)
        self.status._sendStartStatus.assert_called_once_with(
            builder_name, build)

    def test_buildStarted_failure(self):
        """
        On failure will return `None` and log the error.
        """
        builder_name = 'builder-name'
        error = MarkerError('start-errors')
        self.status._sendStartStatus = Mock(
            return_value=defer.fail(error))

        result = self.status.buildStarted(builder_name, None)

        self.assertIdentical(result, None)
        self.assertLogError(
            error,
            'While sending start status to GitHub for builder-name.')

    def test_buildFinished_success(self):
        """
        Will call _sendFinishStatus and return `None`.
        """
        builder_name = 'builder-name'
        build = object()
        results = object()
        self.status._sendFinishStatus = Mock()

        result = self.status.buildFinished(builder_name, build, results)

        self.assertIdentical(result, None)
        self.status._sendFinishStatus.assert_called_once_with(
            builder_name, build, results)

    def test_buildFinished_failure(self):
        """
        On failure returns `None` and log the error.
        """
        builder_name = 'builder-name'
        error = MarkerError('finish-errors')
        self.status._sendFinishStatus = Mock(
            return_value=defer.fail(error))

        result = self.status.buildFinished(builder_name, None, None)

        self.assertIdentical(result, None)
        self.assertLogError(
            error,
            'While sending finish status to GitHub for builder-name.')

    def test_sendStartStatus_no_properties(self):
        """
        Status sending for _sendStartStatus is skipped if no GitHub specific
        properties are obtained from _getGitHubRepoProperties.
        """
        self.status._getGitHubRepoProperties = lambda build: {}

        d = self.status._sendStartStatus('builder-name', None)
        result = self.successResultOf(d)

        self.assertIdentical(result, None)

    def test_sendStartStatus_failure(self):
        """
        On failure returns the failed deferred.
        """
        error = MarkerError('send-start-status-error')
        self.status._getGitHubRepoProperties = lambda build: defer.fail(error)

        d = self.status._sendStartStatus('builder-name', None)
        failure = self.failureResultOf(d)

        self.assertEqual(error, failure.value)

    def test_sendStartStatus_ok(self):
        """
        When _getGitHubRepoProperties return a dict with properties
        for this build, _sendStartStatus will augment with details for
        start state and send a GitHub API request.
        """
        self.status._getGitHubRepoProperties = lambda build: {
            'repoOwner': 'repo-owner',
            'repoName': 'repo-name',
            'sha': '123',
            'targetURL': 'http://example.tld',
            'buildNumber': '1',
        }
        self.status._sendGitHubStatus = Mock(return_value=defer.succeed(None))
        self.build.getTimes = lambda: (1, None)
        startDateTime = datetime.datetime.fromtimestamp(1).isoformat(' ')

        d = self.status._sendStartStatus('builder-name', self.build)
        result = self.successResultOf(d)

        self.assertIdentical(result, None)
        self.status._sendGitHubStatus.assert_called_with({
            'repoOwner': 'repo-owner',
            'repoName': 'repo-name',
            'sha': '123',
            'targetURL': 'http://example.tld',
            'buildNumber': '1',
            # Augmented arguments.
            'state': 'pending',
            'description': 'Build started.',
            'builderName': 'builder-name',
            'startDateTime': startDateTime,
            'endDateTime': 'In progress',
            'duration': 'In progress',
        })

    def test_sendFinishStatus_no_properties(self):
        """
        Status sending for _sendFinishStatus is skipped if no GitHub specific
        properties are obtained from _getGitHubRepoProperties.
        """
        error = MarkerError('send-start-status-error')
        self.status._getGitHubRepoProperties = lambda build: defer.fail(error)

        d = self.status._sendFinishStatus('builder-name', None, None)
        failure = self.failureResultOf(d)

        self.assertEqual(error, failure.value)

    def test_sendFinishStatus_failure(self):
        """
        On failure returns the failed deferred.
        """
        self.status._getGitHubRepoProperties = lambda build: {}

        d = self.status._sendFinishStatus('builder-name', None, None)
        result = self.successResultOf(d)

        self.assertIdentical(result, None)

    def test_sendFinishStatus_ok(self):
        """
        When _getGitHubRepoProperties return a dict _sendFinishStatus will
        augment it with build result and sent status to GitHub API.
        """
        self.status._getGitHubRepoProperties = lambda build: {
            'repoOwner': 'repo-owner',
            'repoName': 'repo-name',
            'sha': '123',
            'targetURL': 'http://example.tld',
            'buildNumber': '1',
        }
        self.status._sendGitHubStatus = Mock(return_value=defer.succeed(None))
        self.build.getTimes = lambda: (1, 3)
        startDateTime = datetime.datetime.fromtimestamp(1).isoformat(' ')
        endDateTime = datetime.datetime.fromtimestamp(3).isoformat(' ')

        d = self.status._sendFinishStatus('builder-name', self.build, SUCCESS)
        result = self.successResultOf(d)

        self.assertIdentical(result, None)
        self.status._sendGitHubStatus.assert_called_with({
            'repoOwner': 'repo-owner',
            'repoName': 'repo-name',
            'sha': '123',
            'targetURL': 'http://example.tld',
            'buildNumber': '1',
            # Augmented arguments.
            'state': 'success',
            'description': 'Build done.',
            'builderName': 'builder-name',
            'startDateTime': startDateTime,
            'endDateTime': endDateTime,
            'duration': '2 seconds',
        })

    def test_getGitHubRepoProperties_skip_no_sha(self):
        """
        An empty dict is returned when any of the repo name, owner and sha
        interpolation returns an empty string or None.
        """
        self.build._repoOwner = Interpolate('owner')
        self.build._repoName = Interpolate('name')
        self.build._sha = Interpolate('')

        d = self.status._getGitHubRepoProperties(self.build)
        result = self.successResultOf(d)

        self.assertEqual({}, result)
        self.assertLog('GitHubStatus: No revision found.')

    def test_getGitHubRepoProperties_skip_no_owner(self):
        self.status._repoOwner = Interpolate('')
        self.status._repoName = Interpolate('name')
        self.status._sha = Interpolate('sha')

        d = self.status._getGitHubRepoProperties(self.build)
        result = self.successResultOf(d)

        self.assertEqual({}, result)

    def test_getGitHubRepoProperties_skip_no_name(self):
        self.status._repoOwner = Interpolate('owner')
        self.status._repoName = Interpolate('')
        self.status._sha = Interpolate('sha')

        d = self.status._getGitHubRepoProperties(self.build)
        result = self.successResultOf(d)

        self.assertEqual({}, result)

    def test_getGitHubRepoProperties_ok(self):
        """
        A dictionary with build status properties is returned when
        required properties were rendered.
        """
        self.status._repoOwner = Interpolate('owner')
        self.status._repoName = Interpolate('name')
        self.status._sha = Interpolate('sha')
        self.status._status = Mock()
        self.status._status.getURLForThing = lambda build: 'http://example.org'
        self.build.getNumber = lambda: 1

        d = self.status._getGitHubRepoProperties(self.build)
        result = self.successResultOf(d)

        self.assertEqual({
            'buildNumber': '1',
            'repoName': 'name',
            'repoOwner': 'owner',
            'sha': 'sha',
            'targetURL': 'http://example.org',
        },
            result)

    def test_getGitHubState(self):
        """
        _getGitHubState will try to translate BuildBot status into GitHub
        status. For unknown values will fallback to 'error'.
        """
        self.assertEqual('success', _getGitHubState(SUCCESS))
        self.assertEqual('failure', _getGitHubState(FAILURE))
        self.assertEqual('error', _getGitHubState('anything-else'))

    def test_sendGitHubStatus_success(self):
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
        result = self.successResultOf(d)

        self.assertEqual(None, result)
        self.status._github.repos.createStatus.assert_called_with(
            repo_name='name-resum\xc3\xa9',
            repo_user='owner-resum\xc3\xa9',
            sha='sha-resum\xc3\xa9',
            state='state-resum\xc3\xa9',
            target_url='targetURL-resum\xc3\xa9',
            description='description-resum\xc3\xa9',
        )

        self.assertLog(
            u'Status "state-resum\xe9" sent for '
            u'owner-resum\xe9/name-resum\xe9 at sha-resum\xe9.'
        )

    def test_sendGitHubStatus_error(self):
        """
        sendGitHubStatus will log an error if txgithub sendGitHubStatus fails.
        """
        status = {
            'repoOwner': u'owner',
            'repoName': u'name',
            'sha': u'sha',
            'state': u'state',
            'targetURL': u'targetURL',
            'description': u'description',
        }
        error = MarkerError('fail-send-status')
        self.status._github.repos.createStatus = Mock(
            return_value=defer.fail(error))

        self.status._sendGitHubStatus(status)

        self.assertLogError(
            error,
            u'Fail to send status "state" for owner/name at sha.')
