
from twisted.trial import unittest
from twisted.internet import defer

from buildbot.eventual import eventually, fireEventually, flushEventualQueue

class TestEventual(unittest.TestCase):

    def tearDown(self):
        return flushEventualQueue()

    def testSend(self):
        results = []
        eventually(results.append, 1)
        self.failIf(results)
        def _check():
            self.failUnlessEqual(results, [1])
        eventually(_check)
        def _check2():
            self.failUnlessEqual(results, [1,2])
        eventually(results.append, 2)
        eventually(_check2)

    def testFlush(self):
        results = []
        eventually(results.append, 1)
        eventually(results.append, 2)
        d = flushEventualQueue()
        def _check(res):
            self.failUnlessEqual(results, [1,2])
        d.addCallback(_check)
        return d

    def testFlush2(self):
        added = []
        called = []
        done_d = defer.Deferred()
        def _then():
            called.append("f1")
            added.append("f2")
            d = flushEventualQueue()
            d.addCallback(lambda ign: called.append("f2"))
            def _second_flush_done(ign):
                done_d.callback(None)
            d.addCallback(_second_flush_done)
        added.append("f1")
        eventually(_then)
        added.append(1)
        eventually(called.append, 1)
        added.append(2)
        eventually(called.append, 2)
        d = flushEventualQueue()
        d.addCallback(flushEventualQueue)
        d.addCallback(lambda ign: done_d)
        def _check(res):
            self.failUnlessEqual(called, ["f1", 1, 2, "f2"])
            self.failUnlessEqual(added, called)
        d.addCallback(_check)
        return d

    def testFire(self):
        results = []
        fireEventually(1).addCallback(results.append)
        fireEventually(2).addCallback(results.append)
        self.failIf(results)
        def _check(res):
            self.failUnlessEqual(results, [1,2])
        d = flushEventualQueue()
        d.addCallback(_check)
        return d
