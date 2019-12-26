"""
Tests for `buildbot_worker.util._hangcheck`.
"""

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.error import ConnectionDone
from twisted.internet.protocol import Protocol
from twisted.internet.task import Clock
from twisted.python.failure import Failure
from twisted.spread.pb import PBClientFactory
from twisted.trial.unittest import TestCase
from twisted.web.server import Site
from twisted.web.static import Data

from ..backports import SynchronousTestCase
from ..util import HangCheckFactory
from ..util._hangcheck import HangCheckProtocol

try:
    from twisted.internet.testing import AccumulatingProtocol
    from twisted.internet.testing import StringTransport
except ImportError:
    from twisted.test.proto_helpers import AccumulatingProtocol
    from twisted.test.proto_helpers import StringTransport


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
        protocol.dataReceived(b'some-data')

        self.assertEqual(wrapped_protocol.data, b"some-data")

    def test_data_cancels_timeout(self):
        """
        When data is received, the timeout is canceled
        """
        clock = Clock()
        protocol = HangCheckProtocol(Protocol(), reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol
        protocol.makeConnection(transport)
        protocol.dataReceived(b'some-data')
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
        protocol.dataReceived(b"some-data")
        protocol.connectionLost(
            Failure(ConnectionDone("Bye."))
        )

        assert_clock_idle(self, clock)


@defer.inlineCallbacks
def connected_server_and_client(case, server_factory, client_factory):
    """
    Create a server and client connected to that server.

    :param case: The test case that will handle cleanup.
    :param IProtocolFactory server_factory: The factory for the server protocol.
    :param IProtocolFactory client_factory: The factory for the client protocol.

    :return: A deferred that fires when the client has connected.

    .. todo:

       Figure out what a sensible value to return is. The existing caller doesn't
       use the return value.
    """
    try:
        listening_port = yield TCP4ServerEndpoint(reactor, 0).listen(server_factory)
        case.addCleanup(listening_port.stopListening)

        endpoint = TCP4ClientEndpoint(reactor, '127.0.0.1', listening_port.getHost().port)
        yield endpoint.connect(client_factory)

    except Exception as e:
        f = Failure(e)  # we can't use `e` from the lambda itself
        case.addCleanup(lambda: f)


class EndToEndHangCheckTests(TestCase):
    """
    End to end test for HangCheckProtocol.
    """

    @defer.inlineCallbacks
    def test_http(self):
        """
        When connecting to a HTTP server, a PB connection times
        out.
        """
        result = defer.Deferred()

        site = Site(Data("", "text/plain"))
        client = HangCheckFactory(
            PBClientFactory(), lambda: result.callback(None))

        self.patch(HangCheckProtocol, '_HUNG_CONNECTION_TIMEOUT', 0.1)

        d_connected = connected_server_and_client(
            self, site, client,
        )

        def cancel_all():
            result.cancel()
            d_connected.cancel()

        timer = reactor.callLater(2, cancel_all)

        try:
            yield result
        except defer.CancelledError:
            raise Exception('Timeout did not happen')
        finally:
            d_connected.cancel()
            timer.cancel()
