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

from typing import TYPE_CHECKING
from typing import Any
from typing import Callable

from twisted.internet import defer
from twisted.python.reflect import namedObject

from buildbot.util import service

if TYPE_CHECKING:
    from buildbot.config.master import MasterConfig
    from buildbot.mq import base
    from buildbot.util.twisted import InlineCallbacksType


class MQConnector(service.ReconfigurableServiceMixin, service.AsyncMultiService):
    classes = {
        'simple': {
            'class': "buildbot.mq.simple.SimpleMQ",
            'keys': set(['debug']),
        },
        'wamp': {
            'class': "buildbot.mq.wamp.WampMQ",
            'keys': set(["router_url", "realm", "wamp_debug_level"]),
        },
    }
    name: str | None = 'mq'  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.impl: base.MQBase | None = None  # set in setup
        self.impl_type: str | None = None  # set in setup

    @defer.inlineCallbacks
    def setup(self) -> InlineCallbacksType[None]:
        assert not self.impl

        # imports are done locally so that we don't try to import
        # implementation-specific modules unless they're required.
        typ = self.master.config.mq['type']
        assert typ in self.classes  # this is checked by MasterConfig
        self.impl_type = typ
        cls = namedObject(self.classes[typ]['class'])
        self.impl = cls()

        # set up the impl as a child service
        yield self.impl.setServiceParent(self)

        # configure it (early)
        self.impl.reconfigServiceWithBuildbotConfig(self.master.config)  # type: ignore[union-attr]

        # copy the methods onto this object for ease of access
        self.produce = self.impl.produce  # type: ignore[method-assign,assignment]
        self.startConsuming = self.impl.startConsuming  # type: ignore[method-assign]
        self.waitUntilEvent = self.impl.waitUntilEvent

    def reconfigServiceWithBuildbotConfig(self, new_config: MasterConfig) -> Any:
        # double-check -- the master ensures this in config checks
        assert self.impl_type == new_config.mq['type']

        return super().reconfigServiceWithBuildbotConfig(new_config)

    def produce(self, routing_key: tuple[str, ...], data: dict[str, Any]) -> None:
        # will be patched after configuration to point to the running
        # implementation's method
        raise NotImplementedError

    def startConsuming(
        self,
        callback: Callable[..., Any],
        filter: tuple[str | None, ...],
        persistent_name: str | None = None,
    ) -> defer.Deferred[base.QueueRef]:
        # will be patched after configuration to point to the running
        # implementation's method
        raise NotImplementedError
