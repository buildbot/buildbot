# -*- test-case-name: buildbot.test.test_console -*-

from twisted.trial import unittest

from buildbot.status import builder
from buildbot.status.web import console
from buildbot.test.runutils import RunMixin
from buildbot.changes import changes

try:
    reversed
except NameError:
    def reversed(data):
	for index in xrange(len(data)-1,-1,-1):
	    yield data[index]

# Configuration to be used by the getBuildDetailsTest
run_config = """
from buildbot.process import factory
from buildbot.steps.shell import ShellCommand, WithProperties
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit', properties={'slprop':'slprop'})]
c['schedulers'] = []
c['slavePortnum'] = 0
c['properties'] = { 'global' : 'global' }

f1 = factory.BuildFactory([s(ShellCommand, flunkOnFailure=True,
                             command=['ls'],
                             workdir='.', timeout=10)])

f2 = factory.BuildFactory([s(ShellCommand, flunkOnFailure=True,
                             command=['ls -WillFail'],
                             workdir='.', timeout=10)])

b1 = BuilderConfig(name='full1', slavename='bot1', builddir='bd1', factory=f1)
b2 = BuilderConfig(name='full2', slavename='bot1', builddir='bd2', factory=f2)
c['builders'] = [b1, b2]
"""


# Tests for the global functions in console.py
class ConsoleTest(unittest.TestCase):
    # Test for console.getResultsClass
    def testgetResultsClass(self):
        self.assertEqual(console.getResultsClass(None, None, True), "running")
        self.assertEqual(console.getResultsClass(None, builder.SUCCESS, False), "notstarted")
        self.assertEqual(console.getResultsClass(builder.SUCCESS, builder.SUCCESS, False), "success")
        self.assertEqual(console.getResultsClass(builder.SUCCESS, builder.FAILURE, False), "success")
        self.assertEqual(console.getResultsClass(builder.FAILURE, builder.FAILURE, False), "warnings")
        self.assertEqual(console.getResultsClass(builder.FAILURE, builder.SUCCESS, False), "failure")
        self.assertEqual(console.getResultsClass(builder.FAILURE, None, False), "failure")
        self.assertEqual(console.getResultsClass(builder.FAILURE, builder.EXCEPTION, False), "failure")
        self.assertEqual(console.getResultsClass(builder.FAILURE, builder.FAILURE, True), "running")
        self.assertEqual(console.getResultsClass(builder.EXCEPTION, builder.FAILURE, False), "exception")

def _createDummyChange(revision):
    return changes.Change('Committer', ['files'], 'comment', revision=revision)

class TimeRevisionComparatorTest(unittest.TestCase):
    def setUp(self):
        self.comparator = console.TimeRevisionComparator()
        
    def testSameRevisionIsNotGreater(self):
        change = _createDummyChange('abcdef')
        self.assertFalse(self.comparator.isRevisionEarlier(change, change))

    def testOrdersDifferentRevisions(self):
        first = _createDummyChange('first_rev')
        second = _createDummyChange('second_rev')
        
        second.when += 1 # Make sure it's "after" the first
        self.assertTrue(self.comparator.isRevisionEarlier(first, second))
        self.assertFalse(self.comparator.isRevisionEarlier(second, first))

    def testReturnedKeySortsRevisionsCorrectly(self):
        my_changes = [_createDummyChange('rev' + str(i))
                      for i in range(1, 6)]
        for i in range(1, len(my_changes)):
            my_changes[i].when = my_changes[i-1].when + 1

        reversed_changes = list(reversed(my_changes))
        reversed_changes.sort(lambda a,b: cmp(getattr(a, self.comparator.getSortingKey()), getattr(b, self.comparator.getSortingKey())))
        self.assertEqual(my_changes, reversed_changes)

class IntegerRevisionComparatorTest(unittest.TestCase):
    def setUp(self):
        self.comparator = console.IntegerRevisionComparator()
    
    def testSameRevisionIsNotGreater(self):
        change = _createDummyChange('1')
        self.assertFalse(self.comparator.isRevisionEarlier(change, change))

    def testOrdersDifferentRevisions(self):
        first = _createDummyChange('1')
        second = _createDummyChange('2')

        self.assertTrue(self.comparator.isRevisionEarlier(first, second))
        self.assertFalse(self.comparator.isRevisionEarlier(second, first))

    def testIsValidRevisionAcceptsIntegers(self):
        for rev in range(100):
            self.assertTrue(self.comparator.isValidRevision(str(rev)))

    def testIsValidRevisionDoesNotAcceptNonIntegers(self):
        self.assertFalse(self.comparator.isValidRevision('revision'))

    def testReturnedKeySortsRevisionsCorrectly(self):
        my_changes = [_createDummyChange(str(i)) for i in range(1, 6)]

        reversed_changes = list(reversed(my_changes))
        reversed_changes.sort(lambda a,b: cmp(getattr(a, self.comparator.getSortingKey()), getattr(b, self.comparator.getSortingKey())))
        self.assertEqual(my_changes, reversed_changes)

# Helper class to mock a request. We define only what we really need.
class MockRequest(object):
    def childLink(self, link):
        return link

# Class to test the method getBuildDetails in ConsoleStatusResource.
class GetBuildDetailsTests(RunMixin, unittest.TestCase):
    # Test ConsoleStatusResource.getBuildDetails with a success and a failure case.
    def testgetBuildDetails(self):
        # run an actual build with a step that will succeed, then another build with
        # a step that will fail, then make sure the build details generated contains
        # the right data.
        d = self.master.loadConfig(run_config)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectOneSlave("bot1"))
        d.addCallback(lambda res: self.requestBuild("full1"))

        # Make sure the build details returned is an  empty string to signify that
        # everything was ok
        def expectSuccess(bs):
            console_status = console.ConsoleStatusResource()
            results = console_status.getBuildDetails(MockRequest(), "buildername", bs);
            self.assertEqual(results, "")
        d.addCallback(expectSuccess)

        d.addCallback(lambda res: self.requestBuild("full2"))

        # Make sure the build details returned contained the expected error.
        def expectFailure(bs):
            expected_details = """<li> buildername : 'ls -WillFail' failed. 
[ <a href="../builders/buildername/builds/0/steps/shell/logs/stdio">stdio</a> ]"""
            console_status = console.ConsoleStatusResource()
            results = console_status.getBuildDetails(MockRequest(), "buildername", bs);
            self.assertEqual(results, expected_details)

        d.addCallback(expectFailure)
        return d

