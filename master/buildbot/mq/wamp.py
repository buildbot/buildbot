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

from autobahn.wamp.types import PublishOptions
from autobahn.wamp.types import SubscribeOptions
from twisted.internet import defer

from buildbot.mq import base
from buildbot.util import service
from buildbot.util import toJson

import json


class WampMQ(service.ReconfigurableServiceMixin, base.MQBase):
    NAMESPACE = u"org.buildbot.mq"

    def __init__(self, master):
        base.MQBase.__init__(self, master)

    def produce(self, routingKey, data):
        self._produce(routingKey, data)

    @classmethod
    def messageTopic(cls, routingKey):
        routingKey = [key if key is not None else u"" for key in routingKey]
        return cls.NAMESPACE + u"." + u".".join(routingKey)

    @defer.inlineCallbacks
    def _produce(self, routingKey, data):
        service = yield self.master.wamp.getService()
        _data = json.loads(json.dumps(data, default=toJson))
        options = PublishOptions(excludeMe=False)
        service.publish(self.messageTopic(routingKey), dict(topic=routingKey, data=_data), options=options)

    def startConsuming(self, callback, _filter, persistent_name=None):
        if persistent_name is not None:
            print "wampmq: persistant queues are not persisted!", persistent_name, _filter

        qr = QueueRef(callback)
        self._startConsuming(qr, callback, _filter)
        return defer.succeed(qr)

    @defer.inlineCallbacks
    def _startConsuming(self, qr, callback, _filter, persistent_name=None):
        service = yield self.master.wamp.getService()
        yield qr.subscribe(service, _filter)


class QueueRef(base.QueueRef):

    def __init__(self, callback):
        base.QueueRef.__init__(self, callback)
        self.unreg = None

    @defer.inlineCallbacks
    def subscribe(self, service, _filter):
        self.filter = _filter
        self.emulated = False
        if None in _filter:
            options = SubscribeOptions(match=u"wildcard")
        else:
            options = None
        _filter = WampMQ.messageTopic(_filter)
        self.unreg = yield service.subscribe(self.invoke, _filter, options=options)
        if self.callback is None:
            yield self.stopConsuming()

    def invoke(self, msg):
        return base.QueueRef.invoke(self, msg[u'topic'], msg[u'data'])

    def stopConsuming(self):
        self.callback = None
        if self.unreg is not None:
            unreg = self.unreg
            self.unreg = None
            return unreg.unsubscribe()
