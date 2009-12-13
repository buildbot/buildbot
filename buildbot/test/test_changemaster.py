# -*- test-case-name: buildbot.test.test_changemaster -*-

from twisted.trial import unittest

from buildbot.changes.changes import *

class _DummyParent:
    def __init__(self):
        self.changes = []
    def addChange(self, change):
        self.changes.append(change)

    def addService(self, child):
        pass

class TestMaster(unittest.TestCase):
    def testAddChange(self):
        parent = _DummyParent()
        master = TestChangeMaster()
        master.setServiceParent(parent)

        change = Change('user', [], 'comments')

        master.addChange(change)

        self.failUnlessEqual(parent.changes, [change])

    def testChangeHorizon(self):
        parent = _DummyParent()
        master = TestChangeMaster()
        master.setServiceParent(parent)
        master.changeHorizon = 3

        changes = []
        for i in range(4):
            change = Change('user', [], 'comment %i' % i)
            master.addChange(change)
            changes.append(change)

        changes = changes[-3:]

        self.failUnlessEqual(master.changes, changes)

    def testNoChangeHorizon(self):
        parent = _DummyParent()
        master = TestChangeMaster()
        master.setServiceParent(parent)
        master.changeHorizon = 0

        changes = []
        for i in range(4):
            change = Change('user', [], 'comment %i' % i)
            master.addChange(change)
            changes.append(change)

        changes = changes[:]

        self.failUnlessEqual(master.changes, changes)
