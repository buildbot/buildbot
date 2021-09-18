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

from twisted.internet import defer
from twisted.internet import interfaces
from twisted.internet import protocol
from zope.interface import implementer


class HTTPTunnelClient(protocol.Protocol):
    """
    This protocol handles the HTTP communication with the proxy server
    and subsequent creation of the tunnel.

    Once the tunnel is established, all incoming communication is forwarded
    directly to the wrapped protocol.
    """

    def __init__(self, connectedDeferred):
        # this gets set once the tunnel is ready
        self._proxyWrappedProtocol = None
        self._connectedDeferred = connectedDeferred

    def connectionMade(self):
        request = "CONNECT {}:{} HTTP/1.1\r\n\r\n".format(
            self.factory.host, self.factory.port)
        self.transport.write(request.encode())

    def connectionLost(self, reason):
        if self._proxyWrappedProtocol:
            # Proxy connectionLost to the wrapped protocol
            self._proxyWrappedProtocol.connectionLost(reason)

    def dataReceived(self, data):
        if self._proxyWrappedProtocol is not None:
            # If tunnel is already established, proxy dataReceived()
            # calls to the wrapped protocol
            return self._proxyWrappedProtocol.dataReceived(data)

        # process data from the proxy server
        _, status, _ = data.split(b"\r\n")[0].split(b" ", 2)
        if status != b"200":
            return self.transport.loseConnection()

        self._proxyWrappedProtocol = (
            self.factory._proxyWrappedFactory.buildProtocol(
                self.transport.getPeer()))
        self._proxyWrappedProtocol.makeConnection(self.transport)
        self._connectedDeferred.callback(self._proxyWrappedProtocol)

        # forward all traffic directly to the wrapped protocol
        self.transport.protocol = self._proxyWrappedProtocol

        # In case the server sent some data together with its response,
        # forward those to the wrapped protocol.
        remaining_data = data.split(b"\r\n\r\n", 2)[1]
        if remaining_data:
            return self._proxyWrappedProtocol.dataReceived(remaining_data)

        return None


class HTTPTunnelFactory(protocol.ClientFactory):
    """The protocol factory for the HTTP tunnel.

    It is used as a wrapper for BotFactory, which can hence be shielded
    from all the proxy business.
    """
    protocol = HTTPTunnelClient

    def __init__(self, host, port, wrappedFactory):
        self.host = host
        self.port = port

        self._proxyWrappedFactory = wrappedFactory
        self._onConnection = defer.Deferred()

    def doStart(self):
        super().doStart()
        # forward start notifications through to the wrapped factory.
        self._proxyWrappedFactory.doStart()

    def doStop(self):
        # forward stop notifications through to the wrapped factory.
        self._proxyWrappedFactory.doStop()
        super().doStop()

    def buildProtocol(self, addr):
        proto = self.protocol(self._onConnection)
        proto.factory = self
        return proto

    def clientConnectionFailed(self, connector, reason):
        if not self._onConnection.called:
            self._onConnection.errback(reason)


@implementer(interfaces.IStreamClientEndpoint)
class HTTPTunnelEndpoint(object):
    """This handles the connection to buildbot master on given 'host'
    and 'port' through the proxy server given as 'proxyEndpoint'.
    """

    def __init__(self, host, port, proxyEndpoint):
        self.host = host
        self.port = port
        self.proxyEndpoint = proxyEndpoint

    def connect(self, protocolFactory):
        """Connect to remote server through an HTTP tunnel."""
        tunnel = HTTPTunnelFactory(self.host, self.port, protocolFactory)
        d = self.proxyEndpoint.connect(tunnel)
        # once tunnel connection is established,
        # defer the subsequent server connection
        d.addCallback(lambda result: tunnel._onConnection)
        return d
