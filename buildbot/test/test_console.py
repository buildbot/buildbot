# -*- test-case-name: buildbot.test.test_console -*-

import os 

from twisted.trial import unittest

from buildbot.status import builder
from buildbot.status.web import console
from buildbot.test.runutils import RunMixin

# Configuration to be used by the getBuildDetailsTest
run_config = """
from buildbot.process import factory
from buildbot.steps.shell import ShellCommand, WithProperties
from buildbot.buildslave import BuildSlave
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

b1 = {'name': 'full1', 'slavename': 'bot1', 'builddir': 'bd1', 'factory': f1}
b2 = {'name': 'full2', 'slavename': 'bot1', 'builddir': 'bd2', 'factory': f2}
c['builders'] = [b1, b2]
"""


# Tests for the global functions in console.py
class ConsoleTest(unittest.TestCase):
    # Test for console.getResultsClass
    def testgetResultsClass(self):
        self.failUnless(console.getResultsClass(None, None, True) == "running")
        self.failUnless(console.getResultsClass(None, builder.SUCCESS, False) == "notstarted")
        self.failUnless(console.getResultsClass(builder.SUCCESS, builder.SUCCESS, False) == "success")
        self.failUnless(console.getResultsClass(builder.SUCCESS, builder.FAILURE, False) == "success")
        self.failUnless(console.getResultsClass(builder.FAILURE, builder.FAILURE, False) == "warnings")
        self.failUnless(console.getResultsClass(builder.FAILURE, builder.SUCCESS, False) == "failure")
        self.failUnless(console.getResultsClass(builder.FAILURE, None, False) == "failure")
        self.failUnless(console.getResultsClass(builder.FAILURE, builder.EXCEPTION, False) == "failure")
        self.failUnless(console.getResultsClass(builder.FAILURE, builder.FAILURE, True) == "running")
        self.failUnless(console.getResultsClass(builder.EXCEPTION, builder.FAILURE, False) == "exception")

# Helper class to mock a request. We define only what we really need.
class MockRequest(object):
  def childLink(self, link):
    return link

# Class to test the method getBuildDetails in ConsoleStatusResource.
class GetBuildDetailsTests(RunMixin, unittest.TestCase):
    # Make sure the build details returned is an  empty string to signify that everything
    # was ok.
    def expectSuccess(self, bs):
        console_status = console.ConsoleStatusResource()
        results = console_status.getBuildDetails(MockRequest(), "buildername", bs);
        self.failUnless(results == "")

    # Make sure the build details returned contained the expected error.
    def expectFailure(self, bs):
        expected_details = """<li> buildername : 'ls -WillFail' failed. 
[ <a href="../builders/buildername/builds/0/steps/shell/logs/stdio">stdio</a> ]"""

        console_status = console.ConsoleStatusResource()
        results = console_status.getBuildDetails(MockRequest(), "buildername", bs);
        self.failUnless(results == expected_details)

    def testgetBuildDetails(self):
        # run an actual build with a step that will succeed, then another build with
        # a step that will fail, then make sure the build details generated contains
        # the right data.
        d = self.master.loadConfig(run_config)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectOneSlave("bot1"))
        d.addCallback(lambda res: self.requestBuild("full1"))
        d.addCallback(self.expectSuccess)
        d.addCallback(lambda res: self.requestBuild("full2"))
        d.addCallback(self.expectFailure)
        return d

