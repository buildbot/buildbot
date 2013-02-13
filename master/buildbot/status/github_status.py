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

import datetime
from dateutil.relativedelta import relativedelta

from zope.interface import implements
from twisted.python import log
from github import Github, GithubException

from buildbot.status.builder import SUCCESS, FAILURE, EXCEPTION
from buildbot.status.base import StatusReceiverMultiService
from buildbot.interfaces import IStatusReceiver


GITHUB_STATE = {
  SUCCESS: 'success',
  FAILURE: 'failure',
  EXCEPTION: 'error',
}


class GitHubStatus(StatusReceiverMultiService):
    implements(IStatusReceiver)

    """
    Publishes a build status using Github Status API
    (http://developer.github.com/v3/repos/statuses/).

    Builders will need to define the following properties:
    * github_repo_owner
    * github_repo_name

    Buildes without this properties are skipped.

    The following class members can be changes for custom detailed message:
    * startDescription
    * endDescription

    The following keys are available for custome message:
    * state - 'pending'|'success'|'failure'|'error'
    * sha
    * targetUrl - URL to Buildbot build page.
    * repoOwner - Name of repo owner.
    * repoName - Name of the repo.
    * buildNumber - Buildbot build number.
    * builderName - Name of the builder.
    * startDateTime
    * endDateTime
    * duration - Human readable representation of elapsed time.
    """

    startDescription = (
        "Build started at %(startDateTime)s."
        )
    endDescription = (
        "[%(state)s] Build done after %(duration)s. "
        "Done at %(endDateTime)s."
        )

    def __init__(self, token):
        """
        Token for GitHub API.
        """
        StatusReceiverMultiService.__init__(self)
        self._token = token
        self._github = Github(token)
        self._repos = {}

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
        sha = build.getProperty('revision', None)
        repo = self._getGitHubRepoProperties(build)
        if not repo:
            return

        (startTime, endTime) = build.getTimes()
        buildNumber = str(build.getNumber())
        state = 'pending'
        targetUrl = self._status.getURLForThing(build)

        status = {
            'state': state,
            'sha': sha,
            'description': self.startDescription,
            'targetUrl': targetUrl,
            'repoOwner': repo['owner'],
            'repoName': repo['name'],
            'buildNumber': buildNumber,
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
        buildNumber = str(build.getNumber())
        sha = build.getProperty('revision')
        targetUrl = self._status.getURLForThing(build)

        status = {
            'state': state,
            'sha': sha,
            'description': self.endDescription,
            'targetUrl': targetUrl,
            'repoOwner': repo['owner'],
            'repoName': repo['name'],
            'buildNumber': buildNumber,
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
        owner = build.getProperty('github_repo_owner', None)
        name = build.getProperty('github_repo_name', None)

        if not owner or not name:
            return {}

        return {
            'owner': owner,
            'name': name,
        }

    def _getGitHubCachedRepo(self, repo_name):
        """
        Return cached repo.

        Here we have a cache and we have a problem.
        I hope repos should not change location that often.
        """
        try:
            return self._repos[repo_name]
        except KeyError:
            self._repos[repo_name] = self._github.get_repo(repo_name)
            return self._repos[repo_name]

    def _sendGitHubStatus(self, status):
        """
        Send status to github.
        """
        if not status['sha']:
            log.msg('GitHubStatus: Build has no revision')
            return

        repo_name = "%s/%s" % (status['repoOwner'], status['repoName'])
        description = status['description'] % status
        try:
            repo = self._getGitHubCachedRepo(repo_name)
            commit = repo.get_commit(status['sha'])
            commit.create_status(
                status['state'],
                status['targetUrl'],
                description,
                )
        except GithubException, error:
            log.msg(
                'GitHubStatus: Failed to send status for %s to GitHub: %s' % (
                repo_name, str(error)))
