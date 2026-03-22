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

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable

from autobahn.wamp.exception import TransportLost
from autobahn.wamp.types import EventDetails
from autobahn.wamp.types import PublishOptions
from autobahn.wamp.types import SubscribeOptions
from twisted.internet import defer
from twisted.python import log

from buildbot.mq import base
from buildbot.util import service
from buildbot.util import toJson

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class WampMQ(service.ReconfigurableServiceMixin, base.MQBase):
    NAMESPACE = "org.buildbot.mq"

    def produce(self, routingKey: tuple[str, ...], data: dict[str, Any]) -> None:
        d = self._produce(routingKey, data)
        d.addErrback(log.err, "Problem while producing message on topic " + repr(routingKey))

    @classmethod
    def messageTopic(cls, routingKey: tuple[str | None, ...]) -> str:
        def ifNone(v: str | None, default: str) -> str:
            return default if v is None else v

        # replace None values by "" in routing key
        routingKey = [ifNone(key, "") for key in routingKey]  # type: ignore[assignment]
        # then join them with "dot", and add the prefix
        return cls.NAMESPACE + "." + ".".join(routingKey)  # type: ignore[arg-type]

    @classmethod
    def routingKeyFromMessageTopic(cls, topic: str) -> tuple[str, ...]:
        # just split the topic, and remove the NAMESPACE prefix
        return tuple(topic[len(WampMQ.NAMESPACE) + 1 :].split("."))

    def _produce(self, routingKey: tuple[str, ...], data: dict[str, Any]) -> defer.Deferred[Any]:
        _data = json.loads(json.dumps(data, default=toJson))
        options = PublishOptions(exclude_me=False)
        return self.master.wamp.publish(self.messageTopic(routingKey), _data, options=options)

    def startConsuming(  # type: ignore[override]
        self,
        callback: Callable[..., Any],
        _filter: tuple[str | None, ...],
        persistent_name: str | None = None,
    ) -> defer.Deferred[QueueRef]:
        if persistent_name is not None:
            log.err(f'wampmq: persistent queues are not persisted: {persistent_name} {_filter}')

        qr = QueueRef(self, callback)

        self._startConsuming(qr, callback, _filter)
        return defer.succeed(qr)

    def _startConsuming(
        self,
        qr: QueueRef,
        callback: Callable[..., Any],
        _filter: tuple[str | None, ...],
        persistent_name: str | None = None,
    ) -> defer.Deferred[None]:
        return qr.subscribe(self.master.wamp, self, _filter)


class QueueRef(base.QueueRef):
    def __init__(self, mq: WampMQ, callback: Callable[..., Any] | None) -> None:
        super().__init__(callback)
        self.unreg: Any = None
        self.mq = mq

    @defer.inlineCallbacks
    def subscribe(
        self,
        connector_service: Any,
        wamp_service: WampMQ,
        _filter: tuple[str | None, ...],
    ) -> InlineCallbacksType[None]:
        self.filter = _filter
        self.emulated = False
        options: dict[str, str] = {"details_arg": 'details'}
        if None in _filter:
            options["match"] = "wildcard"
        options = SubscribeOptions(**options)  # type: ignore[assignment]
        _filter = WampMQ.messageTopic(_filter)  # type: ignore[assignment]
        self.unreg = yield connector_service.subscribe(self.wampInvoke, _filter, options=options)
        if self.callback is None:
            yield self.stopConsuming()

    def wampInvoke(self, msg: dict[str, Any], details: EventDetails) -> None:
        if details.topic is not None:
            # in the case of a wildcard, wamp router sends the topic
            topic = WampMQ.routingKeyFromMessageTopic(details.topic)
        else:
            # in the case of an exact match, then we can use our own topic
            topic = self.filter  # type: ignore[assignment]
        self.mq.invokeQref(self, topic, msg)

    @defer.inlineCallbacks
    def stopConsuming(self) -> InlineCallbacksType[None]:
        self.callback = None
        if self.unreg is not None:
            unreg = self.unreg
            self.unreg = None
            try:
                yield unreg.unsubscribe()
            except TransportLost:
                pass
            except Exception as e:
                log.err(e, 'When unsubscribing MQ connection ' + str(unreg))
