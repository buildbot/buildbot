"""
Tests for `buildbot_worker.util._hangcheck`.
"""

from twisted.internet import reactor
from twisted.internet.defer import CancelledError
from twisted.internet.defer import Deferred
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.error import ConnectionDone
from twisted.internet.protocol import Protocol
from twisted.internet.task import Clock
from twisted.python.failure import Failure
from twisted.spread.pb import PBClientFactory
from twisted.test.proto_helpers import AccumulatingProtocol
from twisted.test.proto_helpers import StringTransport
from twisted.trial.unittest import SynchronousTestCase
from twisted.trial.unittest import TestCase
from twisted.web.server import Site
from twisted.web.static import Data

from ..util import HangCheckFactory
from ..util._hangcheck import HangCheckProtocol


def assert_clock_idle(case, clock):
    """
    Assert that the given clock doesn't have any pending delayed
    calls.
    """
    case.assertEqual(
        clock.getDelayedCalls(), [],
    )


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
        assert_clock_idle(self, clock)

    def test_transport(self):
        """
        The transport passed to the underlying protocol is
        the underlying transport.
        """
        clock = Clock()
        wrapped_protocol = Protocol()
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
        wrapped_protocol = AccumulatingProtocol()
        protocol = HangCheckProtocol(wrapped_protocol, reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)
        protocol.dataReceived('some-data')

        self.assertEqual(wrapped_protocol.data , "some-data")

    def test_data_cancels_timeout(self):
        """
        When data is received, the timeout is canceled
        """
        clock = Clock()
        protocol = HangCheckProtocol(Protocol(), reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)
        protocol.dataReceived('some-data')
        assert_clock_idle(self, clock)

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
        assert_clock_idle(self, clock)

    def test_disconnect_forwarded(self):
        """
        If the connection is closed, the underlying protocol is informed.
        """
        clock = Clock()
        wrapped_protocol = AccumulatingProtocol()
        protocol = HangCheckProtocol(wrapped_protocol, reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)
        reason = ConnectionDone("Bye.")
        protocol.connectionLost(
            Failure(reason)
        )

        self.assertTrue(wrapped_protocol.closed)
        self.assertEqual(
            wrapped_protocol.closedReason.value,
            reason,
        )

    def test_disconnect_cancels_timeout(self):
        """
        If the connection is closed, the hang check is cancelled.
        """
        clock = Clock()
        protocol = HangCheckProtocol(
            Protocol(),
            reactor=clock,
        )
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)
        protocol.connectionLost(
            Failure(ConnectionDone("Bye."))
        )

        assert_clock_idle(self, clock)

    def test_data_and_disconnect(self):
        """
        If the connection receives data and then is closed, no error results.
        """
        clock = Clock()
        protocol = HangCheckProtocol(
            Protocol(),
            reactor=clock,
        )
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)
        protocol.dataReceived("some-data")
        protocol.connectionLost(
            Failure(ConnectionDone("Bye."))
        )

        assert_clock_idle(self, clock)


def reportUnhandledErrors(case, d):
    """
    Make sure that any unhandled errors from the
    given deferred are reported when the test case
    ends.
    """
    def cleanup():
        if isinstance(d.result, Failure):
            return d
    case.addCleanup(cleanup)
    return d


def listen(case, endpoint, factory):
    """
    Listen on an endpoint and cleanup when the
    test case ends.
    """
    d = endpoint.listen(factory)

    def registerCleanup(listeningPort):
        case.addCleanup(listeningPort.stopListening)
        return listeningPort
    d.addCallback(registerCleanup)
    return reportUnhandledErrors(case, d)


class EndToEndHangCheckTests(TestCase):
    """
    End to end test for HangCheckProtocol.
    """

    def test_http(self):
        """
        When connecting to a HTTP server, a PB connection times
        out.
        """
        result = Deferred()

        site = Site(Data("", "text/plain"))
        client = HangCheckFactory(
            PBClientFactory(), lambda: result.callback(None))

        self.patch(HangCheckProtocol, '_HUNG_CONNECTION_TIMEOUT', 0.1)

        listen(self, TCP4ServerEndpoint(
            reactor, 0), site).addCallback(
                lambda listening_port:
                TCP4ClientEndpoint(
                    reactor, '127.0.0.1', listening_port.getHost().port)
                .connect(client)

            )

        timer = reactor.callLater(2, result.cancel)
        result.addCallback(lambda _: timer.cancel())

        def check_for_timeout(reason):
            reason.trap(CancelledError)
            raise Exception("Didn't not hangup")
        result.addErrback(check_for_timeout)

        return result
