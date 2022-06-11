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

import time

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.util import backoff


class TestException(Exception):
    pass


class ExponentialBackoffEngineAsyncTests(unittest.TestCase, TestReactorMixin):
    def setUp(self):
        self.setup_test_reactor()

    def test_construct_asserts(self):
        with self.assertRaises(ValueError):
            backoff.ExponentialBackoffEngine(-1, 1, 1)
        with self.assertRaises(ValueError):
            backoff.ExponentialBackoffEngine(1, -1, 1)
        with self.assertRaises(ValueError):
            backoff.ExponentialBackoffEngine(1, 1, -1)

    @defer.inlineCallbacks
    def assert_called_after_time(self, d, time):
        self.assertFalse(d.called)

        self.reactor.advance(time * 0.99)
        self.assertFalse(d.called)
        self.reactor.advance(time * 0.010001)  # avoid rounding errors by overshooting a little
        self.assertTrue(d.called)

        yield d  # throw exceptions stored in d, if any

    @defer.inlineCallbacks
    def assert_called_immediately(self, d):
        self.assertTrue(d.called)
        yield d

    @defer.inlineCallbacks
    def test_wait_times(self):
        engine = backoff.ExponentialBackoffEngineAsync(self.reactor, start_seconds=10,
                                                       multiplier=2, max_wait_seconds=1000)
        yield self.assert_called_after_time(engine.wait_on_failure(), 10)
        yield self.assert_called_after_time(engine.wait_on_failure(), 20)

        engine.on_success()

        yield self.assert_called_after_time(engine.wait_on_failure(), 10)
        yield self.assert_called_after_time(engine.wait_on_failure(), 20)
        yield self.assert_called_after_time(engine.wait_on_failure(), 40)

        engine.on_success()
        engine.on_success()

        yield self.assert_called_after_time(engine.wait_on_failure(), 10)

    @defer.inlineCallbacks
    def test_max_wait_seconds(self):
        engine = backoff.ExponentialBackoffEngineAsync(self.reactor, start_seconds=10,
                                                       multiplier=2, max_wait_seconds=100)

        yield self.assert_called_after_time(engine.wait_on_failure(), 10)
        yield self.assert_called_after_time(engine.wait_on_failure(), 20)
        yield self.assert_called_after_time(engine.wait_on_failure(), 40)
        yield self.assert_called_after_time(engine.wait_on_failure(), 30)
        with self.assertRaises(backoff.BackoffTimeoutExceededError):
            yield self.assert_called_immediately(engine.wait_on_failure())
        with self.assertRaises(backoff.BackoffTimeoutExceededError):
            yield self.assert_called_immediately(engine.wait_on_failure())

        engine.on_success()

        yield self.assert_called_after_time(engine.wait_on_failure(), 10)
        yield self.assert_called_after_time(engine.wait_on_failure(), 20)
        yield self.assert_called_after_time(engine.wait_on_failure(), 40)
        yield self.assert_called_after_time(engine.wait_on_failure(), 30)
        with self.assertRaises(backoff.BackoffTimeoutExceededError):
            yield self.assert_called_immediately(engine.wait_on_failure())


class ExponentialBackoffEngineSyncTests(unittest.TestCase):
    # All the complex cases are tested in ExponentialBackoffEngineAsyncTests where we can fake
    # the clock. For the synchronous engine we just need to test that waiting works.
    def test_wait_on_failure(self):
        engine = backoff.ExponentialBackoffEngineSync(start_seconds=0.05, multiplier=2,
                                                      max_wait_seconds=1)
        begin = time.monotonic()
        engine.wait_on_failure()
        end = time.monotonic()
        # Note that if time is adjusted back even a little bit during the test it will fail.
        # So we add a little bit of wiggle room.
        self.assertGreater(end - begin, 0.04)
