from twisted.internet.interfaces import IProtocol, IProtocolFactory
from twisted.python.components import proxyForInterface


def _noop():
    pass


class HangCheckProtocol(
    proxyForInterface(IProtocol, '_wrapped_protocol'), object,
):
    transport = None
    _hungConnectionTimer = None

    # hung connections wait for a relatively long time, since a busy master may
    # take a while to get back to us.
    _HUNG_CONNECTION_TIMEOUT = 120

    def __init__(self, wrapped_protocol, hung_callback=_noop, reactor=None):
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
        def hungConnection():
            self._hung_callback()
            self._hungConnectionTimer = None
            self.transport.loseConnection()
        self._hungConnectionTimer = self._reactor.callLater(
            self._HUNG_CONNECTION_TIMEOUT, hungConnection)

    def _stopHungConnectionTimer(self):
        if self._hungConnectionTimer:
            self._hungConnectionTimer.cancel()
        self._hungConnectionTimer = None


class HangCheckFactory(
    proxyForInterface(IProtocolFactory, '_wrapped_factory'), object,
):

    def __init__(self, wrapped_factory, hung_callback):
        self._wrapped_factory = wrapped_factory
        self._hung_callback = hung_callback

    # This is used as a ClientFactory, which doesn't have a specific interface, so forward the additional methods.
    def buildProtocol(self, addr):
        protocol = self._wrapped_factory.buildProtocol(addr)
        return HangCheckProtocol(protocol, hung_callback=self._hung_callback)

    def startedConnecting(self, connector):
        self._wrapped_factory.startedConnecting(connector)

    def clientConnectionFailed(self, connector, reason):
        self._wrapped_factory.clientConnectionFailed(connector, reason)

    def clientConnectionLost(self, connector, reason):
        self._wrapped_factory.clientConnectionLost(connector, reason)
