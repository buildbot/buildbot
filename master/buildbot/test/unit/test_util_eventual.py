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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.python import log
from twisted.trial import unittest

from buildbot.util import eventual


class Eventually(unittest.TestCase):

    def setUp(self):
        # reset the queue to its base state
        eventual._theSimpleQueue = eventual._SimpleCallQueue()
        self.old_log_err = log.err
        self.results = []

    def tearDown(self):
        log.err = self.old_log_err
        return eventual.flushEventualQueue()

    # utility callback
    def cb(self, *args, **kwargs):
        r = args
        if kwargs:
            r = r + (kwargs,)
        self.results.append(r)

    # flush the queue and assert results
    def assertResults(self, exp):
        d = eventual.flushEventualQueue()

        @d.addCallback
        def cb(_):
            self.assertEqual(self.results, exp)
        return d

    # tests

    def test_eventually_calls(self):
        eventual.eventually(self.cb)
        return self.assertResults([()])

    def test_eventually_args(self):
        eventual.eventually(self.cb, 1, 2, a='a')
        return self.assertResults([(1, 2, dict(a='a'))])

    def test_eventually_err(self):
        # monkey-patch log.err; this is restored by tearDown
        log.err = lambda: self.results.append("err")

        def cb_fails():
            raise RuntimeError("should not cause test failure")
        eventual.eventually(cb_fails)
        return self.assertResults(['err'])

    def test_eventually_butNotNow(self):
        eventual.eventually(self.cb, 1)
        self.assertFalse(self.results != [])
        return self.assertResults([(1,)])

    def test_eventually_order(self):
        eventual.eventually(self.cb, 1)
        eventual.eventually(self.cb, 2)
        eventual.eventually(self.cb, 3)
        return self.assertResults([(1,), (2,), (3,)])

    def test_flush_waitForChainedEventuallies(self):
        def chain(n):
            self.results.append(n)
            if n <= 0:
                return
            eventual.eventually(chain, n - 1)
        chain(3)
        # (the flush this tests is implicit in assertResults)
        return self.assertResults([3, 2, 1, 0])

    def test_flush_waitForTreeEventuallies(self):
        # a more complex set of eventualities
        def tree(n):
            self.results.append(n)
            if n <= 0:
                return
            eventual.eventually(tree, n - 1)
            eventual.eventually(tree, n - 1)
        tree(2)
        # (the flush this tests is implicit in assertResults)
        return self.assertResults([2, 1, 1, 0, 0, 0, 0])

    def test_flush_duringTurn(self):
        testd = defer.Deferred()

        def cb():
            d = eventual.flushEventualQueue()
            d.addCallback(testd.callback)
        eventual.eventually(cb)
        return testd

    def test_fireEventually_call(self):
        d = eventual.fireEventually(13)
        d.addCallback(self.cb)
        return self.assertResults([(13,)])
