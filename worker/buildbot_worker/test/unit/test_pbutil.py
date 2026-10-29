"""Tests for worker PB connection and login deadlines."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

from twisted.application.internet import ClientService
from twisted.cred.credentials import UsernamePassword
from twisted.internet import defer
from twisted.internet.address import IPv4Address
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.error import ConnectionDone
from twisted.internet.task import Clock
from twisted.internet.testing import MemoryReactorClock
from twisted.internet.testing import StringTransport
from twisted.internet.testing import StringTransportWithDisconnection
from twisted.python.failure import Failure
from twisted.trial.unittest import TestCase

from buildbot_worker import pbutil
from buildbot_worker.pbutil import AutoLoginPBFactory

if TYPE_CHECKING:
    from twisted.spread.pb import Broker


PB_GREETING = b'\x02\x80\x02\x82pb\x04\x82none'


class TestLoginTimeout(TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.factory = AutoLoginPBFactory()
        self.factory._reactor = self.clock
        self.factory.startLogin(UsernamePassword(b'worker', b'password'))
        self.broker, self.transport = self.connect_broker(self.factory)

    def connect_broker(self, factory: AutoLoginPBFactory) -> tuple[Broker, StringTransport]:
        factory._reactor = self.clock
        broker = factory.buildProtocol(IPv4Address('TCP', '127.0.0.1', 9990))
        transport = StringTransport()
        broker.makeConnection(transport)
        self.addCleanup(self.disconnect_broker, broker)
        return broker, transport

    def disconnect_broker(self, broker: Broker) -> None:
        if not broker.disconnected:
            broker.connectionLost(Failure(ConnectionDone()))

    def test_silent_master(self) -> None:
        """A TCP connection alone does not satisfy the login deadline."""
        self.clock.advance(59)
        self.assertFalse(self.transport.disconnected)
        self.clock.advance(1)
        self.assertTrue(self.transport.disconnected)
        self.assertEqual(self.clock.getDelayedCalls(), [])

    def test_partial_negotiation(self) -> None:
        """Receiving part of the greeting does not cancel the deadline."""
        self.broker.dataReceived(PB_GREETING[:1])
        self.clock.advance(60)
        self.assertTrue(self.transport.disconnected)

    def start_login(self) -> defer.Deferred:
        login: defer.Deferred = defer.Deferred()
        self.patch(self.factory, '_cbSendUsername', lambda *args: login)
        self.broker.dataReceived(PB_GREETING)
        self.assertIs(self.factory._login_d, login)
        # Complete any simulated login before disconnecting the broker in cleanup.
        self.addCleanup(lambda: None if login.called else login.callback(Mock()))
        return login

    def test_stalled_login(self) -> None:
        """Completing protocol negotiation does not satisfy the deadline."""
        self.start_login()
        self.clock.advance(60)
        self.assertTrue(self.transport.disconnected)

    def test_successful_login(self) -> None:
        """Successful authentication cancels the deadline."""
        got_perspective = Mock()
        self.patch(self.factory, 'gotPerspective', got_perspective)
        login = self.start_login()
        perspective = Mock()
        login.callback(perspective)
        got_perspective.assert_called_once_with(perspective)
        self.assertEqual(self.clock.getDelayedCalls(), [])
        self.clock.advance(120)
        self.assertFalse(self.transport.disconnected)

    def test_disconnect(self) -> None:
        """Disconnecting before login cancels the deadline."""
        self.disconnect_broker(self.broker)
        self.assertEqual(self.clock.getDelayedCalls(), [])
        self.clock.advance(120)
        self.assertFalse(self.transport.disconnected)

    def test_replacement_connection_has_its_own_deadline(self) -> None:
        """The previous connection's deadline cannot abort its replacement."""
        self.clock.advance(30)
        self.disconnect_broker(self.broker)
        _, transport = self.connect_broker(self.factory)
        self.clock.advance(30)
        self.assertFalse(transport.disconnected)
        self.clock.advance(30)
        self.assertTrue(transport.disconnected)
        self.assertEqual(self.clock.getDelayedCalls(), [])

    def test_custom_timeout(self) -> None:
        self.disconnect_broker(self.broker)
        _, transport = self.connect_broker(AutoLoginPBFactory(loginTimeout=120))
        self.clock.advance(60)
        self.assertFalse(transport.disconnected)
        self.clock.advance(60)
        self.assertTrue(transport.disconnected)

    def test_late_login_cannot_cancel_replacement_deadline(self) -> None:
        """Login completion applies only to the connection that requested it."""
        login = self.start_login()
        self.disconnect_broker(self.broker)
        _, transport = self.connect_broker(self.factory)
        login.callback(Mock())
        self.clock.advance(60)
        self.assertTrue(transport.disconnected)

    def test_disabled_timeout(self) -> None:
        self.disconnect_broker(self.broker)
        _, transport = self.connect_broker(AutoLoginPBFactory(loginTimeout=None))
        self.assertEqual(self.clock.getDelayedCalls(), [])
        self.clock.advance(600)
        self.assertFalse(transport.disconnected)

    def test_invalid_timeout(self) -> None:
        for timeout in (0, -1):
            self.assertRaises(ValueError, AutoLoginPBFactory, loginTimeout=timeout)


class TestLoginTimeoutRetry(TestCase):
    def setUp(self) -> None:
        self.clock = MemoryReactorClock()
        self.patch(pbutil, 'reactor', self.clock)
        factory = AutoLoginPBFactory(retryPolicy=lambda attempt: 0)
        factory._reactor = self.clock
        factory.startLogin(UsernamePassword(b'worker', b'password'))
        self.service = ClientService(
            TCP4ClientEndpoint(self.clock, '127.0.0.1', 9990),
            factory,
            clock=self.clock,
            retryPolicy=lambda attempt: 1,
        )
        self.service.startService()
        self.addCleanup(lambda: self.service.stopService() if self.service.running else None)
        self.assertEqual(len(self.clock.tcpClients), 1)
        protocol = self.clock.tcpClients[0][2].buildProtocol(IPv4Address('TCP', '127.0.0.1', 9990))
        self.transport = StringTransportWithDisconnection()
        self.transport.protocol = protocol
        protocol.makeConnection(self.transport)

    def test_silent_master_retried(self) -> None:
        """A handshake timeout triggers ClientService's existing retry policy."""
        self.clock.advance(60)
        self.assertTrue(self.transport.disconnected)
        self.assertEqual(len(self.clock.tcpClients), 1)
        self.clock.advance(1)
        self.assertEqual(len(self.clock.tcpClients), 2)
        self.successResultOf(self.service.stopService())
        self.assertEqual(self.clock.getDelayedCalls(), [])

    def test_service_stop_cancels_timeout(self) -> None:
        """Stopping during negotiation leaves no deadline or retry behind."""
        self.successResultOf(self.service.stopService())
        self.assertEqual(self.clock.getDelayedCalls(), [])
        self.clock.advance(120)
        self.assertEqual(len(self.clock.tcpClients), 1)

    def test_stalled_login_retried(self) -> None:
        """A peer that negotiates PB but never answers login is retried."""
        self.transport.protocol.dataReceived(PB_GREETING)
        self.clock.advance(60)
        self.assertTrue(self.transport.disconnected)
        self.clock.advance(1)
        self.assertEqual(len(self.clock.tcpClients), 2)
        self.successResultOf(self.service.stopService())
        self.assertEqual(self.clock.getDelayedCalls(), [])
