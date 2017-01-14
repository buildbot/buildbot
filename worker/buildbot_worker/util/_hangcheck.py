"""
Protocol wrapper that will detect hung connections.

In particular, since PB expects the server to talk first and HTTP
expects the client to talk first, when a PB client talks to an HTTP
server, neither side will talk, leading to a hung connection. This
wrapper will disconnect in that case, and inform the caller.
"""

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet.interfaces import IProtocol
from twisted.internet.interfaces import IProtocolFactory
from twisted.python.components import proxyForInterface


def _noop():
    pass


class HangCheckProtocol(
    proxyForInterface(IProtocol, '_wrapped_protocol'), object,
):
    """
    Wrap a protocol, so the underlying connection will disconnect if
    the other end doesn't send data within a given timeout.
    """
    transport = None
    _hungConnectionTimer = None

    # hung connections wait for a relatively long time, since a busy master may
    # take a while to get back to us.
    _HUNG_CONNECTION_TIMEOUT = 120

    def __init__(self, wrapped_protocol, hung_callback=_noop, reactor=None):
        """
        :param IProtocol wrapped_protocol: The protocol to wrap.
        :param hung_callback: Called when the connection has hung.
        :type hung_callback: callable taking no arguments.
        :param IReactorTime reactor: The reactor to use to schedule
            the hang check.
        """
        if reactor is None:
            from twisted.internet import reactor
        self._wrapped_protocol = wrapped_protocol
        self._reactor = reactor
        self._hung_callback = hung_callback

    def makeConnection(self, transport):
        # Note that we don't wrap the transport for the protocol,
        # because we only care about noticing data received, not
        # sent.
        self.transport = transport
        super(HangCheckProtocol, self).makeConnection(transport)
        self._startHungConnectionTimer()

    def dataReceived(self, data):
        self._stopHungConnectionTimer()
        super(HangCheckProtocol, self).dataReceived(data)

    def connectionLost(self, reason):
        self._stopHungConnectionTimer()
        super(HangCheckProtocol, self).connectionLost(reason)

    def _startHungConnectionTimer(self):
        """
        Start a timer to detect if the connection is hung.
        """
        def hungConnection():
            self._hung_callback()
            self._hungConnectionTimer = None
            self.transport.loseConnection()
        self._hungConnectionTimer = self._reactor.callLater(
            self._HUNG_CONNECTION_TIMEOUT, hungConnection)

    def _stopHungConnectionTimer(self):
        """
        Cancel the hang check timer, since we have received data or
        been closed.
        """
        if self._hungConnectionTimer:
            self._hungConnectionTimer.cancel()
        self._hungConnectionTimer = None


class HangCheckFactory(
    proxyForInterface(IProtocolFactory, '_wrapped_factory'), object,
):
    """
    Wrap a protocol factory, so the underlying connection will
    disconnect if the other end doesn't send data within a given
    timeout.
    """

    def __init__(self, wrapped_factory, hung_callback):
        """
        :param IProtocolFactory wrapped_factory: The factory to wrap.
        :param hung_callback: Called when the connection has hung.
        :type hung_callback: callable taking no arguments.
        """
        self._wrapped_factory = wrapped_factory
        self._hung_callback = hung_callback

    def buildProtocol(self, addr):
        protocol = self._wrapped_factory.buildProtocol(addr)
        return HangCheckProtocol(protocol, hung_callback=self._hung_callback)

    # This is used as a ClientFactory, which doesn't have a specific interface, so forward the additional methods.

    def startedConnecting(self, connector):
        self._wrapped_factory.startedConnecting(connector)

    def clientConnectionFailed(self, connector, reason):
        self._wrapped_factory.clientConnectionFailed(connector, reason)

    def clientConnectionLost(self, connector, reason):
        self._wrapped_factory.clientConnectionLost(connector, reason)
