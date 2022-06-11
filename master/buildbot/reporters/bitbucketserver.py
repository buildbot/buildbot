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
from urllib.parse import urlparse

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.plugins import util
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.results import SUCCESS
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.message import MessageFormatterRenderable
from buildbot.util import bytes2unicode
from buildbot.util import httpclientservice
from buildbot.util import unicode2bytes

from .utils import merge_reports_prop

# Magic words understood by Bitbucket Server REST API
INPROGRESS = 'INPROGRESS'
SUCCESSFUL = 'SUCCESSFUL'
FAILED = 'FAILED'
STATUS_API_URL = '/rest/build-status/1.0/commits/{sha}'
STATUS_CORE_API_URL = '/rest/api/1.0/projects/{proj_key}/repos/{repo_slug}/commits/{sha}/builds'
COMMENT_API_URL = '/rest/api/1.0{path}/comments'
HTTP_PROCESSED = 204
HTTP_CREATED = 201


class BitbucketServerStatusPush(ReporterBase):
    name = "BitbucketServerStatusPush"

    def checkConfig(self, base_url, user, password, key=None, statusName=None, verbose=False,
                    debug=None, verify=None, generators=None, **kwargs):

        if generators is None:
            generators = self._create_default_generators()

        super().checkConfig(generators=generators, **kwargs)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self, base_url, user, password, key=None, statusName=None, verbose=False,
                        debug=None, verify=None, generators=None, **kwargs):
        user, password = yield self.renderSecrets(user, password)
        self.debug = debug
        self.verify = verify
        self.verbose = verbose

        if generators is None:
            generators = self._create_default_generators()

        yield super().reconfigService(generators=generators, **kwargs)

        self.key = key or Interpolate('%(prop:buildername)s')
        self.context = statusName
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url, auth=(user, password),
            debug=self.debug, verify=self.verify)

    def _create_default_generators(self):
        start_formatter = MessageFormatterRenderable('Build started.')
        end_formatter = MessageFormatterRenderable('Build done.')

        return [
            BuildStartEndStatusGenerator(start_formatter=start_formatter,
                                         end_formatter=end_formatter)
        ]

    def createStatus(self, sha, state, url, key, description=None, context=None):
        payload = {
            'state': state,
            'url': url,
            'key': key,
        }

        if description:
            payload['description'] = description
        if context:
            payload['name'] = context

        return self._http.post(STATUS_API_URL.format(sha=sha), json=payload)

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        report = reports[0]
        build = reports[0]['builds'][0]

        props = Properties.fromDict(build['properties'])
        props.master = self.master

        description = report.get('body', None)

        results = build['results']
        if build['complete']:
            state = SUCCESSFUL if results == SUCCESS else FAILED
        else:
            state = INPROGRESS

        key = yield props.render(self.key)
        context = yield props.render(self.context) if self.context else None

        sourcestamps = build['buildset']['sourcestamps']

        for sourcestamp in sourcestamps:
            try:
                sha = sourcestamp['revision']

                if sha is None:
                    log.msg("Unable to get the commit hash")
                    continue

                url = build['url']
                res = yield self.createStatus(
                    sha=sha,
                    state=state,
                    url=url,
                    key=key,
                    description=description,
                    context=context
                )

                if res.code not in (HTTP_PROCESSED,):
                    content = yield res.content()
                    log.msg(f"{res.code}: Unable to send Bitbucket Server status: "
                            f"{content}")
                elif self.verbose:
                    log.msg(f'Status "{state}" sent for {sha}.')
            except Exception as e:
                log.err(
                    e,
                    f"Failed to send status '{state}' for {sourcestamp['repository']} at {sha}")


class BitbucketServerCoreAPIStatusPush(ReporterBase):
    name = "BitbucketServerCoreAPIStatusPush"
    secrets = ["token", "auth"]

    def checkConfig(self, base_url, token=None, auth=None,
                    statusName=None, statusSuffix=None, key=None, parentName=None,
                    buildNumber=None, ref=None, duration=None,
                    testResults=None, verbose=False, debug=None, verify=None, generators=None,
                    **kwargs):

        if generators is None:
            generators = self._create_default_generators()

        super().checkConfig(generators=generators, **kwargs)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

        if not base_url:
            config.error("Parameter base_url has to be given")
        if token is not None and auth is not None:
            config.error("Only one authentication method can be given "
                         "(token or auth)")

    @defer.inlineCallbacks
    def reconfigService(self, base_url, token=None, auth=None,
                        statusName=None, statusSuffix=None, key=None, parentName=None,
                        buildNumber=None, ref=None, duration=None,
                        testResults=None, verbose=False, debug=None, verify=None, generators=None,
                        **kwargs):
        self.status_name = statusName
        self.status_suffix = statusSuffix
        self.key = key or Interpolate('%(prop:buildername)s')
        self.parent_name = parentName
        self.build_number = buildNumber or Interpolate('%(prop:buildnumber)s')
        self.ref = ref
        self.duration = duration

        self.debug = debug
        self.verify = verify
        self.verbose = verbose

        if generators is None:
            generators = self._create_default_generators()

        yield super().reconfigService(generators=generators, **kwargs)

        if testResults:
            self.test_results = testResults
        else:
            @util.renderer
            def r_testresults(props):
                failed = props.getProperty("tests_failed", 0)
                skipped = props.getProperty("tests_skipped", 0)
                successful = props.getProperty("tests_successful", 0)
                if any([failed, skipped, successful]):
                    return {
                        "failed": failed,
                        "skipped": skipped,
                        "successful": successful
                    }
                return None
            self.test_results = r_testresults

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url, auth=auth, headers=headers, debug=debug,
            verify=verify)

    def _create_default_generators(self):
        start_formatter = MessageFormatterRenderable('Build started.')
        end_formatter = MessageFormatterRenderable('Build done.')

        return [
            BuildStartEndStatusGenerator(start_formatter=start_formatter,
                                         end_formatter=end_formatter)
        ]

    def createStatus(self, proj_key, repo_slug, sha, state, url, key, parent,
                     build_number, ref, description, name, duration,
                     test_results):
        payload = {
            'state': state,
            'url': url,
            'key': key,
            'parent': parent,
            'ref': ref,
            'buildNumber': build_number,
            'description': description,
            'name': name,
            'duration': duration,
            'testResults': test_results
        }

        if self.verbose:
            log.msg(f"Sending payload: '{payload}' for {proj_key}/{repo_slug} {sha}.")

        _url = STATUS_CORE_API_URL.format(proj_key=proj_key, repo_slug=repo_slug,
                                          sha=sha)
        return self._http.post(_url, json=payload)

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        report = reports[0]
        build = reports[0]['builds'][0]

        props = Properties.fromDict(build['properties'])
        props.master = self.master

        description = report.get('body', None)

        duration = None
        test_results = None
        if build['complete']:
            state = SUCCESSFUL if build['results'] == SUCCESS else FAILED
            if self.duration:
                duration = yield props.render(self.duration)
            else:
                td = build['complete_at'] - build['started_at']
                duration = int(td.seconds * 1000)
            if self.test_results:
                test_results = yield props.render(self.test_results)
        else:
            state = INPROGRESS
            duration = None

        parent_name = (build['parentbuilder'] or {}).get('name')
        if self.parent_name:
            parent = yield props.render(self.parent_name)
        elif parent_name:
            parent = parent_name
        else:
            parent = build['builder']['name']

        if self.status_name:
            status_name = yield props.render(self.status_name)
        else:
            status_name = f'{props.getProperty("buildername")} #{props.getProperty("buildnumber")}'
            if parent_name:
                status_name = \
                    f"{parent_name} #{build['parentbuild']['number']} \u00BB {status_name}"
        if self.status_suffix:
            status_name = status_name + (yield props.render(self.status_suffix))

        key = yield props.render(self.key)
        build_number = yield props.render(self.build_number)
        url = build['url']

        sourcestamps = build['buildset']['sourcestamps']

        for sourcestamp in sourcestamps:
            try:
                ssid = sourcestamp.get('ssid')
                sha = sourcestamp.get('revision')
                branch = sourcestamp.get('branch')
                repo = sourcestamp.get('repository')

                if not sha:
                    log.msg(f"Unable to get the commit hash for SSID: {ssid}")
                    continue

                ref = None
                if self.ref is None:
                    if branch is not None:
                        if branch.startswith("refs/"):
                            ref = branch
                        else:
                            ref = f"refs/heads/{branch}"
                else:
                    ref = yield props.render(self.ref)

                if not ref:
                    log.msg(f"WARNING: Unable to resolve ref for SSID: {ssid}. "
                            "Build status will not be visible on Builds or "
                            "PullRequest pages only for commits")

                r = re.search(r"^.*?/([^/]+)/([^/]+?)(?:\.git)?$", repo or "")
                if r:
                    proj_key = r.group(1)
                    repo_slug = r.group(2)
                else:
                    log.msg(f"Unable to parse repository info from '{repo}' for SSID: {ssid}")
                    continue

                res = yield self.createStatus(
                    proj_key=proj_key,
                    repo_slug=repo_slug,
                    sha=sha,
                    state=state,
                    url=url,
                    key=key,
                    parent=parent,
                    build_number=build_number,
                    ref=ref,
                    description=description,
                    name=status_name,
                    duration=duration,
                    test_results=test_results
                )

                if res.code not in (HTTP_PROCESSED,):
                    content = yield res.content()
                    log.msg(f"{res.code}: Unable to send Bitbucket Server status for "
                            f"{proj_key}/{repo_slug} {sha}: {content}")
                elif self.verbose:
                    log.msg(f'Status "{state}" sent for {proj_key}/{repo_slug} {sha}')
            except Exception as e:
                log.err(
                    e,
                    f'Failed to send status "{state}" for {proj_key}/{repo_slug} {sha}')


class BitbucketServerPRCommentPush(ReporterBase):
    name = "BitbucketServerPRCommentPush"

    @defer.inlineCallbacks
    def reconfigService(self, base_url, user, password,
                        verbose=False, debug=None, verify=None, generators=None, **kwargs):
        user, password = yield self.renderSecrets(user, password)
        self.verbose = verbose

        if generators is None:
            generators = self._create_default_generators()

        yield super().reconfigService(generators=generators, **kwargs)
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url, auth=(user, password),
            debug=debug, verify=verify)

    def checkConfig(self, base_url, user, password,
                    verbose=False, debug=None, verify=None, generators=None, **kwargs):

        if generators is None:
            generators = self._create_default_generators()

        super().checkConfig(generators=generators, **kwargs)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    def _create_default_generators(self):
        return [BuildStatusGenerator()]

    def sendComment(self, pr_url, text):
        path = urlparse(unicode2bytes(pr_url)).path
        payload = {'text': text}
        return self._http.post(COMMENT_API_URL.format(
            path=bytes2unicode(path)), json=payload)

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        body = merge_reports_prop(reports, 'body')
        builds = merge_reports_prop(reports, 'builds')

        pr_urls = set()
        for build in builds:
            props = Properties.fromDict(build['properties'])
            pr_urls.add(props.getProperty("pullrequesturl"))

        for pr_url in pr_urls:
            if pr_url is None:
                continue
            try:
                res = yield self.sendComment(
                    pr_url=pr_url,
                    text=body
                )
                if res.code not in (HTTP_CREATED,):
                    content = yield res.content()
                    log.msg(f"{res.code}: Unable to send a comment: {content}")
                elif self.verbose:
                    log.msg(f'Comment sent to {pr_url}')
            except Exception as e:
                log.err(e, f'Failed to send a comment to "{pr_url}"')
