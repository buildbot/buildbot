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
from buildbot.util.giturlparse import giturlparse

HOSTED_BASE_URL = 'https://api.github.com'


class GitHubStatusPush(http.HttpStatusPushBase):
    name = "GitHubStatusPush"

    @defer.inlineCallbacks
    def reconfigService(self, token,
                        startDescription=None, endDescription=None,
                        context=None, baseURL=None, verbose=False, wantProperties=True, **kwargs):
        token = yield self.renderSecrets(token)
        yield super().reconfigService(wantProperties=wantProperties, **kwargs)

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
        props.master = self.master

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
        if not sourcestamps:
            return

        for sourcestamp in sourcestamps:
            issue = None
            branch = props.getProperty('branch')
            if branch:
                m = re.search(r"refs/pull/([0-9]*)/merge", branch)
                if m:
                    issue = m.group(1)

            repo_owner = None
            repo_name = None
            project = sourcestamp['project']
            repository = sourcestamp['repository']
            if project and "/" in project:
                repo_owner, repo_name = project.split('/')
            elif repository:
                giturl = giturlparse(repository)
                if giturl:
                    repo_owner = giturl.owner
                    repo_name = giturl.repo

            if not repo_owner or not repo_name:
                log.msg('Skipped status update because required repo information is missing.')
                continue

            sha = sourcestamp['revision']
            response = None

            # If the scheduler specifies multiple codebases, don't bother updating
            # the ones for which there is no revision
            if not sha:
                log.msg(
                    'Skipped status update for codebase {codebase}, '
                    'context "{context}", issue {issue}.'.format(
                        codebase=sourcestamp['codebase'], issue=issue, context=context))
                continue

            try:
                if self.verbose:
                    log.msg("Updating github status: repo_owner={}, repo_name={}".format(
                            repo_owner, repo_name))

                response = yield self.createStatus(repo_user=repo_owner,
                                                   repo_name=repo_name,
                                                   sha=sha,
                                                   state=state,
                                                   target_url=build['url'],
                                                   context=context,
                                                   issue=issue,
                                                   description=description)

                if not response:
                    # the implementation of createStatus refused to post update due to missing data
                    continue

                if not self.isStatus2XX(response.code):
                    raise Exception()

                if self.verbose:
                    log.msg(
                        'Updated status with "{state}" for {repo_owner}/{repo_name} '
                        'at {sha}, context "{context}", issue {issue}.'.format(
                            state=state, repo_owner=repo_owner, repo_name=repo_name,
                            sha=sha, issue=issue, context=context))
            except Exception as e:
                if response:
                    content = yield response.content()
                    code = response.code
                else:
                    content = code = "n/a"
                log.err(
                    e,
                    'Failed to update "{state}" for {repo_owner}/{repo_name} '
                    'at {sha}, context "{context}", issue {issue}. '
                    'http {code}, {content}'.format(
                        state=state, repo_owner=repo_owner, repo_name=repo_name,
                        sha=sha, issue=issue, context=context,
                        code=code, content=content))


class GitHubCommentPush(GitHubStatusPush):
    name = "GitHubCommentPush"

    def setDefaults(self, context, startDescription, endDescription):
        self.context = ''
        self.startDescription = startDescription
        self.endDescription = endDescription or 'Build done.'

    @defer.inlineCallbacks
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

        if issue is None:
            log.msg('Skipped status update for repo {} sha {} as issue is not specified'.format(
                repo_name, sha))
            return None

        url = '/'.join(['/repos', repo_user, repo_name, 'issues', issue, 'comments'])
        ret = yield self._http.post(url, json=payload)
        return ret
