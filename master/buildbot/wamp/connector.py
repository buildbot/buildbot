# This file is part of .  Buildbot is free software: you can
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
# Copyright  Team Members
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import txaio
from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.wamp import Service
from autobahn.wamp.exception import TransportLost
from twisted.internet import defer
from twisted.logger import Logger
from twisted.python import log

from buildbot.util import bytes2unicode
from buildbot.util import service

if TYPE_CHECKING:
    from autobahn.wamp.request import Publication
    from autobahn.wamp.request import Subscription
    from autobahn.wamp.types import CloseDetails
    from autobahn.wamp.types import SessionDetails
    from twisted.python.failure import Failure

    from buildbot.util.twisted import InlineCallbacksType


class MasterService(ApplicationSession, service.AsyncMultiService):
    """
    concatenation of all the wamp services of buildbot
    """

    def __init__(self, config: Any) -> None:
        # Cannot use super() here.
        # We must explicitly call both parent constructors.
        ApplicationSession.__init__(self, config)
        service.AsyncMultiService.__init__(self)
        self.leaving = False
        self.setServiceParent(config.extra['parent'])

        self._logger = Logger("WampAppSessionMasterService")

    @defer.inlineCallbacks
    def onJoin(self, details: SessionDetails) -> InlineCallbacksType[None]:
        self._logger.info("Wamp connection succeed (authid={authid})!", authid=self.authid)
        for handler in [self, *self.services]:
            yield self.register(handler)
            yield self.subscribe(handler)
        yield self.publish(f"org.buildbot.{self.master.masterid}.connected")
        self.parent.service = self  # type: ignore[attr-defined]
        self.parent.serviceDeferred.callback(self)  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def onLeave(self, details: CloseDetails) -> InlineCallbacksType[None]:
        if self.leaving:
            return

        # XXX We don't handle crossbar reboot, or any other disconnection well.
        # this is a tricky problem, as we would have to reconnect with exponential backoff
        # re-subscribe to subscriptions, queue messages until reconnection.
        # This is quite complicated, and I believe much better handled in autobahn
        # It is possible that such failure is practically non-existent
        # so for now, we just crash the master
        self._logger.info("Guru meditation! We have been disconnected from wamp server")
        self._logger.info("We don't know how to recover this without restarting the whole system")
        self._logger.info(str(details))
        yield self.master.stopService()

    def onUserError(self, e: Failure, msg: str) -> None:
        self._logger.failure(msg, e)


def make(config: Any) -> MasterService | dict[str, str]:
    if config:
        return MasterService(config)
    # if no config given, return a description of this WAMPlet ..
    return {
        'label': 'Buildbot master wamplet',
        'description': 'This contains all the wamp methods provided by a buildbot master',
    }


class WampConnector(service.ReconfigurableServiceMixin, service.AsyncMultiService):
    serviceClass = Service
    name: str | None = "wamp"  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.app: Service | None = None
        self.router_url: str | None = None
        self.realm: str | None = None
        self.wamp_debug_level: str | None = None
        self.serviceDeferred: defer.Deferred[MasterService] = defer.Deferred()
        self.service: MasterService | None = None

    def getService(self) -> defer.Deferred[MasterService]:
        if self.service is not None:
            return defer.succeed(self.service)
        d: defer.Deferred[MasterService] = defer.Deferred()

        @self.serviceDeferred.addCallback
        def gotService(service: MasterService) -> MasterService:
            d.callback(service)
            return service

        return d

    def stopService(self) -> None:  # type: ignore[override]
        if self.service is not None:
            self.service.leaving = True

        super().stopService()

    @defer.inlineCallbacks
    def publish(
        self, topic: str, data: Any, options: Any = None
    ) -> InlineCallbacksType[Publication | None]:
        service = yield self.getService()
        try:
            ret = yield service.publish(topic, data, options=options)
        except TransportLost as e:
            log.err(e, "while publishing event " + topic)
            return None
        return ret

    @defer.inlineCallbacks
    def subscribe(
        self, callback: Any, topic: str | None = None, options: Any = None
    ) -> InlineCallbacksType[Subscription | list[Subscription]]:
        service = yield self.getService()
        ret = yield service.subscribe(callback, topic, options)
        return ret

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config: Any) -> InlineCallbacksType[None]:
        if new_config.mq.get('type', 'simple') != "wamp":
            if self.app is not None:
                raise ValueError("Cannot use different wamp settings when reconfiguring")
            return

        wamp = new_config.mq
        log.msg("Starting wamp with config: %r", wamp)
        router_url = wamp.get('router_url', None)
        realm = bytes2unicode(wamp.get('realm', 'buildbot'))
        wamp_debug_level = wamp.get('wamp_debug_level', 'error')

        # MQ router can be reconfigured only once. Changes to configuration are not supported.
        # We can't switch realm nor the URL as that would leave transactions in inconsistent state.
        # Implementing reconfiguration just for wamp_debug_level does not seem like a good
        # investment.
        if self.app is not None:
            if (
                self.router_url != router_url
                or self.realm != realm
                or self.wamp_debug_level != wamp_debug_level
            ):
                raise ValueError("Cannot use different wamp settings when reconfiguring")
            return

        if router_url is None:
            return

        self.router_url = router_url
        self.realm = realm
        self.wamp_debug_level = wamp_debug_level

        self.app = self.serviceClass(
            url=self.router_url,
            extra={"master": self.master, "parent": self},
            realm=realm,
            make=make,
        )
        txaio.set_global_log_level(wamp_debug_level)  # type: ignore[attr-defined]
        yield self.app.setServiceParent(self)
        yield super().reconfigServiceWithBuildbotConfig(new_config)
