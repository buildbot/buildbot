from twisted.internet.interfaces import IProtocol
from twisted.python.components import proxyForInterface


def _noop():
    pass

class HangCheckProtocol(
    proxyForInterface(IProtocol, '_wrapped_protocol'), object,
):

    connected = False
    transport = None

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
        self.connected = True
        super(HangCheckProtocol, self).makeConnection(transport)
        self._startHungConnectionTimer()

    def dataReceived(self, data):
        self._stopHungConnectionTimer()
        super(HangCheckProtocol, self).dataReceived(data)

    # hung connections wait for a relatively long time, since a busy master may
    # take a while to get back to us.
    _hungConnectionTimer = None
    _HUNG_CONNECTION_TIMEOUT = 120

    def _startHungConnectionTimer(self):
        self._stopHungConnectionTimer()

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
