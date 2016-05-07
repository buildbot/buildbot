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

import abc

from future.utils import iteritems
from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.reporters import utils
from buildbot.util import service

# use the 'requests' lib: http://python-requests.org
try:
    import txrequests
except ImportError:
    txrequests = None


class HttpStatusPushBase(service.BuildbotService):
    neededDetails = dict()

    def checkConfig(self, *args, **kwargs):
        service.BuildbotService.checkConfig(self)
        if txrequests is None:
            config.error("Please install txrequests and requests to use %s (pip install txrequest)" %
                         (self.__class__,))
        if not isinstance(kwargs.get('builders'), (type(None), list)):
            config.error("builders must be a list or None")

    @defer.inlineCallbacks
    def reconfigService(self, builders=None, **kwargs):
        yield service.BuildbotService.reconfigService(self)
        self.builders = builders
        for k, v in iteritems(kwargs):
            if k.startswith("want"):
                self.neededDetails[k] = v

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
        return self.getMoreInfoAndSend(build)

    def buildFinished(self, key, build):
        return self.getMoreInfoAndSend(build)

    def filterBuilds(self, build):
        if self.builders is not None:
            return build['builder']['name'] in self.builders
        return True

    @defer.inlineCallbacks
    def getMoreInfoAndSend(self, build):
        yield utils.getDetailsForBuild(self.master, build, **self.neededDetails)
        if self.filterBuilds(build):
            yield self.send(build)

    @abc.abstractmethod
    def send(self, build):
        pass


class HttpStatusPush(HttpStatusPushBase):
    name = "HttpStatusPush"

    def checkConfig(self, serverUrl, user, password, **kwargs):
        HttpStatusPushBase.checkConfig(self, **kwargs)
        if txrequests is None:
            config.error("Please install txrequests and requests to use %s (pip install txrequest)" %
                         (self.__class__,))

    def reconfigService(self, serverUrl, user, password, **kwargs):
        HttpStatusPushBase.reconfigService(self, **kwargs)
        self.serverUrl = serverUrl
        self.auth = (user, password)

    @defer.inlineCallbacks
    def send(self, build):
        response = yield self.session.post(self.serverUrl, build, auth=self.auth)
        if response.status_code != 200:
            log.msg("%s: unable to upload status: %s" %
                    (response.status_code, response.content))
