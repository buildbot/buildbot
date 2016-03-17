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

from buildbot import config
from buildbot.reporters import utils
from buildbot.util import service

from twisted.internet import defer
from twisted.python import log

# use the 'requests' lib: http://python-requests.org
try:
    import txrequests
except ImportError:
    txrequests = None


class HttpStatusPush(service.BuildbotService):
    name = "HttpStatusPush"

    def __init__(self, serverUrl, user, password):
        service.BuildbotService.__init__(self)
        self.serverUrl = serverUrl
        self.auth = (user, password)
        if txrequests is None:
            config.error("Please install txrequests and requests to use %s (pip install txrequest)" %
                         (self.__class__,))

    @defer.inlineCallbacks
    def send(self, build):
        yield utils.getDetailsForBuild(self.master, build)
        build_url = utils.getURLForBuild(self.master, build['builderid'], build['number'])
        response = yield self.session.post(self.serverUrl, {'build': build, 'url': build_url}, auth=self.auth)
        if response.status != 200:
            log.msg("%s: unable to upload stash status: %s", response.status, response.content)

    def sessionFactory(self):
        """txrequests mocking endpoint"""
        return txrequests.Session()

    @defer.inlineCallbacks
    def startService(self):
        self.session = self.sessionFactory()
        yield service.BuildbotService.startService(self)
        startConsuming = self.master.mq.startConsuming

        self._buildCompleteConsumer = yield startConsuming(
            self.buildFinished,
            ('builds', None, 'finished'))

        self._buildStartedConsumer = yield startConsuming(
            self.buildStarted,
            ('builds', None, 'started'))

    def stopService(self):
        self._buildCompleteConsumer.stopConsuming()
        self._buildStartedConsumer.stopConsuming()
        self.session.close()

    def buildStarted(self, key, build):
        return self.send(build)

    def buildFinished(self, key, build):
        return self.send(build)
