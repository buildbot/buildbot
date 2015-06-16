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

from datetime import datetime

from twisted.internet import defer
from twisted.python import log
try:
    from txgithub.api import GithubApi as GitHubAPI
except ImportError:
    GitHubAPI = None
from zope.interface import implements

from buildbot import config
from buildbot.interfaces import IStatusReceiver
from buildbot.process.properties import Interpolate
from buildbot.status.base import StatusReceiverMultiService
from buildbot.status.builder import FAILURE
from buildbot.status.builder import SUCCESS
from buildbot.util import human_readable_delta

_STATE_MAP = {
    SUCCESS: 'success',
    FAILURE: 'failure',
}


def _getGitHubState(results):
    """
    Convert Buildbot states into GitHub states.
    """
    # GitHub defines `success`, `failure` and `error` states.
    # We explicitly map success and failure. Any other BuildBot status
    # is converted to `error`.
    return _STATE_MAP.get(results, 'error')


class GitHubStatus(StatusReceiverMultiService):

    """
    Send build status to GitHub.

    For more details see Buildbot's user manual.
    """

    implements(IStatusReceiver)

    def __init__(self, token, repoOwner, repoName, sha=None,
                 startDescription=None, endDescription=None,
                 baseURL=None, context=None):
        """
        Token for GitHub API.
        """
        if not GitHubAPI:
            config.error('GitHubStatus requires txgithub package installed')

        StatusReceiverMultiService.__init__(self)

        self._sha = sha or Interpolate("%(src::revision)s")
        self._repoOwner = repoOwner
        self._repoName = repoName
        self._context = context or Interpolate("buildbot/%(prop:buildername)s")
        self._startDescription = startDescription or "Build started."
        self._endDescription = endDescription or "Build done."

        self._github = GitHubAPI(oauth2_token=token, baseURL=baseURL)

        self._status = None

    def startService(self):
        StatusReceiverMultiService.startService(self)
        self._status = self.parent.getStatus()
        self._status.subscribe(self)

    def stopService(self):
        StatusReceiverMultiService.stopService(self)
        self._status.unsubscribe(self)

    def builderAdded(self, name_, builder_):
        """
        Subscribe to all builders.
        """
        return self

    def buildStarted(self, builderName, build):
        """
        See: C{IStatusReceiver}.
        """
        d = self._sendStartStatus(builderName, build)
        d.addErrback(log.err,
                     'While sending start status to GitHub for %s.' %
                     (builderName,))

    @defer.inlineCallbacks
    def _sendStartStatus(self, builderName, build):
        """
        Send start status to GitHub.
        """
        status = yield self._getGitHubRepoProperties(build)
        if not status:
            defer.returnValue(None)

        startTime, _ = build.getTimes()

        description = yield build.render(self._startDescription)

        status.update({
            'state': 'pending',
            'description': description,
            'builderName': builderName,
            'startDateTime': datetime.fromtimestamp(startTime).isoformat(' '),
            'endDateTime': 'In progress',
            'duration': 'In progress',
        })
        result = yield self._sendGitHubStatus(status)
        defer.returnValue(result)

    def buildFinished(self, builderName, build, results):
        """
        See: C{IStatusReceiver}.
        """
        d = self._sendFinishStatus(builderName, build, results)
        d.addErrback(log.err,
                     'While sending finish status to GitHub for %s.' %
                     (builderName,))

    @defer.inlineCallbacks
    def _sendFinishStatus(self, builderName, build, results):
        """
        Send status to GitHub at end of builder execution.
        """
        status = yield self._getGitHubRepoProperties(build)
        if not status:
            defer.returnValue(None)

        state = _getGitHubState(results)
        startTime, endTime = build.getTimes()
        duration = human_readable_delta(startTime, endTime)
        description = yield build.render(self._endDescription)

        status.update({
            'state': state,
            'description': description,
            'builderName': builderName,
            'startDateTime': datetime.fromtimestamp(startTime).isoformat(' '),
            'endDateTime': datetime.fromtimestamp(endTime).isoformat(' '),
            'duration': duration,
        })

        result = yield self._sendGitHubStatus(status)
        defer.returnValue(result)

    @defer.inlineCallbacks
    def _getGitHubRepoProperties(self, build):
        """
        Return a dictionary with GitHub related properties from `build`.
        """
        repoOwner, repoName, sha, context = yield defer.gatherResults([
            build.render(self._repoOwner),
            build.render(self._repoName),
            build.render(self._sha),
            build.render(self._context),
        ])

        if not repoOwner or not repoName:
            defer.returnValue({})

        if not sha:
            log.msg('GitHubStatus: No revision found.')
            defer.returnValue({})

        result = {
            'repoOwner': repoOwner,
            'repoName': repoName,
            'sha': sha,
            'targetURL': self._status.getURLForThing(build),
            'buildNumber': str(build.getNumber()),
            'context': context,
        }
        defer.returnValue(result)

    def _sendGitHubStatus(self, status):
        """
        Send status to GitHub API.
        """

        d = self._github.repos.createStatus(
            repo_user=status['repoOwner'].encode('utf-8'),
            repo_name=status['repoName'].encode('utf-8'),
            sha=status['sha'].encode('utf-8'),
            state=status['state'].encode('utf-8'),
            target_url=status['targetURL'].encode('utf-8'),
            description=status['description'].encode('utf-8'),
            context=status['context'].encode('utf-8'),
        )

        success_message = (
            'Status "%(state)s" sent for '
            '%(repoOwner)s/%(repoName)s at %(sha)s.'
        ) % status
        error_message = (
            'Fail to send status "%(state)s" for '
            '%(repoOwner)s/%(repoName)s at %(sha)s.'
        ) % status
        d.addCallback(lambda _: log.msg(success_message))
        d.addErrback(lambda failure: log.err(failure, error_message))
        return d
