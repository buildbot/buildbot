"""
Tests for `buildbot_worker.util._hangcheck`.
"""

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.protocol import Protocol
from twisted.internet.task import Clock
from twisted.spread.pb import PBClientFactory
from twisted.test.proto_helpers import AccumulatingProtocol
from twisted.test.proto_helpers import StringTransport
from twisted.trial.unittest import SynchronousTestCase
from twisted.trial.unittest import TestCase
from twisted.web.server import Site
from twisted.web.static import Data

from buildbot_worker.hangcheck import HangCheckProtocol


class HangCheckFactory(Factory):

    def __init__(self, wrapped_factory, hung_callback):
        self._wrapped_factory = wrapped_factory
        self._hung_callback = hung_callback

    def buildProtocol(self, addr):
        protocol = self._wrapped_factory.buildProtocol(addr)
        return HangCheckProtocol(protocol, hung_callback=self._hung_callback)


class HangCheckTests(SynchronousTestCase):
    """
    Tests for HangCheckProtocol.
    """

    def test_disconnects(self):
        """
        When connecting to a server that doesn't send any data,
        the protocol disconnects after the timeout.
        """
        clock = Clock()
        protocol = HangCheckProtocol(Protocol(), reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)

        clock.advance(120)
        self.assertTrue(transport.disconnecting)

    def test_stays_connected(self):
        """
        When connecting to a server that does send any data,
        the protocol does not disconnect after the timeout.
        """
        clock = Clock()
        wrapped_protocol = AccumulatingProtocol()
        protocol = HangCheckProtocol(wrapped_protocol, reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)
        protocol.dataReceived('some-data')

        self.assertEqual(wrapped_protocol.data, 'some-data')

    def test_transport(self):
        """
        The transport passed to the underlying protocol is
        the underyling transport.
        """
        clock = Clock()
        wrapped_protocol = AccumulatingProtocol()
        protocol = HangCheckProtocol(wrapped_protocol, reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)

        self.assertIdentical(wrapped_protocol.transport, transport)

    def test_forwards_data(self):
        """
        Data received by the protocol gets passed to the wrapped
        protocol.
        """
        clock = Clock()
        protocol = HangCheckProtocol(Protocol(), reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)
        protocol.dataReceived('some-data')

    def test_calls_callback(self):
        """
        When connecting to a server that doesn't send any data,
        the protocol calls the hung callback.
        """
        results = []
        clock = Clock()
        protocol = HangCheckProtocol(
            Protocol(),
            hung_callback=lambda: results.append(True),
            reactor=clock,
        )
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)

        clock.advance(120)
        self.assertEqual(results, [True])


class EndToEndHangCheckTests(TestCase):
    """
    End to end test for HangCheckProtocol.
    """
    skip = "Don't test end-to-end."

    def test_http(self):
        """
        When connecting to a HTTP server, a PB connection times
        out.
        """
        result = Deferred()

        site = Site(Data("", "text/plain"))
        client = HangCheckFactory(
            PBClientFactory(), lambda: result.callback(None))

        server_endpoint = TCP4ServerEndpoint(
            reactor, 8888)  # Fixme: Dynamically allocate port.
        client_endpoint = TCP4ClientEndpoint(
            reactor, '127.0.0.1', 8888)

        server_endpoint.listen(site)

        client_endpoint.connect(client)
        self.patch(HangCheckProtocol, '_HUNG_CONNECTION_TIMEOUT', 1)

        timer = reactor.callLater(5, result.cancel)
        result.addCallback(lambda _: timer.cancel())

        # TODO: Disconnect client and server.
        return result
