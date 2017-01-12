# Copyright Buildbot Team Members
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import absolute_import
from __future__ import print_function

from twisted.python.failure import Failure
from twisted.trial.unittest import SynchronousTestCase

from buildbot.util import Notifier


class TestException(Exception):

    """
    An exception thrown in tests.
    """


class Tests(SynchronousTestCase):

    def test_wait(self):
        """
        Calling `Notifier.wait` returns a deferred that hasn't fired.
        """
        n = Notifier()
        self.assertNoResult(n.wait())

    def test_notify_no_waiters(self):
        """
        Calling `Notifier.notify` when there are no waiters does not
        raise.
        """
        n = Notifier()
        n.notify(object())
        # Does not raise.

    def test_notify_multiple_waiters(self):
        """
        If there all multiple waiters, `Notifier.notify` fires all
        the deferreds with the same value.
        """
        value = object()
        n = Notifier()
        ds = [n.wait(), n.wait()]
        n.notify(value)
        self.assertEqual(
            [self.successResultOf(d) for d in ds],
            [value] * 2,
        )

    def test_new_waiters_not_notified(self):
        """
        If a new waiter is added while notifying, it won't be
        notified until the next notification.
        """
        value = object()
        n = Notifier()
        box = []

        def add_new_waiter(_):
            box.append(n.wait())
        n.wait().addCallback(add_new_waiter)
        n.notify(object())
        self.assertNoResult(box[0])
        n.notify(value)
        self.assertEqual(
            self.successResultOf(box[0]),
            value,
        )

    def test_notify_failure(self):
        """
        If a failure is passed to `Notifier.notify` then the waiters
        are errback'd.
        """
        n = Notifier()
        d = n.wait()
        n.notify(Failure(TestException()))
        self.failureResultOf(d, TestException)

    def test_nonzero_waiters(self):
        """
        If there are waiters, ``Notifier`` evaluates as `True`.
        """
        n = Notifier()
        n.wait()
        self.assertTrue(n)

    def test_nonzero_no_waiters(self):
        """
        If there no waiters, ``Notifier`` evaluates as `False`.
        """
        n = Notifier()
        self.assertFalse(n)

    def test_nonzero_cleared_waiters(self):
        """
        After notifying waiters, ``Notifier`` evaluates as `False`.
        """
        n = Notifier()
        n.wait()
        n.notify(object())
        self.assertFalse(n)
