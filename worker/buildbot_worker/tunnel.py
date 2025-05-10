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

#
# Parts of this code were copied from Twisted Python.
# Copyright (c) Twisted Matrix Laboratories.
#
from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.internet import interfaces
from twisted.internet import protocol
from zope.interface import implementer

if TYPE_CHECKING:
    from twisted.internet.interfaces import IAddress
    from twisted.internet.interfaces import IConnector
    from twisted.internet.interfaces import IProtocol
    from twisted.internet.interfaces import IProtocolFactory
    from twisted.internet.interfaces import IStreamClientEndpoint
    from twisted.internet.protocol import Protocol
    from twisted.python.failure import Failure


class HTTPTunnelClient(protocol.Protocol):
    """
    This protocol handles the HTTP communication with the proxy server
    and subsequent creation of the tunnel.

    Once the tunnel is established, all incoming communication is forwarded
    directly to the wrapped protocol.
    """

    def __init__(self, connectedDeferred: defer.Deferred[IProtocol]) -> None:
        # this gets set once the tunnel is ready
        self._proxyWrappedProtocol: IProtocol | None = None
        self._connectedDeferred = connectedDeferred

    def connectionMade(self) -> None:
        assert isinstance(self.factory, HTTPTunnelFactory)
        request = f"CONNECT {self.factory.host}:{self.factory.port} HTTP/1.1\r\n\r\n"
        assert self.transport is not None
        self.transport.write(request.encode())

    def connectionLost(self, reason: Failure = protocol.connectionDone) -> None:
        if self._proxyWrappedProtocol:
            # Proxy connectionLost to the wrapped protocol
            self._proxyWrappedProtocol.connectionLost(reason)

    def dataReceived(self, data: bytes) -> None:
        if self._proxyWrappedProtocol is not None:
            # If tunnel is already established, proxy dataReceived()
            # calls to the wrapped protocol
            return self._proxyWrappedProtocol.dataReceived(data)

        assert self.transport is not None

        # process data from the proxy server
        _, status, _ = data.split(b"\r\n")[0].split(b" ", 2)
        if status != b"200":
            self.transport.loseConnection()
            return

        assert isinstance(self.factory, HTTPTunnelFactory)
        self._proxyWrappedProtocol = self.factory._proxyWrappedFactory.buildProtocol(
            self.transport.getPeer()
        )
        assert self._proxyWrappedProtocol is not None
        self._proxyWrappedProtocol.makeConnection(self.transport)
        self._connectedDeferred.callback(self._proxyWrappedProtocol)

        # forward all traffic directly to the wrapped protocol
        self.transport.protocol = self._proxyWrappedProtocol  # type: ignore[attr-defined]

        # In case the server sent some data together with its response,
        # forward those to the wrapped protocol.
        remaining_data = data.split(b"\r\n\r\n", 2)[1]
        if remaining_data:
            self._proxyWrappedProtocol.dataReceived(remaining_data)
            return

        return None


class HTTPTunnelFactory(protocol.ClientFactory):
    """The protocol factory for the HTTP tunnel.

    It is used as a wrapper for BotFactory, which can hence be shielded
    from all the proxy business.
    """

    protocol = HTTPTunnelClient  # type: ignore[assignment]

    def __init__(self, host: str, port: int, wrappedFactory: IProtocolFactory) -> None:
        self.host = host
        self.port = port

        self._proxyWrappedFactory = wrappedFactory
        self._onConnection: defer.Deferred[IProtocol] = defer.Deferred()

    def doStart(self) -> None:
        super().doStart()
        # forward start notifications through to the wrapped factory.
        self._proxyWrappedFactory.doStart()

    def doStop(self) -> None:
        # forward stop notifications through to the wrapped factory.
        self._proxyWrappedFactory.doStop()
        super().doStop()

    def buildProtocol(self, addr: IAddress) -> Protocol | None:
        proto = self.protocol(self._onConnection)  # type: ignore[has-type]
        proto.factory = self
        return proto

    def clientConnectionFailed(
        self,
        connector: IConnector,
        reason: Failure | BaseException | None,
    ) -> None:
        if not self._onConnection.called:
            self._onConnection.errback(reason)


@implementer(interfaces.IStreamClientEndpoint)
class HTTPTunnelEndpoint:
    """This handles the connection to buildbot master on given 'host'
    and 'port' through the proxy server given as 'proxyEndpoint'.
    """

    def __init__(self, host: str, port: int, proxyEndpoint: IStreamClientEndpoint) -> None:
        self.host = host
        self.port = port
        self.proxyEndpoint = proxyEndpoint

    def connect(self, protocolFactory: IProtocolFactory) -> defer.Deferred:
        """Connect to remote server through an HTTP tunnel."""
        tunnel = HTTPTunnelFactory(self.host, self.port, protocolFactory)
        d = self.proxyEndpoint.connect(tunnel)
        # once tunnel connection is established,
        # defer the subsequent server connection
        d.addCallback(lambda result: tunnel._onConnection)
        return d
