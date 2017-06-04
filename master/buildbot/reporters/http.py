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
from future.utils import iteritems

import abc
import copy

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.reporters import utils
from buildbot.util import httpclientservice
from buildbot.util import service


class HttpStatusPushBase(service.BuildbotService):
    neededDetails = dict()

    def checkConfig(self, *args, **kwargs):
        service.BuildbotService.checkConfig(self)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)
        if not isinstance(kwargs.get('builders'), (type(None), list)):
            config.error("builders must be a list or None")

    @defer.inlineCallbacks
    def reconfigService(self, builders=None, debug=None, verify=None, **kwargs):
        yield service.BuildbotService.reconfigService(self)
        self.debug = debug
        self.verify = verify
        self.builders = builders
        self.neededDetails = copy.copy(self.neededDetails)
        for k, v in iteritems(kwargs):
            if k.startswith("want"):
                self.neededDetails[k] = v

    @defer.inlineCallbacks
    def startService(self):
        yield service.BuildbotService.startService(self)

        startConsuming = self.master.mq.startConsuming
        self._buildCompleteConsumer = yield startConsuming(
            self.buildFinished,
            ('builds', None, 'finished'))

        self._buildStartedConsumer = yield startConsuming(
            self.buildStarted,
            ('builds', None, 'new'))

    def stopService(self):
        self._buildCompleteConsumer.stopConsuming()
        self._buildStartedConsumer.stopConsuming()

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

    def checkConfig(self, serverUrl, user=None, password=None, auth=None, format_fn=None, **kwargs):
        if user is not None and auth is not None:
            config.error("Only one of user/password or auth must be given")
        if user is not None:
            config.warnDeprecated("0.9.1", "user/password is deprecated, use 'auth=(user, password)'")
        if (format_fn is not None) and not callable(format_fn):
            config.error("format_fn must be a function")
        HttpStatusPushBase.checkConfig(self, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self, serverUrl, user=None, password=None, auth=None, format_fn=None, **kwargs):
        yield HttpStatusPushBase.reconfigService(self, **kwargs)
        if user is not None:
            auth = (user, password)
        if format_fn is None:
            self.format_fn = lambda x: x
        else:
            self.format_fn = format_fn
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, serverUrl, auth=auth)

    @defer.inlineCallbacks
    def send(self, build):
        response = yield self._http.post("", json=self.format_fn(build))
        if response.code != 200:
            log.msg("%s: unable to upload status: %s" %
                    (response.code, response.content))
