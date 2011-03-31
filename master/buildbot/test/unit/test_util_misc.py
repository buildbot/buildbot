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

from twisted.trial import unittest
from buildbot.util import misc
from buildbot import util
from twisted.python import failure
from twisted.internet import defer, reactor
from buildbot.test.util import compat

class deferredLocked(unittest.TestCase):
    def test_name(self):
        self.assertEqual(util.deferredLocked, misc.deferredLocked)

    def test_fn(self):
        l = defer.DeferredLock()
        @util.deferredLocked(l)
        def check_locked(arg1, arg2):
            self.assertEqual([l.locked, arg1, arg2], [True, 1, 2])
            return defer.succeed(None)
        d = check_locked(1, 2)
        def check_unlocked(_):
            self.assertFalse(l.locked)
        d.addCallback(check_unlocked)
        return d

    def test_fn_fails(self):
        l = defer.DeferredLock()
        @util.deferredLocked(l)
        def do_fail():
            return defer.fail(RuntimeError("oh noes"))
        d = do_fail()
        def check_unlocked(_):
            self.assertFalse(l.locked)
        d.addCallbacks(lambda _ : self.fail("didn't errback"),
                       lambda _ : self.assertFalse(l.locked))
        return d

    def test_fn_exception(self):
        l = defer.DeferredLock()
        @util.deferredLocked(l)
        def do_fail():
            raise RuntimeError("oh noes")
        d = do_fail()
        def check_unlocked(_):
            self.assertFalse(l.locked)
        d.addCallbacks(lambda _ : self.fail("didn't errback"),
                       lambda _ : self.assertFalse(l.locked))
        return d

    def test_method(self):
        testcase = self
        class C:
            @util.deferredLocked('aLock')
            def check_locked(self, arg1, arg2):
                testcase.assertEqual([self.aLock.locked, arg1, arg2], [True, 1, 2])
                return defer.succeed(None)
        obj = C()
        obj.aLock = defer.DeferredLock()
        d = obj.check_locked(1, 2)
        def check_unlocked(_):
            self.assertFalse(obj.aLock.locked)
        d.addCallback(check_unlocked)
        return d

class SerializedInvocation(unittest.TestCase):

    def waitForQuiet(self, si):
        d = defer.Deferred()
        si._quiet = lambda : d.callback(None)
        return d

    # tests

    def test_name(self):
        self.assertEqual(util.SerializedInvocation, misc.SerializedInvocation)

    def testCallFolding(self):
        events = []
        def testfn():
            d = defer.Deferred()
            def done():
                events.append('TM')
                d.callback(None)
            reactor.callLater(0, done)
            return d
        si = misc.SerializedInvocation(testfn)

        # run three times - the first starts testfn, the second
        # requires a second run, and the third is folded.
        d1 = si()
        d2 = si()
        d3 = si()

        dq = self.waitForQuiet(si)
        d = defer.gatherResults([d1, d2, d3, dq])
        def check(_):
            self.assertEqual(events, [ 'TM', 'TM' ])
        d.addCallback(check)
        return d

    @compat.usesFlushLoggedErrors
    def testException(self):
        def testfn():
            d = defer.Deferred()
            reactor.callLater(0, d.errback,
                              failure.Failure(RuntimeError("oh noes")))
            return d
        si = misc.SerializedInvocation(testfn)

        d = si()

        def check(_):
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        d.addCallback(check)
        return d

