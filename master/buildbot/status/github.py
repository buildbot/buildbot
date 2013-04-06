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

import datetime

from twisted.internet import defer
from twisted.python import log
from zope.interface import implements

from buildbot.interfaces import IStatusReceiver
from buildbot.process.properties import Interpolate
from buildbot.status.builder import SUCCESS, FAILURE
from buildbot.status.base import StatusReceiverMultiService


class GitHubStatus(StatusReceiverMultiService):
    implements(IStatusReceiver)

    """
    Send build status to GitHub.

    For more details see Buildbot's user manual.
    """

    def __init__(self, token, repoOwner, repoName, sha=None,
                 startDescription=None, endDescription=None):
        """
        Token for GitHub API.
        """
        StatusReceiverMultiService.__init__(self)

        if not sha:
            sha = Interpolate("%(src::revision)s")

        if not startDescription:
            startDescription = Interpolate("Build started.")
        self._startDescription = startDescription

        if not endDescription:
            endDescription = Interpolate("Build done.")
        self._endDescription = endDescription

        self._token = token
        self._sha = sha
        self._repoOwner = repoOwner
        self._repoName = repoName

    def startService(self):
        StatusReceiverMultiService.startService(self)
        self._status = self.parent.getStatus()
        self._status.subscribe(self)

    def builderAdded(self, name, builder):
        """
        Subscribe to all builders.
        """
        return self

    @defer.inlineCallbacks
    def buildStarted(self, builderName, build):
        status = yield self._getGitHubRepoProperties(build)
        if not status:
            defer.returnValue(None)

        (startTime, endTime) = build.getTimes()

        description = yield build.render(self._startDescription)

        status.update({
            'state': 'pending',
            'description': description,
            'builderName': builderName,
            'startDateTime': datetime.datetime.fromtimestamp(
                startTime).isoformat(' '),
            'endDateTime': 'In progress',
            'duration': 'In progress',
            })
        result = yield self._sendGitHubStatus(status)
        defer.returnValue(result)

    @defer.inlineCallbacks
    def buildFinished(self, builderName, build, results):
        status = yield self._getGitHubRepoProperties(build)
        if not status:
            defer.returnValue(None)

        state = self._getGitHubState(results)
        (startTime, endTime) = build.getTimes()
        duration = self._timeDeltaToHumanReadable(startTime, endTime)
        description = yield build.render(self._endDescription)

        status.update({
            'state': state,
            'description': description,
            'builderName': builderName,
            'startDateTime': datetime.datetime.fromtimestamp(
                startTime).isoformat(' '),
            'endDateTime': datetime.datetime.fromtimestamp(
                endTime).isoformat(' '),
            'duration': duration,
            })

        result = yield self._sendGitHubStatus(status)
        defer.returnValue(result)

    def _timeDeltaToHumanReadable(self, start, end):
        """
        Return a string of human readable time delta.
        """
        start_date = datetime.datetime.fromtimestamp(start)
        end_date = datetime.datetime.fromtimestamp(end)
        delta = end_date - start_date

        result = []
        if delta.days > 0:
            result.append('%d days' % (delta.days,))
        if delta.seconds > 0:
            hours = delta.seconds / 3600
            if hours > 0:
                result.append('%d hours' % (hours,))
            minutes = (delta.seconds - hours * 3600) / 60
            if minutes:
                result.append('%d minutes' % (minutes,))
            seconds = delta.seconds % 60
            if seconds > 0:
                result.append('%d seconds' % (seconds,))
        result = ', '.join(result)
        if not result:
            return 'super fast'
        else:
            return result

    @defer.inlineCallbacks
    def _getGitHubRepoProperties(self, build):
        """
        Return a dictionary with GitHub related properties from `build`.
        """
        repoOwner, repoName, sha = yield defer.gatherResults([
            build.render(self._repoOwner),
            build.render(self._repoName),
            build.render(self._sha),
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
            'targetUrl': self._status.getURLForThing(build),
            'buildNumber': str(build.getNumber()),
        }
        defer.returnValue(result)

    def _getGitHubState(self, results):
        """
        Convert Buildbot states into GitHub states.
        """
        # GitHub defines `success`, `failure` and `error` states.
        # We explicitly map success and failure. Any other BuildBot status
        # is converted to `error`.
        state_map = {
          SUCCESS: 'success',
          FAILURE: 'failure',
        }

        try:
            return state_map[results]
        except KeyError:
            return 'error'

    def _sendGitHubStatus(self, status):
        """
        Send status to GitHub API.
        """
        from txgithub.api import GithubApi as GitHubAPI

        github = GitHubAPI(oauth2_token=self._token)
        d = github.createStatus(
            repo_user=status['repoOwner'],
            repo_name=status['repoName'],
            sha=status['sha'],
            state=status['state'],
            target_url=status['targetUrl'],
            description=status['description'],
            )
        d.addCallback(lambda result: None)
        d.addErrback(
            log.err,
            "while sending GitHub status for %s/%s at %s." % (
                status['repoOwner'], status['repoName'], status['sha'])
            )
        return d
