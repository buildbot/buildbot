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

import base64

try:
    import simplejson as json
    assert json
except ImportError:
    import json

from zope.interface import implements
from twisted.internet import defer, reactor
from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer
from twisted.python import log
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from buildbot.status.builder import SUCCESS, FAILURE, EXCEPTION
from buildbot.status.base import StatusReceiverMultiService
from buildbot.interfaces import IStatusReceiver


STATUS_TO_GITHUB_STATE_MAP = {
  SUCCESS: 'success',
  FAILURE: 'failure',
  EXCEPTION: 'error'
}


class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class StatusGithubCommit(StatusReceiverMultiService):
    implements(IStatusReceiver)

    """
    Publishes a build status using Github Status API
    (http://developer.github.com/v3/repos/statuses/).
    """

    def __init__(self, username, password, account, repository):
        """
        @username: Github account username.
        @password: Github account password.
        @account: Github account or organization name.
        @repository: Github repository name.
        """
        StatusReceiverMultiService.__init__(self)

        self.username = username
        self.password = password
        self.account = account
        self.repository = repository

        self._base_url = 'https://api.github.com/repos/%s/%s/statuses/' % \
                         (self.account, self.repository)
        self._auth_header = 'Basic %s' % (base64.encodestring('%s:%s' % \
                                          (self.username, self.password))[:-1])

    def startService(self):
        StatusReceiverMultiService.startService(self)
        self.status = self.parent.getStatus()
        self.status.subscribe(self)

    def builderAdded(self, name, builder):
        return self

    #### Events

    def buildStarted(self, builderName, build):
        revision = build.getProperty('revision')
        buildNumber = build.getNumber()

        state = 'pending'
        description = 'Build %s is building' % (buildNumber)
        buildUrl = self.status.getURLForThing(build)

        self._sendStatusToGithub(revision=revision, state=state,
                                 description=description,
                                 targetUrl=buildUrl)

        return self

    def buildFinished(self, builderName, build, results):
        builder = build.getBuilder()

        buildNumber = build.getNumber()
        revision = build.getProperty('got_revision')

        (start, end) = build.getTimes()
        elapsed = (end - start)

        state = STATUS_TO_GITHUB_STATE_MAP[results]
        description = 'Build %s finished in %.2f seconds' % (buildNumber,
                                                             elapsed)
        buildUrl = self.status.getURLForThing(build)
        self._sendStatusToGithub(revision=revision, state=state,
                                 description=description,
                                 targetUrl=buildUrl)

    def _sendStatusToGithub(self, revision, state, description=None,
                            targetUrl=None):
        if not revision:
            log.msg('Not sending status to Github because revision is empty')
            return

        log.msg('Sending status to Github...')

        data = {'state': state}

        if description:
            data['description'] = description

        if targetUrl:
            data['target_url'] = targetUrl

        payload = json.dumps(data)

        agent = Agent(reactor)
        url = self._base_url + str(revision)
        headers = Headers({'Authorization': [self._auth_header]})

        d = agent.request(method='POST', uri=url, headers=headers,
                          bodyProducer=StringProducer(payload))
        return d

# vim: set ts=4 sts=4 sw=4 et:
