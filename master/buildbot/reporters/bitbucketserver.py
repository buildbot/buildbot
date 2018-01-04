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
from twisted.python import log

from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.results import SUCCESS
from buildbot.reporters import http
from buildbot.reporters import notifier
from buildbot.util import bytes2NativeString
from buildbot.util import httpclientservice
from buildbot.util import unicode2bytes
from buildbot.util import unicode2NativeString

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
        user, password = yield self.renderSecrets(user, password)
        yield http.HttpStatusPushBase.reconfigService(
            self, wantProperties=True, **kwargs)
        self.key = key or Interpolate('%(prop:buildername)s')
        self.context = statusName
        self.endDescription = endDescription or 'Build done.'
        self.startDescription = startDescription or 'Build started.'
        self.verbose = verbose
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url, auth=(user, password),
            debug=self.debug, verify=self.verify)

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
    def send(self, build):
        props = Properties.fromDict(build['properties'])
        props.master = self.master

        results = build['results']
        if build['complete']:
            state = SUCCESSFUL if results == SUCCESS else FAILED
            description = self.endDescription
        else:
            state = INPROGRESS
            description = self.startDescription

        key = yield props.render(self.key)
        description = yield props.render(description) if description else None
        context = yield props.render(self.context) if self.context else None

        sourcestamps = build['buildset']['sourcestamps']

        for sourcestamp in sourcestamps:
            try:
                sha = unicode2NativeString(sourcestamp['revision'])

                if sha is None:
                    log.msg("Unable to get the commit hash")
                    continue

                key = unicode2NativeString(key)
                state = unicode2NativeString(state)
                url = unicode2NativeString(build['url'])
                key = unicode2NativeString(key)
                description = unicode2NativeString(description)
                context = unicode2NativeString(context)

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
                    log.msg("{code}: Unable to send Bitbucket Server status: "
                        "{content}".format(code=res.code, content=content))
                elif self.verbose:
                    log.msg('Status "{state}" sent for {sha}.'.format(
                        state=state, sha=sha))
            except Exception as e:
                log.err(
                    e,
                    'Failed to send status "{state}" for '
                    '{repo} at {sha}'.format(
                        state=state,
                        repo=sourcestamp['repository'], sha=sha
                    ))


class BitbucketServerPRCommentPush(notifier.NotifierBase):
    name = "BitbucketServerPRCommentPush"

    @defer.inlineCallbacks
    def reconfigService(self, base_url, user, password, messageFormatter=None,
                        verbose=False, debug=None, verify=None, **kwargs):
        user, password = yield self.renderSecrets(user, password)
        yield notifier.NotifierBase.reconfigService(
            self, messageFormatter=messageFormatter, watchedWorkers=None,
            messageFormatterMissingWorker=None, subject='', addLogs=False,
            addPatch=False, **kwargs)
        self.verbose = verbose
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url, auth=(user, password),
            debug=debug, verify=verify)

    def checkConfig(self, base_url, user, password, messageFormatter=None,
                    verbose=False, debug=None, verify=None, **kwargs):

        notifier.NotifierBase.checkConfig(self,
                                          messageFormatter=messageFormatter,
                                          watchedWorkers=None,
                                          messageFormatterMissingWorker=None,
                                          subject='',
                                          addLogs=False,
                                          addPatch=False,
                                          **kwargs)

    def isMessageNeeded(self, build):
        if 'pullrequesturl' in build['properties']:
            return notifier.NotifierBase.isMessageNeeded(self, build)
        return False

    def workerMissing(self, key, worker):
        # a comment is always associated to a change
        pass

    def sendComment(self, pr_url, text):
        path = urlparse(unicode2bytes(pr_url)).path
        payload = {'text': text}
        return self._http.post(COMMENT_API_URL.format(
            path=bytes2NativeString(path)), json=payload)

    @defer.inlineCallbacks
    def sendMessage(self, body, subject=None, type=None, builderName=None,
                    results=None, builds=None, users=None, patches=None,
                    logs=None, worker=None):
        pr_urls = set()
        for build in builds:
            props = Properties.fromDict(build['properties'])
            pr_urls.add(props.getProperty("pullrequesturl"))
        for pr_url in pr_urls:
            try:
                res = yield self.sendComment(
                    pr_url=pr_url,
                    text=body
                )
                if res.code not in (HTTP_CREATED,):
                    content = yield res.content()
                    log.msg("{code}: Unable to send a comment: "
                        "{content}".format(code=res.code, content=content))
                elif self.verbose:
                    log.msg('Comment sent to {url}'.format(url=pr_url))
            except Exception as e:
                log.err(e, 'Failed to send a comment to "{}"'.format(pr_url))
