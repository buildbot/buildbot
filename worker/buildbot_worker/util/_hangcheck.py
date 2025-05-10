"""
Protocol wrapper that will detect hung connections.

In particular, since PB expects the server to talk first and HTTP
expects the client to talk first, when a PB client talks to an HTTP
server, neither side will talk, leading to a hung connection. This
wrapper will disconnect in that case, and inform the caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from twisted.internet.interfaces import IProtocol
from twisted.internet.interfaces import IProtocolFactory
from twisted.python.components import proxyForInterface

if TYPE_CHECKING:
    from typing import Callable

    from twisted.internet.interfaces import IAddress
    from twisted.internet.interfaces import IConnector
    from twisted.internet.interfaces import IDelayedCall
    from twisted.internet.interfaces import IReactorTime
    from twisted.internet.interfaces import ITransport
    from twisted.internet.protocol import ClientFactory
    from twisted.python.failure import Failure


def _noop() -> None:
    pass


class HangCheckProtocol(
    proxyForInterface(IProtocol, '_wrapped_protocol'),  # type: ignore[misc]
):
    """
    Wrap a protocol, so the underlying connection will disconnect if
    the other end doesn't send data within a given timeout.
    """

    transport: ITransport | None = None
    _hungConnectionTimer: IDelayedCall | None = None

    # hung connections wait for a relatively long time, since a busy master may
    # take a while to get back to us.
    _HUNG_CONNECTION_TIMEOUT = 120

    def __init__(
        self,
        wrapped_protocol: IProtocol,
        hung_callback: Callable[[], None] = _noop,
        reactor: IReactorTime | None = None,
    ) -> None:
        """
        :param IProtocol wrapped_protocol: The protocol to wrap.
        :param hung_callback: Called when the connection has hung.
        :type hung_callback: callable taking no arguments.
        :param IReactorTime reactor: The reactor to use to schedule
            the hang check.
        """
        if reactor is None:
            from twisted.internet import reactor as default_reactor

            reactor = cast("IReactorTime", default_reactor)

        self._wrapped_protocol = wrapped_protocol
        self._reactor = reactor
        self._hung_callback = hung_callback

    def makeConnection(self, transport: ITransport) -> None:
        # Note that we don't wrap the transport for the protocol,
        # because we only care about noticing data received, not
        # sent.
        self.transport = transport
        super().makeConnection(transport)
        self._startHungConnectionTimer()

    def dataReceived(self, data: bytes) -> None:
        self._stopHungConnectionTimer()
        super().dataReceived(data)

    def connectionLost(self, reason: Failure) -> None:
        self._stopHungConnectionTimer()
        super().connectionLost(reason)

    def _startHungConnectionTimer(self) -> None:
        """
        Start a timer to detect if the connection is hung.
        """

        def hungConnection() -> None:
            self._hung_callback()
            self._hungConnectionTimer = None
            if self.transport is not None:
                self.transport.loseConnection()

        self._hungConnectionTimer = self._reactor.callLater(
            self._HUNG_CONNECTION_TIMEOUT, hungConnection
        )

    def _stopHungConnectionTimer(self) -> None:
        """
        Cancel the hang check timer, since we have received data or
        been closed.
        """
        if self._hungConnectionTimer:
            self._hungConnectionTimer.cancel()
        self._hungConnectionTimer = None


class HangCheckFactory(
    proxyForInterface(IProtocolFactory, '_wrapped_factory'),  # type: ignore[misc]
):
    """
    Wrap a protocol factory, so the underlying connection will
    disconnect if the other end doesn't send data within a given
    timeout.
    """

    def __init__(
        self,
        wrapped_factory: ClientFactory,
        hung_callback: Callable[[], None],
    ) -> None:
        """
        :param IProtocolFactory wrapped_factory: The factory to wrap.
        :param hung_callback: Called when the connection has hung.
        :type hung_callback: callable taking no arguments.
        """
        self._wrapped_factory = wrapped_factory
        self._hung_callback = hung_callback

    def buildProtocol(self, addr: IAddress) -> HangCheckProtocol | None:
        protocol = self._wrapped_factory.buildProtocol(addr)
        if protocol is None:
            return None
        return HangCheckProtocol(protocol, hung_callback=self._hung_callback)

    # This is used as a ClientFactory, which doesn't have a specific interface, so forward the
    # additional methods.

    def startedConnecting(self, connector: IConnector) -> None:
        self._wrapped_factory.startedConnecting(connector)

    def clientConnectionFailed(self, connector: IConnector, reason: Failure) -> None:
        self._wrapped_factory.clientConnectionFailed(connector, reason)

    def clientConnectionLost(self, connector: IConnector, reason: Failure) -> None:
        self._wrapped_factory.clientConnectionLost(connector, reason)
