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
from twisted.internet import task
from twisted.trial import unittest

from buildbot import util
from buildbot.util import misc


class deferredLocked(unittest.TestCase):

    def test_name(self):
        self.assertEqual(util.deferredLocked, misc.deferredLocked)

    def test_fn(self):
        lock = defer.DeferredLock()

        @util.deferredLocked(lock)
        def check_locked(arg1, arg2):
            self.assertEqual([lock.locked, arg1, arg2], [True, 1, 2])
            return defer.succeed(None)
        d = check_locked(1, 2)

        @d.addCallback
        def check_unlocked(_):
            self.assertFalse(lock.locked)
        return d

    def test_fn_fails(self):
        lock = defer.DeferredLock()

        @util.deferredLocked(lock)
        def do_fail():
            return defer.fail(RuntimeError("oh noes"))
        d = do_fail()

        def check_unlocked(_):
            self.assertFalse(lock.locked)
        d.addCallbacks(lambda _: self.fail("didn't errback"),
                       lambda _: self.assertFalse(lock.locked))
        return d

    def test_fn_exception(self):
        lock = defer.DeferredLock()

        @util.deferredLocked(lock)
        def do_fail():
            raise RuntimeError("oh noes")
        # using decorators confuses pylint and gives a false positive below
        d = do_fail()           # pylint: disable=assignment-from-no-return

        def check_unlocked(_):
            self.assertFalse(lock.locked)
        d.addCallbacks(lambda _: self.fail("didn't errback"),
                       lambda _: self.assertFalse(lock.locked))
        return d

    def test_method(self):
        testcase = self

        class C:

            @util.deferredLocked('aLock')
            def check_locked(self, arg1, arg2):
                testcase.assertEqual(
                    [self.aLock.locked, arg1, arg2], [True, 1, 2])
                return defer.succeed(None)
        obj = C()
        obj.aLock = defer.DeferredLock()
        d = obj.check_locked(1, 2)

        @d.addCallback
        def check_unlocked(_):
            self.assertFalse(obj.aLock.locked)
        return d


class TestCancelAfter(unittest.TestCase):

    def setUp(self):
        self.d = defer.Deferred()

    def test_succeeds(self):
        d = misc.cancelAfter(10, self.d)
        self.assertIdentical(d, self.d)

        @d.addCallback
        def check(r):
            self.assertEqual(r, "result")
        self.assertFalse(d.called)
        self.d.callback("result")
        self.assertTrue(d.called)

    def test_fails(self):
        d = misc.cancelAfter(10, self.d)
        self.assertFalse(d.called)
        self.d.errback(RuntimeError("oh noes"))
        self.assertTrue(d.called)
        self.assertFailure(d, RuntimeError)

    def test_timeout_succeeds(self):
        c = task.Clock()
        d = misc.cancelAfter(10, self.d, _reactor=c)
        self.assertFalse(d.called)
        c.advance(11)
        d.callback("result")  # ignored
        self.assertTrue(d.called)
        self.assertFailure(d, defer.CancelledError)

    def test_timeout_fails(self):
        c = task.Clock()
        d = misc.cancelAfter(10, self.d, _reactor=c)
        self.assertFalse(d.called)
        c.advance(11)
        self.d.errback(RuntimeError("oh noes"))  # ignored
        self.assertTrue(d.called)
        self.assertFailure(d, defer.CancelledError)
