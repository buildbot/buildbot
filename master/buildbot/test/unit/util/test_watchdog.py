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

from unittest import mock

from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.util.watchdog import Watchdog


class TestWatchdog(TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()

    def test_not_started_no_calls(self):
        m = mock.Mock()
        w = Watchdog(self.reactor, m, 10)
        self.reactor.pump([1] * 100)
        self.assertEqual(m.call_count, 0)
        del w  # to silence unused variable warnings

    def test_started_calls(self):
        m = mock.Mock()
        w = Watchdog(self.reactor, m, 10)
        w.start()

        self.reactor.advance(9.9)
        self.assertEqual(m.call_count, 0)
        self.reactor.advance(0.2)
        self.assertEqual(m.call_count, 1)
        self.reactor.advance(20)
        self.assertEqual(m.call_count, 1)

    def test_two_starts_single_call(self):
        m = mock.Mock()
        w = Watchdog(self.reactor, m, 10)
        w.start()
        w.start()

        self.reactor.advance(9.9)
        self.assertEqual(m.call_count, 0)
        self.reactor.advance(0.2)
        self.assertEqual(m.call_count, 1)
        self.reactor.advance(20)
        self.assertEqual(m.call_count, 1)

    def test_started_stopped_does_not_call(self):
        m = mock.Mock()
        w = Watchdog(self.reactor, m, 10)
        w.start()
        w.stop()

        self.reactor.pump([1] * 100)
        self.assertEqual(m.call_count, 0)

    def test_triggers_repeatedly(self):
        m = mock.Mock()
        w = Watchdog(self.reactor, m, 10)

        w.start()
        self.reactor.advance(9.9)
        self.assertEqual(m.call_count, 0)
        self.reactor.advance(0.2)
        self.assertEqual(m.call_count, 1)

        w.start()
        self.reactor.advance(9.9)
        self.assertEqual(m.call_count, 1)
        self.reactor.advance(0.2)
        self.assertEqual(m.call_count, 2)

        w.start()
        self.reactor.advance(9.9)
        self.assertEqual(m.call_count, 2)
        self.reactor.advance(0.2)
        self.assertEqual(m.call_count, 3)

    def test_notify_delays_trigger(self):
        m = mock.Mock()
        w = Watchdog(self.reactor, m, 10)

        w.start()
        self.reactor.advance(5)
        w.notify()
        self.reactor.advance(9.9)
        self.assertEqual(m.call_count, 0)
        self.reactor.advance(0.2)
        self.assertEqual(m.call_count, 1)
