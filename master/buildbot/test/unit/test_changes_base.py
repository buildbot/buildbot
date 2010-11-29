from twisted.trial import unittest
from twisted.internet import defer, reactor
from twisted.python import log
from buildbot.test.util import changesource
from buildbot.changes import base

class TestPollingChangeSource(changesource.ChangeSourceMixin, unittest.TestCase):
    class Subclass(base.PollingChangeSource):
        polledFn = None
        def poll(self):
            reactor.callLater(0, self.polledFn)
            return defer.succeed(None)

    def setUp(self):
        d = self.setUpChangeSource()
        def create_poller(_):
            self.poller = self.Subclass()
        d.addCallback(create_poller)
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def test_loop_loops(self):
        test_d = defer.Deferred()
        def polledFn():
            test_d.callback(None)
        self.poller.polledFn = polledFn
        poll_d = self.startChangeSource(self.poller)
        poll_d.addErrback(log.err)
        return defer.DeferredList([ test_d, poll_d ])
