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
from buildbot.util import httpclientservice
from buildbot.util.giturlparse import giturlparse
from buildbot.warnings import warn_deprecated

HOSTED_BASE_URL = 'https://api.github.com'


class GitHubStatusPush(ReporterBase):
    name = "GitHubStatusPush"

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
    def reconfigService(self, token, startDescription=None, endDescription=None,
                        context=None, baseURL=None, verbose=False, wantProperties=True,
                        builders=None, debug=None, verify=None,
                        wantSteps=False, wantPreviousBuild=False, wantLogs=False, generators=None,
                        **kwargs):
        token = yield self.renderSecrets(token)
        self.debug = debug
        self.verify = verify
        self.verbose = verbose
        self.context = self.setup_context(context)

        if generators is None:
            generators = self._create_generators_from_old_args(builders, wantProperties, wantSteps,
                                                               wantPreviousBuild, wantLogs,
                                                               startDescription, endDescription)

        yield super().reconfigService(generators=generators, **kwargs)

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

    def setup_context(self, context):
        return context or Interpolate('buildbot/%(prop:buildername)s')

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
        # the only case when this function is called is when the user derives this class, overrides
        # send() and calls super().send(build) from there.
        yield self._send_impl(build, self._cached_report)

    def is_status_2xx(self, code):
        return code // 100 == 2

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        build = reports[0]['builds'][0]
        if self.send.__func__ is not GitHubStatusPush.send:
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
                FAILURE: 'failure',
                SKIPPED: 'success',
                EXCEPTION: 'error',
                RETRY: 'pending',
                CANCELLED: 'error'
            }.get(build['results'], 'error')
        else:
            state = 'pending'

        context = yield props.render(self.context)

        sourcestamps = build['buildset'].get('sourcestamps')
        if not sourcestamps:
            return

        for sourcestamp in sourcestamps:
            issue = None
            branch = props.getProperty('branch')
            if branch:
                m = re.search(r"refs/pull/([0-9]*)/(head|merge)", branch)
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

                if not self.is_status_2xx(response.code):
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

    def setup_context(self, context):
        return ''

    def _create_generators_from_old_args(self, builders, wantProperties, wantSteps,
                                         wantPreviousBuild, wantLogs,
                                         startDescription, endDescription):
        # wantProperties is ignored, because MessageFormatterRenderable always wants properties.
        # wantSteps and wantPreviousBuild are ignored ignored, because they are not used in
        # this reporter.
        start_formatter = MessageFormatterRenderable(startDescription)
        end_formatter = MessageFormatterRenderable(endDescription or 'Build done.')

        return [
            BuildStartEndStatusGenerator(builders=builders, add_logs=wantLogs,
                                         start_formatter=start_formatter,
                                         end_formatter=end_formatter)
        ]

    @defer.inlineCallbacks
    def _send_impl(self, build, report):
        if 'body' not in report or report['body'] is None:
            return
        yield super()._send_impl(build, report)

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
