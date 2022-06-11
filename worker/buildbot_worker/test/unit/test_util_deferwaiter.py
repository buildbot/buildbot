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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot_worker.util.deferwaiter import DeferWaiter


class TestException(Exception):
    pass


class WaiterTests(unittest.TestCase):

    def test_add_deferred_called(self):
        w = DeferWaiter()
        w.add(defer.succeed(None))
        self.assertFalse(w.has_waited())

        d = w.wait()
        self.assertTrue(d.called)

    def test_add_non_deferred(self):
        w = DeferWaiter()
        w.add(2)
        self.assertFalse(w.has_waited())

        d = w.wait()
        self.assertTrue(d.called)

    def test_add_deferred_not_called_and_call_later(self):
        w = DeferWaiter()

        d1 = defer.Deferred()
        w.add(d1)
        self.assertTrue(w.has_waited())

        d = w.wait()
        self.assertFalse(d.called)

        d1.callback(None)
        self.assertFalse(w.has_waited())
        self.assertTrue(d.called)

    @defer.inlineCallbacks
    def test_passes_result(self):
        w = DeferWaiter()

        d1 = defer.Deferred()
        w.add(d1)

        d1.callback(123)
        res = yield d1
        self.assertEqual(res, 123)

        d = w.wait()
        self.assertTrue(d.called)

    @defer.inlineCallbacks
    def test_cancel_not_called(self):
        w = DeferWaiter()

        d1 = defer.Deferred()
        w.add(d1)
        self.assertTrue(w.has_waited())

        w.cancel()
        self.assertFalse(w.has_waited())

        d = w.wait()
        self.assertTrue(d.called)
        with self.assertRaises(defer.CancelledError):
            yield d1

        self.flushLoggedErrors(defer.CancelledError)

    @defer.inlineCallbacks
    def test_cancel_called(self):
        w = DeferWaiter()

        d1_waited = defer.Deferred()
        d1 = defer.succeed(None)
        d1.addCallback(lambda _: d1_waited)
        w.add(d1)

        w.cancel()

        d = w.wait()
        self.assertTrue(d.called)
        self.assertTrue(d1.called)
        self.assertTrue(d1_waited.called)
        with self.assertRaises(defer.CancelledError):
            yield d1

        self.flushLoggedErrors(defer.CancelledError)
