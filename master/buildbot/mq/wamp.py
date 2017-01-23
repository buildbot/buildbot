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
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json

from autobahn.wamp.exception import TransportLost
from autobahn.wamp.types import PublishOptions
from autobahn.wamp.types import SubscribeOptions
from twisted.internet import defer
from twisted.python import log

from buildbot.mq import base
from buildbot.util import service
from buildbot.util import toJson


class WampMQ(service.ReconfigurableServiceMixin, base.MQBase):
    NAMESPACE = "org.buildbot.mq"

    def __init__(self):
        base.MQBase.__init__(self)

    def produce(self, routingKey, data):
        d = self._produce(routingKey, data)
        d.addErrback(
            log.err, "Problem while producing message on topic " + repr(routingKey))

    @classmethod
    def messageTopic(cls, routingKey):
        def ifNone(v, default):
            return default if v is None else v
        # replace None values by "" in routing key
        routingKey = [ifNone(key, "") for key in routingKey]
        # then join them with "dot", and add the prefix
        return cls.NAMESPACE + "." + ".".join(routingKey)

    @classmethod
    def routingKeyFromMessageTopic(cls, topic):
        # just split the topic, and remove the NAMESPACE prefix
        return tuple(topic[len(WampMQ.NAMESPACE) + 1:].split("."))

    def _produce(self, routingKey, data):
        _data = json.loads(json.dumps(data, default=toJson))
        options = PublishOptions(exclude_me=False)
        return self.master.wamp.publish(self.messageTopic(routingKey), _data, options=options)

    def startConsuming(self, callback, _filter, persistent_name=None):
        if persistent_name is not None:
            log.err('wampmq: persistant queues are not persisted: %s %s' %
                    (persistent_name, _filter))

        qr = QueueRef(callback)

        self._startConsuming(qr, callback, _filter)
        return defer.succeed(qr)

    def _startConsuming(self, qr, callback, _filter, persistent_name=None):
        return qr.subscribe(self.master.wamp, _filter)


class QueueRef(base.QueueRef):

    def __init__(self, callback):
        base.QueueRef.__init__(self, callback)
        self.unreg = None

    @defer.inlineCallbacks
    def subscribe(self, service, _filter):
        self.filter = _filter
        self.emulated = False
        options = dict(details_arg=str('details'))
        if None in _filter:
            options["match"] = "wildcard"
        options = SubscribeOptions(**options)
        _filter = WampMQ.messageTopic(_filter)
        self.unreg = yield service.subscribe(self.invoke, _filter, options=options)
        if self.callback is None:
            yield self.stopConsuming()

    def invoke(self, msg, details):
        if details.topic is not None:
            # in the case of a wildcard, wamp router sends the topic
            topic = WampMQ.routingKeyFromMessageTopic(details.topic)
        else:
            # in the case of an exact match, then we can use our own topic
            topic = self.filter
        return base.QueueRef.invoke(self, topic, msg)

    @defer.inlineCallbacks
    def stopConsuming(self):
        self.callback = None
        if self.unreg is not None:
            unreg = self.unreg
            self.unreg = None
            try:
                yield unreg.unsubscribe()
            except TransportLost:
                pass
