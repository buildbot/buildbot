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
from future.moves.urllib.parse import urlparse

from twisted.internet import defer

from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.results import SUCCESS
from buildbot.reporters import http
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger
from buildbot.util import unicode2bytes

log = Logger()

# Magic words understood by Bitbucket Server REST API
INPROGRESS = 'INPROGRESS'
SUCCESSFUL = 'SUCCESSFUL'
FAILED = 'FAILED'
STATUS_API_URL = '/rest/build-status/1.0/commits/{sha}'
COMMENT_API_URL = '/rest/api/1.0{path}/comments'
HTTP_PROCESSED = 204
HTTP_CREATED = 201


class BitbucketServerStatusPush(http.HttpStatusPushBase):
    name = "BitbucketServerStatusPush"

    @defer.inlineCallbacks
    def reconfigService(self, base_url, user, password, key=None,
                        statusName=None, startDescription=None,
                        endDescription=None, verbose=False, **kwargs):
        yield http.HttpStatusPushBase.reconfigService(
            self, wantProperties=True, **kwargs)
        self.key = key or Interpolate('%(prop:buildername)s')
        self.statusName = statusName
        self.endDescription = endDescription or 'Build done.'
        self.startDescription = startDescription or 'Build started.'
        self.verbose = verbose
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url, auth=(user, password),
            debug=self.debug, verify=self.verify)

    @defer.inlineCallbacks
    def send(self, build):
        props = Properties.fromDict(build['properties'])
        results = build['results']
        if build['complete']:
            status = SUCCESSFUL if results == SUCCESS else FAILED
            description = self.endDescription
        else:
            status = INPROGRESS
            description = self.startDescription

        # got_revision could be a string, a dictionary or None
        got_revision = props.getProperty('got_revision', None)
        for sourcestamp in build['buildset']['sourcestamps']:
            sha = sourcestamp['revision']

            if sha is None:
                if isinstance(got_revision, dict):
                    sha = got_revision[sourcestamp['codebase']]
                else:
                    sha = got_revision

            if sha is None:
                log.error("Unable to get the commit hash")
                continue

            key = yield props.render(self.key)
            payload = {
                'state': status,
                'url': build['url'],
                'key': key,
            }
            if description:
                payload['description'] = yield props.render(description)
            if self.statusName:
                payload['name'] = yield props.render(self.statusName)
            response = yield self._http.post(
                STATUS_API_URL.format(sha=sha), json=payload)
            if response.code == HTTP_PROCESSED:
                if self.verbose:
                    log.info('Status "{status}" sent for {sha}.',
                             status=status, sha=sha)
            else:
                content = yield response.content()
                log.error("{code}: Unable to send Bitbucket Server status: {content}",
                          code=response.code, content=content)


class BitbucketServerPRCommentPush(http.HttpStatusPushBase):
    name = "BitbucketServerPRCommentPush"

    @defer.inlineCallbacks
    def reconfigService(self, base_url, user, password, text=None,
                        verbose=False, **kwargs):
        yield http.HttpStatusPushBase.reconfigService(
            self, wantProperties=True, **kwargs)
        self.text = text or Interpolate('Builder: %(prop:buildername)s '
                                        'Status: %(prop:statustext)s')
        self.verbose = verbose
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url, auth=(user, password),
            debug=self.debug, verify=self.verify)

    @defer.inlineCallbacks
    def send(self, build):
        if build['complete'] and "pullrequesturl" in build['properties']:
            yield self.sendPullRequestComment(build)

    @defer.inlineCallbacks
    def sendPullRequestComment(self, build):
        props = Properties.fromDict(build['properties'])
        pr_url = props.getProperty("pullrequesturl")
        # we assume that the PR URL is well-formed as it comes from a PR event
        path = urlparse(unicode2bytes(pr_url)).path
        status = "SUCCESS" if build['results'] == SUCCESS else "FAILED"
        props.setProperty('statustext', status, self.name)
        props.setProperty('url', build['url'], self.name)
        comment_text = yield props.render(self.text)
        payload = {'text': comment_text}
        response = yield self._http.post(
            COMMENT_API_URL.format(path=path), json=payload)

        if response.code == HTTP_CREATED:
            if self.verbose:
                log.info('{comment} sent to {url}',
                         comment=comment_text, url=pr_url)
        else:
            content = yield response.content()
            log.error("{code}: Unable to send a comment: {content}",
                      code=response.code, content=content)
