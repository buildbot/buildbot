"""
Tests for `buildbot_worker.util._hangcheck`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.error import ConnectionDone
from twisted.internet.protocol import Protocol
from twisted.internet.task import Clock
from twisted.internet.testing import StringTransport
from twisted.python.failure import Failure
from twisted.spread.pb import PBClientFactory
from twisted.trial.unittest import TestCase
from twisted.web.static import Data

from buildbot_worker.test.util.site import SiteWithClose

from ..util import HangCheckFactory
from ..util._hangcheck import HangCheckProtocol

try:
    from twisted.internet.testing import AccumulatingProtocol
    from twisted.internet.testing import StringTransport
except ImportError:
    from twisted.test.proto_helpers import AccumulatingProtocol
    from twisted.test.proto_helpers import StringTransport

if TYPE_CHECKING:
    from twisted.internet.interfaces import IReactorTime

    from buildbot_worker.util.twisted import InlineCallbacksType


def assert_clock_idle(case: TestCase, clock: IReactorTime) -> None:
    """
    Assert that the given clock doesn't have any pending delayed
    calls.
    """
    case.assertEqual(
        clock.getDelayedCalls(),
        [],
    )


class HangCheckTests(TestCase):
    """
    Tests for HangCheckProtocol.
    """

    # On slower machines with high CPU oversubscription this test may take longer to run than
    # the default timeout.
    timeout = 20

    def test_disconnects(self) -> None:
        """
        When connecting to a server that doesn't send any data,
        the protocol disconnects after the timeout.
        """
        clock = Clock()
        protocol = HangCheckProtocol(Protocol(), reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol  # type: ignore[attr-defined]
        protocol.makeConnection(transport)

        clock.advance(120)
        self.assertTrue(transport.disconnecting)
        assert_clock_idle(self, clock)

    def test_transport(self) -> None:
        """
        The transport passed to the underlying protocol is
        the underlying transport.
        """
        clock = Clock()
        wrapped_protocol = Protocol()
        protocol = HangCheckProtocol(wrapped_protocol, reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol  # type: ignore[attr-defined]
        protocol.makeConnection(transport)

        self.assertIdentical(wrapped_protocol.transport, transport)

    def test_forwards_data(self) -> None:
        """
        Data received by the protocol gets passed to the wrapped
        protocol.
        """
        clock = Clock()
        wrapped_protocol = AccumulatingProtocol()
        protocol = HangCheckProtocol(wrapped_protocol, reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol  # type: ignore[attr-defined]
        protocol.makeConnection(transport)
        protocol.dataReceived(b'some-data')

        self.assertEqual(wrapped_protocol.data, b"some-data")

    def test_data_cancels_timeout(self) -> None:
        """
        When data is received, the timeout is canceled
        """
        clock = Clock()
        protocol = HangCheckProtocol(Protocol(), reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol  # type: ignore[attr-defined]
        protocol.makeConnection(transport)
        protocol.dataReceived(b'some-data')
        assert_clock_idle(self, clock)

    def test_calls_callback(self) -> None:
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

        transport.protocol = protocol  # type: ignore[attr-defined]
        protocol.makeConnection(transport)

        clock.advance(120)
        self.assertEqual(results, [True])
        assert_clock_idle(self, clock)

    def test_disconnect_forwarded(self) -> None:
        """
        If the connection is closed, the underlying protocol is informed.
        """
        clock = Clock()
        wrapped_protocol = AccumulatingProtocol()
        protocol = HangCheckProtocol(wrapped_protocol, reactor=clock)
        transport = StringTransport()

        transport.protocol = protocol  # type: ignore[attr-defined]
        protocol.makeConnection(transport)
        reason = ConnectionDone("Bye.")
        protocol.connectionLost(Failure(reason))

        self.assertTrue(wrapped_protocol.closed)
        assert wrapped_protocol.closedReason is not None
        self.assertEqual(
            wrapped_protocol.closedReason.value,
            reason,
        )

    def test_disconnect_cancels_timeout(self) -> None:
        """
        If the connection is closed, the hang check is cancelled.
        """
        clock = Clock()
        protocol = HangCheckProtocol(
            Protocol(),
            reactor=clock,
        )
        transport = StringTransport()

        transport.protocol = protocol  # type: ignore[attr-defined]
        protocol.makeConnection(transport)
        protocol.connectionLost(Failure(ConnectionDone("Bye.")))

        assert_clock_idle(self, clock)

    def test_data_and_disconnect(self) -> None:
        """
        If the connection receives data and then is closed, no error results.
        """
        clock = Clock()
        protocol = HangCheckProtocol(
            Protocol(),
            reactor=clock,
        )
        transport = StringTransport()

        transport.protocol = protocol  # type: ignore[attr-defined]
        protocol.makeConnection(transport)
        protocol.dataReceived(b"some-data")
        protocol.connectionLost(Failure(ConnectionDone("Bye.")))

        assert_clock_idle(self, clock)


@defer.inlineCallbacks
def connected_server_and_client(
    case: TestCase,
    server_factory: SiteWithClose,
    client_factory: HangCheckFactory,
) -> InlineCallbacksType[None]:
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
    # On slower machines with high CPU oversubscription this test may take longer to run than
    # the default timeout.
    timeout = 20

    @defer.inlineCallbacks
    def test_http(self) -> InlineCallbacksType[None]:
        """
        When connecting to a HTTP server, a PB connection times
        out.
        """
        result: defer.Deferred[None] = defer.Deferred()

        site = SiteWithClose(Data("", "text/plain"))
        client = HangCheckFactory(PBClientFactory(), lambda: result.callback(None))

        self.patch(HangCheckProtocol, '_HUNG_CONNECTION_TIMEOUT', 0.1)

        d_connected = connected_server_and_client(
            self,
            site,
            client,
        )

        def cancel_all() -> None:
            result.cancel()
            d_connected.cancel()

        timer = cast("IReactorTime", reactor).callLater(2, cancel_all)

        try:
            yield result
        except defer.CancelledError as e:
            raise RuntimeError('Timeout did not happen') from e
        finally:
            d_connected.cancel()
            timer.cancel()

        site.close_connections()
