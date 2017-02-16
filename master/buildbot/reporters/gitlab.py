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

HOSTED_BASE_URL = 'https://gitlab.com'


class GitLabStatusPush(http.HttpStatusPushBase):
    name = "GitLabStatusPush"
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
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, baseURL, headers={'PRIVATE-TOKEN': token})
        self.verbose = verbose
        self.project_ids = {}

    def createStatus(self,
                     project_id, branch, sha, state, target_url=None,
                     description=None, context=None):
        """
        :param project_id: Project ID from GitLab
        :param branch: Branch name to create the status for.
        :param sha: Full sha to create the status for.
        :param state: one of the following 'pending', 'success', 'error'
                      or 'failure'.
        :param target_url: Target url to associate with this status.
        :param description: Short description of the status.
        :param context: Context of the result
        :return: A deferred with the result from GitLab.

        """
        payload = {'state': state, 'ref': branch}

        if description is not None:
            payload['description'] = description

        if target_url is not None:
            payload['target_url'] = target_url

        if context is not None:
            payload['name'] = context

        return self._http.post('/api/v3/projects/%d/statuses/%s' % (
            project_id, sha),
            json=payload)

    @defer.inlineCallbacks
    def send(self, build):
        props = Properties.fromDict(build['properties'])

        if build['complete']:
            state = {
                SUCCESS: 'success',
                WARNINGS: 'success',
                FAILURE: 'failed',
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

        # default to master if not found
        branch = sourcestamps[0].get('branch', 'master')

        if project:
            repoOwner, repoName = project.split('/')
        else:
            repo = sourcestamps[0]['repository'].split('/')[-2:]
            repoOwner = repo[0]
            repoName = '.'.join(repo[1].split('.')[:-1])

        m = re.match(".*:(.*)", repoOwner)
        if m is not None:
            repoOwner = m.group(1)

        # retrieve project id via cache
        self.project_ids
        project_full_name = "%s%%2F%s" % (repoOwner, repoName)
        project_full_name = unicode2NativeString(project_full_name)

        if project_full_name not in self.project_ids:
            proj = yield self._http.get('/api/v3/projects/%s' % (project_full_name))
            proj = yield proj.json()
            self.project_ids[project_full_name] = proj['id']

        proj_id = self.project_ids[project_full_name]
        for sourcestamp in sourcestamps:
            sha = sourcestamp['revision']
            try:
                branch = unicode2NativeString(branch)
                sha = unicode2NativeString(sha)
                state = unicode2NativeString(state)
                target_url = unicode2NativeString(build['url'])
                context = unicode2NativeString(context)
                description = unicode2NativeString(description)
                res = yield self.createStatus(
                    project_id=proj_id,
                    branch=branch,
                    sha=sha,
                    state=state,
                    target_url=target_url,
                    context=context,
                    description=description
                )
                if res.code not in (200, 201, 204):
                    message = yield res.json()
                    message = message.get('message', 'unspecified error')
                    log.msg(
                        'Could not send status "{state}" for '
                        '{repoOwner}/{repoName} at {sha}: {message}'.format(
                            state=state, repoOwner=repoOwner,
                            repoName=repoName, sha=sha,
                            message=message))
                elif self.verbose:
                    log.msg(
                        'Status "{state}" sent for '
                        '{repoOwner}/{repoName} at {sha}.'.format(
                            state=state, repoOwner=repoOwner,
                            repoName=repoName, sha=sha))
            except Exception as e:
                log.err(
                    e,
                    'Fail to send status "{state}" for '
                    '{repoOwner}/{repoName} at {sha}'.format(
                        state=state, repoOwner=repoOwner,
                        repoName=repoName, sha=sha))
