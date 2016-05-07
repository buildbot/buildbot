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

HOSTED_BASE_URL = 'https://api.github.com'


class GithubStatusPush(http.HttpStatusPushBase):
    name = "GithubStatusPush"
    neededDetails = dict(wantProperties=True)

    @defer.inlineCallbacks
    def reconfigService(self, token,
                        startDescription=None, endDescription=None,
                        context=None, baseURL=None, verbose=False, **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)

        self.context = context or Interpolate('buildbot/%(prop:buildername)s')
        self.startDescription = startDescription or 'Build started.'
        self.endDescription = endDescription or 'Build done.'
        if baseURL is None:
            baseURL = HOSTED_BASE_URL
        if baseURL.endswith('/'):
            baseURL = baseURL[:-1]
        self.baseURL = baseURL
        self.session.headers.update({'Authorization': 'token ' + token})
        self.verbose = verbose

    def createStatus(self,
                     repo_user, repo_name, sha, state, target_url=None,
                     description=None, context=None):
        """
        :param sha: Full sha to create the status for.
        :param state: one of the following 'pending', 'success', 'error'
                      or 'failure'.
        :param target_url: Target url to associate with this status.
        :param description: Short description of the status.
        :return: A defered with the result from GitHub.

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

        return self.session.post('/'.join(
            [self.baseURL, 'repos', repo_user, repo_name, 'statuses', sha]), json=payload)

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
        else:
            state = 'pending'
            description = yield props.render(self.startDescription)

        context = yield props.render(self.context)

        sourcestamps = build['buildset']['sourcestamps']
        project = sourcestamps[0]['project']

        if project:
            repoOwner, repoName = project.split('/')
        else:
            repo = sourcestamps[0]['repository'].split('/')[-2:]
            repoOwner = repo[0]
            repoName = '.'.join(repo[1].split('.')[:-1])

        for sourcestamp in sourcestamps:
            sha = sourcestamp['revision']
            try:
                yield self.createStatus(
                    repo_user=repoOwner.encode('utf-8'),
                    repo_name=repoName.encode('utf-8'),
                    sha=sha.encode('utf-8'),
                    state=state.encode('utf-8'),
                    target_url=build['url'].encode('utf-8'),
                    context=context.encode('utf-8'),
                    description=description.encode('utf-8')
                )
                if self.verbose:
                    log.msg(
                        'Status "{state}" sent for '
                        '{repoOwner}/{repoName} at {sha}.'.format(
                            state=state, repoOwner=repoOwner, repoName=repoName, sha=sha))
            except Exception as e:
                log.err(
                    e,
                    'Fail to send status "{state}" for '
                    '{repoOwner}/{repoName} at {sha}'.format(
                        state=state, repoOwner=repoOwner, repoName=repoName, sha=sha))
