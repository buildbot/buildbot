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

import pprint
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable

from twisted.internet import defer
from twisted.python import log

from buildbot.mq import base
from buildbot.util import service
from buildbot.util import tuplematch

if TYPE_CHECKING:
    from buildbot.config.master import MasterConfig


class SimpleMQ(service.ReconfigurableServiceMixin, base.MQBase):
    def __init__(self) -> None:
        super().__init__()
        self.qrefs: list[QueueRef] = []
        self.persistent_qrefs: dict[str, PersistentQueueRef] = {}
        self.debug = False

    def reconfigServiceWithBuildbotConfig(self, new_config: MasterConfig) -> Any:
        self.debug = new_config.mq.get('debug', False)  # type: ignore[assignment]
        return super().reconfigServiceWithBuildbotConfig(new_config)

    def produce(self, routingKey: tuple[str, ...], data: dict[str, Any]) -> None:
        if self.debug:
            log.msg(f"MSG: {routingKey}\n{pprint.pformat(data)}")
        for qref in self.qrefs:
            if tuplematch.matchTuple(routingKey, qref.filter):
                self.invokeQref(qref, routingKey, data)

    def startConsuming(  # type: ignore[override]
        self,
        callback: Callable[..., Any],
        filter: tuple[str | None, ...],
        persistent_name: str | None = None,
    ) -> defer.Deferred[QueueRef]:
        if any(not isinstance(k, str) and k is not None for k in filter):
            raise AssertionError(f"{filter} is not a filter")
        qref: QueueRef
        if persistent_name:
            if persistent_name in self.persistent_qrefs:
                pqref = self.persistent_qrefs[persistent_name]
                pqref.startConsuming(callback)
                qref = pqref
            else:
                new_pqref = PersistentQueueRef(self, callback, filter)
                self.qrefs.append(new_pqref)
                self.persistent_qrefs[persistent_name] = new_pqref
                qref = new_pqref
        else:
            qref = QueueRef(self, callback, filter)
            self.qrefs.append(qref)
        return defer.succeed(qref)


class QueueRef(base.QueueRef):
    __slots__ = ['filter', 'mq']

    def __init__(
        self,
        mq: SimpleMQ,
        callback: Callable[..., Any] | None,
        filter: tuple[str | None, ...],
    ) -> None:
        super().__init__(callback)
        self.mq = mq
        self.filter = filter

    def stopConsuming(self) -> None:
        self.callback = None
        try:
            self.mq.qrefs.remove(self)
        except ValueError:
            pass


class PersistentQueueRef(QueueRef):
    __slots__ = ['active', 'queue']

    def __init__(
        self,
        mq: SimpleMQ,
        callback: Callable[..., Any] | None,
        filter: tuple[str | None, ...],
    ) -> None:
        super().__init__(mq, callback, filter)
        self.queue: list[tuple[tuple[str, ...], dict[str, Any]]] = []

    def startConsuming(self, callback: Callable[..., Any]) -> None:
        self.callback = callback
        self.active = True

        # invoke for every message that was missed
        queue = self.queue
        self.queue = []
        for routingKey, data in queue:
            self.invoke(routingKey, data)

    def stopConsuming(self) -> None:
        self.callback = self.addToQueue
        self.active = False

    def addToQueue(self, routingKey: tuple[str, ...], data: dict[str, Any]) -> None:
        self.queue.append((routingKey, data))
