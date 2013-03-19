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
from dateutil.relativedelta import relativedelta

from twisted.python import log as twlog
from txgithub.api import GithubApi as GitHubAPI
from zope.interface import implements

from buildbot.interfaces import IStatusReceiver
from buildbot.process.properties import Interpolate
from buildbot.status.builder import SUCCESS, FAILURE, EXCEPTION
from buildbot.status.base import StatusReceiverMultiService


GITHUB_STATE = {
  SUCCESS: 'success',
  FAILURE: 'failure',
  EXCEPTION: 'error',
}


class GitHubStatus(StatusReceiverMultiService):
    implements(IStatusReceiver)

    """
    Send build status to GitHub.

    For more details see user manual.
    """

    startDescription = (
        "Build started at %(startDateTime)s."
        )
    endDescription = (
        "[%(state)s] Build done after %(duration)s. "
        "Done at %(endDateTime)s."
        )

    def __init__(self, token, repoOwner, repoName, sha=None):
        """
        Token for GitHub API.
        """
        StatusReceiverMultiService.__init__(self)
        self._github = GitHubAPI(oauth2_token=token, sha=None)
        if not sha:
            sha = Interpolate("%(src::revision)s")

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

    def buildStarted(self, builderName, build):
        repo = self._getGitHubRepoProperties(build)
        if not repo:
            return

        (startTime, endTime) = build.getTimes()
        state = 'pending'

        status = {
            'state': state,
            'sha': repo['sha'],
            'description': self.startDescription,
            'targetUrl': repo['targetUrl'],
            'repoOwner': repo['repoOwner'],
            'repoName': repo['repoName'],
            'buildNumber': repo['buildNumber'],
            'builderName': builderName,
            'startDateTime': datetime.datetime.fromtimestamp(
                startTime).isoformat(' '),
            'endDateTime': 'In progress',
            'duration': 'In progress',
            }

        self._sendGitHubStatus(status)
        return self

    def buildFinished(self, builderName, build, results):
        repo = self._getGitHubRepoProperties(build)
        if not repo:
            return

        state = GITHUB_STATE[results]
        (startTime, endTime) = build.getTimes()
        duration = self._timeDeltaToHumanReadable(startTime, endTime)

        status = {
            'state': state,
            'sha': repo['sha'],
            'description': self.endDescription,
            'targetUrl': repo['targetUrl'],
            'repoOwner': repo['repoOwner'],
            'repoName': repo['repoName'],
            'buildNumber': repo['buildNumber'],
            'builderName': builderName,
            'startDateTime': datetime.datetime.fromtimestamp(
                startTime).isoformat(' '),
            'endDateTime': datetime.datetime.fromtimestamp(
                endTime).isoformat(' '),
            'duration': duration,
            }

        self._sendGitHubStatus(status)
        return self

    def _timeDeltaToHumanReadable(self, start, end):
        """
        Return a string of human readable time delta.
        """
        start_date = datetime.datetime.fromtimestamp(start)
        end_date = datetime.datetime.fromtimestamp(end)
        delta = relativedelta(end_date, start_date)

        attributes = [
            'years', 'months', 'days', 'hours', 'minutes', 'seconds']

        result = []
        for attribute_name in attributes:
            attribute = getattr(delta, attribute_name)
            if attribute > 0:
                result.append('%d %s' % (attribute, attribute_name))

        return ', '.join(result)

    def _getGitHubRepoProperties(self, build):
        """
        Return a dictionary with GitHub related properties from `build`.
        """
        repoOwner = build.render(self._repoOwner)
        repoName = build.render(self._repoName)
        sha = build.render(self._sha)

        if not repoOwner or not repoName or not sha:
            return {}

        return {
            'repoOwner': repoOwner,
            'repoName': repoName,
            'sha': sha,
            'targetUrl': self._status.getURLForThing(build),
            'buildNumber': str(build.getNumber()),
        }

    def _sendGitHubStatus(self, status):
        """
        Send status to github.
        """
        if not status['sha']:
            twlog.msg('GitHubStatus: Build has no revision')
            return

        description = status['description'] % status
        deferred = self._github.createStatus(
            repo_user=status['repoOwner'],
            repo_name=status['repoName'],
            sha=status['sha'],
            state=status['state'],
            target_url=status['targetUrl'],
            description=description,
            )
        deferred.addErrback(
            twlog.err,
            "while sending GitHub status for %s/%s at %s." % (
                status['repoOwner'], status['repoName'], status['sha'])
            )
