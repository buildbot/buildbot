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

import re

from twisted.internet import defer
from twisted.python import log

from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import http
from buildbot.util import httpclientservice
from buildbot.util import unicode2NativeString

HOSTED_BASE_URL = 'https://api.github.com'


class GitHubStatusPush(http.HttpStatusPushBase):
    name = "GitHubStatusPush"
    neededDetails = dict(wantProperties=True)

    @defer.inlineCallbacks
    def reconfigService(self, token,
                        startDescription=None, endDescription=None,
                        context=None, baseURL=None, verbose=False, **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)

        self.setDefaults(context, startDescription, endDescription)
        if baseURL is None:
            baseURL = HOSTED_BASE_URL
        if baseURL.endswith('/'):
            baseURL = baseURL[:-1]

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, baseURL, headers={
                'Authorization': 'token ' + token,
                'User-Agent': 'Buildbot'
            },
            debug=self.debug, verify=self.verify)
        self.verbose = verbose

    def setDefaults(self, context, startDescription, endDescription):
        self.context = context or Interpolate('buildbot/%(prop:buildername)s')
        self.startDescription = startDescription or 'Build started.'
        self.endDescription = endDescription or 'Build done.'

    def createStatus(self,
                     repo_user, repo_name, sha, state, target_url=None,
                     context=None, issue=None, description=None):
        """
        :param repo_user: GitHub user or organization
        :param repo_name: Name of the repository
        :param sha: Full sha to create the status for.
        :param state: one of the following 'pending', 'success', 'error'
                      or 'failure'.
        :param target_url: Target url to associate with this status.
        :param description: Short description of the status.
        :param context: Build context
        :return: A deferred with the result from GitHub.

        This code comes from txgithub by @tomprince.
        txgithub is based on twisted's webclient agent, which is much less reliable and featureful
        as txrequest (support for proxy, connection pool, keep alive, retry, etc)
        """
        payload = {'state': state}

        if description is not None:
            payload['description'] = description

        if target_url is not None:
            payload['target_url'] = target_url

        if context is not None:
            payload['context'] = context

        return self._http.post(
            '/'.join(['/repos', repo_user, repo_name, 'statuses', sha]),
            json=payload)

    @defer.inlineCallbacks
    def send(self, build):
        props = Properties.fromDict(build['properties'])

        if build['complete']:
            state = {
                SUCCESS: 'success',
                WARNINGS: 'success',
                FAILURE: 'failure',
                SKIPPED: 'success',
                EXCEPTION: 'error',
                RETRY: 'pending',
                CANCELLED: 'error'
            }.get(build['results'], 'error')
            description = yield props.render(self.endDescription)
        elif self.startDescription:
            state = 'pending'
            description = yield props.render(self.startDescription)
        else:
            return

        context = yield props.render(self.context)

        sourcestamps = build['buildset'].get('sourcestamps')

        if not sourcestamps or not sourcestamps[0]:
            return

        project = sourcestamps[0]['project']

        branch = props['branch']
        m = re.search(r"refs/pull/([0-9]*)/merge", branch)
        if m:
            issue = m.group(1)
        else:
            issue = None

        if project:
            repoOwner, repoName = project.split('/')
        else:
            repo = sourcestamps[0]['repository'].split('/')[-2:]
            repoOwner = repo[0]
            repoName = '.'.join(repo[1].split('.')[:-1])

        for sourcestamp in sourcestamps:
            sha = sourcestamp['revision']
            try:
                repo_user = unicode2NativeString(repoOwner)
                repo_name = unicode2NativeString(repoName)
                sha = unicode2NativeString(sha)
                state = unicode2NativeString(state)
                target_url = unicode2NativeString(build['url'])
                context = unicode2NativeString(context)
                issue = unicode2NativeString(issue)
                description = unicode2NativeString(description)
                yield self.createStatus(
                    repo_user=repo_user,
                    repo_name=repo_name,
                    sha=sha,
                    state=state,
                    target_url=target_url,
                    context=context,
                    issue=issue,
                    description=description
                )
                if self.verbose:
                    log.msg(
                        'Updated status with "{state}" for '
                        '{repoOwner}/{repoName} at {sha}, issue {issue}.'.format(
                            state=state, repoOwner=repoOwner, repoName=repoName, sha=sha, issue=issue))
            except Exception as e:
                log.err(
                    e,
                    'Failed to update "{state}" for '
                    '{repoOwner}/{repoName} at {sha}, issue {issue}'.format(
                        state=state, repoOwner=repoOwner, repoName=repoName, sha=sha, issue=issue))


class GitHubCommentPush(GitHubStatusPush):
    name = "GitHubCommentPush"
    neededDetails = dict(wantProperties=True)

    def setDefaults(self, context, startDescription, endDescription):
        self.context = ''
        self.startDescription = startDescription
        self.endDescription = endDescription or 'Build done.'

    def createStatus(self,
                     repo_user, repo_name, sha, state, target_url=None,
                     context=None, issue=None, description=None):
        """
        :param repo_user: GitHub user or organization
        :param repo_name: Name of the repository
        :param issue: Pull request number
        :param state: one of the following 'pending', 'success', 'error'
                      or 'failure'.
        :param description: Short description of the status.
        :return: A deferred with the result from GitHub.

        This code comes from txgithub by @tomprince.
        txgithub is based on twisted's webclient agent, which is much less reliable and featureful
        as txrequest (support for proxy, connection pool, keep alive, retry, etc)
        """
        payload = {'body': description}

        return self._http.post(
            '/'.join(['/repos', repo_user, repo_name, 'issues', issue, 'comments']),
            json=payload)
