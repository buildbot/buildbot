import os
from twisted.internet import defer, reactor
from twisted.trial import unittest
from twisted.python import log

from buildbot import interfaces, master
from buildbot.db import dbspec, schema
from buildbot.util.eventual import fireEventually, flushEventualQueue
from buildbot.sourcestamp import SourceStamp

from buildbot.broken_test.runutils import MasterMixin

class Observer:
    def __init__(self):
        self.events = []
    def builderChangedState(self, name, state):
        self.events.append( ("builderChangedState", name, state) )
    def requestSubmitted(self, brs):
        self.events.append( ("requestSubmitted", brs) )
    def requestCancelled(self, brs):
        self.events.append( ("requestCancelled", brs) )

config = """\
from buildbot.buildslave import BuildSlave
from buildbot.scheduler import Scheduler
from buildbot.process import factory
c = BuildmasterConfig = {}
c['db_url'] = 'sqlite:///state.sqlite'
c['slaves'] = [BuildSlave('bot1', 'bot1passwd')]
c['slavePortnum'] = 0
c['schedulers'] = []
f1 = factory.BuildFactory()
b1 = {'name': 'full', 'slavename': 'bot1', 'builddir': 'full', 'factory': f1}
c['builders'] = [b1]
c['status'] = []
"""

class Pending(MasterMixin, unittest.TestCase):
    def test_pending(self):

        def submit_build(revision):
            ss = SourceStamp(revision="rev1")
            self.control.submitBuildSet(["full"], ss, "reason")

        o = Observer()
        self.create_master()
        d = self.master.loadConfig(config)
        d.addCallback(self.wait_until_idle)

        def _check1(ign):
            b = self.status.getBuilder("full")
            self.failUnlessEqual(b.getPendingBuilds(), [])
            b.subscribe(o)
            submit_build("rev1")
            pending = b.getPendingBuilds()
            self.failUnlessEqual(len(pending), 1)
            brs = pending[0]
            self.failUnless(interfaces.IBuildRequestStatus.providedBy(brs))
            ss1 = brs.getSourceStamp()
            self.failUnlessEqual(ss1.revision, "rev1")
            self.failUnlessEqual(brs.getBuilderName(), "full")
            return fireEventually()
        d.addCallback(_check1)
        d.addCallback(self.wait_until_idle)

        def _check2(ign):
            # two events: builderChangedState, requestSubmitted
            self.failUnlessEqual(len(o.events), 2)
            brs = [e[1] for e in o.events if e[0] == "requestSubmitted"][0]
            o.events[:] = []
            self.failUnless(interfaces.IBuildRequestStatus.providedBy(brs))
            ss1 = brs.getSourceStamp()
            self.failUnlessEqual(ss1.revision, "rev1")
            self.failUnlessEqual(brs.getBuilderName(), "full")

            bc = self.control.getBuilder("full")
            brcs = bc.getPendingBuilds()
            self.failUnlessEqual(len(brcs), 1)
            brcs[0].cancel()
        d.addCallback(_check2)
        d.addCallback(self.wait_until_idle)

        def _check2a(ign):
            b = self.status.getBuilder("full")
            self.failUnlessEqual(b.getPendingBuilds(), [])
            self.failUnlessEqual(len(o.events), 1)
            rc = o.events.pop(0)
            self.failUnlessEqual(rc[0], "requestCancelled")
            brs = rc[1]
            self.failUnlessEqual(brs.getSourceStamp().revision, "rev1")
        d.addCallback(_check2a)

        def _check3(ign):
            self.status.getBuilder("full").unsubscribe(o)
            submit_build("rev2")
        d.addCallback(_check3)
        d.addCallback(self.wait_until_idle)

        def _check4(ign):
            self.failUnlessEqual(o.events, [])
        d.addCallback(_check4)
        return d
