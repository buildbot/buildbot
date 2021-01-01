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

from urllib.parse import quote_plus as urlquote_plus

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.message import MessageFormatterRenderable
from buildbot.util import giturlparse
from buildbot.util import httpclientservice
from buildbot.warnings import warn_deprecated

HOSTED_BASE_URL = 'https://gitlab.com'


class GitLabStatusPush(ReporterBase):
    name = "GitLabStatusPush"

    def checkConfig(self, token, startDescription=None, endDescription=None,
                    context=None, baseURL=None, verbose=False, wantProperties=True,
                    builders=None, debug=None, verify=None,
                    wantSteps=False, wantPreviousBuild=False, wantLogs=False, generators=None,
                    **kwargs):

        old_arg_names = {
            'startDescription': startDescription is not None,
            'endDescription': endDescription is not None,
            'wantProperties': wantProperties is not True,
            'builders': builders is not None,
            'wantSteps': wantSteps is not False,
            'wantPreviousBuild': wantPreviousBuild is not False,
            'wantLogs': wantLogs is not False,
        }

        passed_old_arg_names = [k for k, v in old_arg_names.items() if v]

        if passed_old_arg_names:

            old_arg_names_msg = ', '.join(passed_old_arg_names)
            if generators is not None:
                config.error(("can't specify generators and deprecated {} arguments ({}) at the "
                              "same time").format(self.__class__.__name__, old_arg_names_msg))
            warn_deprecated('2.10.0',
                            ('The arguments {} passed to {} have been deprecated. Use generators '
                             'instead').format(old_arg_names_msg, self.__class__.__name__))

        if generators is None:
            generators = self._create_generators_from_old_args(builders, wantProperties, wantSteps,
                                                               wantPreviousBuild, wantLogs,
                                                               startDescription, endDescription)

        super().checkConfig(generators=generators, **kwargs)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self, token,
                        startDescription=None, endDescription=None,
                        context=None, baseURL=None, verbose=False, wantProperties=True,
                        builders=None, debug=None, verify=None,
                        wantSteps=False, wantPreviousBuild=False, wantLogs=False, generators=None,
                        **kwargs):

        token = yield self.renderSecrets(token)
        self.debug = debug
        self.verify = verify
        self.verbose = verbose
        self.context = context or Interpolate('buildbot/%(prop:buildername)s')

        if generators is None:
            generators = self._create_generators_from_old_args(builders, wantProperties, wantSteps,
                                                               wantPreviousBuild, wantLogs,
                                                               startDescription, endDescription)

        yield super().reconfigService(generators=generators, **kwargs)

        if baseURL is None:
            baseURL = HOSTED_BASE_URL
        if baseURL.endswith('/'):
            baseURL = baseURL[:-1]
        self.baseURL = baseURL
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, baseURL, headers={'PRIVATE-TOKEN': token},
            debug=self.debug, verify=self.verify)
        self.project_ids = {}

    def _create_generators_from_old_args(self, builders, wantProperties, wantSteps,
                                         wantPreviousBuild, wantLogs,
                                         startDescription, endDescription):
        # wantProperties is ignored, because MessageFormatterRenderable always wants properties.
        # wantSteps and wantPreviousBuild are ignored ignored, because they are not used in
        # this reporter.
        start_formatter = MessageFormatterRenderable(startDescription or 'Build started.')
        end_formatter = MessageFormatterRenderable(endDescription or 'Build done.')

        return [
            BuildStartEndStatusGenerator(builders=builders, add_logs=wantLogs,
                                         start_formatter=start_formatter,
                                         end_formatter=end_formatter)
        ]

    def createStatus(self,
                     project_id, branch, sha, state, target_url=None,
                     description=None, context=None):
        """
        :param project_id: Project ID from GitLab
        :param branch: Branch name to create the status for.
        :param sha: Full sha to create the status for.
        :param state: one of the following 'pending', 'success', 'failed'
                      or 'cancelled'.
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

        return self._http.post('/api/v4/projects/{}/statuses/{}'.format(project_id, sha),
                json=payload)

    @defer.inlineCallbacks
    def getProjectId(self, sourcestamp):
        # retrieve project id via cache
        url = giturlparse(sourcestamp['repository'])
        if url is None:
            return None
        project_full_name = "{}/{}".format(url.owner, url.repo)
        # gitlab needs project name to be fully url quoted to get the project id
        project_full_name = urlquote_plus(project_full_name)

        if project_full_name not in self.project_ids:
            response = yield self._http.get('/api/v4/projects/{}'.format(project_full_name))
            proj = yield response.json()
            if response.code not in (200, ):
                log.msg(
                    'Unknown (or hidden) gitlab project'
                    '{repo}: {message}'.format(
                        repo=project_full_name, **proj))
                return None
            self.project_ids[project_full_name] = proj['id']

        return self.project_ids[project_full_name]

    @defer.inlineCallbacks
    def send(self, build):
        # the only case when this function is called is when the user derives this class, overrides
        # send() and calls super().send(build) from there.
        yield self._send_impl(build, self._cached_report)

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        build = reports[0]['builds'][0]
        if self.send.__func__ is not GitLabStatusPush.send:
            warn_deprecated('2.9.0', 'send() in reporters has been deprecated. Use sendMessage()')
            self._cached_report = reports[0]
            yield self.send(build)
        else:
            yield self._send_impl(build, reports[0])

    @defer.inlineCallbacks
    def _send_impl(self, build, report):
        props = Properties.fromDict(build['properties'])
        props.master = self.master

        description = report.get('body', None)

        if build['complete']:
            state = {
                SUCCESS: 'success',
                WARNINGS: 'success',
                FAILURE: 'failed',
                SKIPPED: 'success',
                EXCEPTION: 'failed',
                RETRY: 'pending',
                CANCELLED: 'cancelled'
            }.get(build['results'], 'failed')
        else:
            state = 'running'

        context = yield props.render(self.context)

        sourcestamps = build['buildset']['sourcestamps']

        # FIXME: probably only want to report status for the last commit in the changeset
        for sourcestamp in sourcestamps:
            sha = sourcestamp['revision']
            if 'source_project_id' in props:
                proj_id = props['source_project_id']
            else:
                proj_id = yield self.getProjectId(sourcestamp)
            if proj_id is None:
                continue
            try:
                if 'source_branch' in props:
                    branch = props['source_branch']
                else:
                    branch = sourcestamp['branch']
                target_url = build['url']
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
                        '{repo} at {sha}: {message}'.format(
                            state=state,
                            repo=sourcestamp['repository'], sha=sha,
                            message=message))
                elif self.verbose:
                    log.msg(
                        'Status "{state}" sent for '
                        '{repo} at {sha}.'.format(
                            state=state, repo=sourcestamp['repository'], sha=sha))
            except Exception as e:
                log.err(
                    e,
                    'Failed to send status "{state}" for '
                    '{repo} at {sha}'.format(
                        state=state,
                        repo=sourcestamp['repository'], sha=sha
                    ))
