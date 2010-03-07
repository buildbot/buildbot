import os
import threading

from zope.interface import implements
from twisted.trial import unittest

from buildbot.test import state
from buildbot.schedulers import basic

class FakeDBConnector(object):
    pass

class FakeSchedulerManager(object):
    def __init__(self):
        self.db = FakeDBConnector()

class Scheduler(unittest.TestCase):

    def makeScheduler(self, **kwargs):
        """Set up a new scheduler with a fake environment; also adds default
        constructor args for convenience"""
        defaultargs = dict(
                name="tsched",
                branch=None,
                treeStableTimer=60,
                builderNames=['tbuild'])
        defaultargs.update(kwargs)
        sch = basic.Scheduler(**defaultargs)

        # NOTE: this doesn't actually call setServiceParent or start()
        sch.parent = FakeSchedulerManager()
        return sch

    def test_constructor_simple(self):
        sch = basic.Scheduler(
                name="tsched",
                branch=None,
                treeStableTimer=60,
                builderNames=['tbuild'])
        self.assertEqual(sch.name, "tsched")

    def test_changeIsRelevant_branch_None(self):
        sch = self.makeScheduler(branch=None)
        changes = [
            state.State(branch="release"),
            state.State(branch="maintenance"),
            state.State(branch=None),
        ]
        relevant = map(sch.changeIsRelevant, changes)
        self.assertEqual(relevant, [
            False,
            False,
            True,
        ])

    def test_changeIsRelevant_branch_set(self):
        sch = self.makeScheduler(branch="release")
        changes = [
            state.State(branch="release"),
            state.State(branch="maintenance"),
            state.State(branch=None),
        ]
        relevant = map(sch.changeIsRelevant, changes)
        self.assertEqual(relevant, [
            True,
            False,
            False,
        ])
