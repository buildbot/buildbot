# -*- test-case-name: buildbot.test.test_limitlogs -*-

from twisted.trial import unittest
from twisted.internet import reactor, defer
from twisted.internet.utils import getProcessValue, getProcessOutput
import twisted
from twisted.python.versions import Version
from twisted.python.procutils import which
from twisted.python import log, logfile
from buildbot.test.runutils import SignalMixin
import os

from buildbot.test.runutils import RunMixin, rmtree
from buildbot.changes import changes

'''Testcases to verify that the --log-size and --log-count options to
create-master and create-slave actually work.

These features require Twisted 8.2.0 to work.

Currently only testing the master side of it.
'''


master_cfg = """from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
s = factory.s

f1 = factory.QuickBuildFactory('fakerep', 'cvsmodule', configure=None)

f2 = factory.BuildFactory([
    dummy.Dummy(timeout=1),
    dummy.RemoteDummy(timeout=2),
    ])

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = []
c['builders'].append({'name':'quick', 'slavename':'bot1',
                      'builddir': 'quickdir', 'factory': f1})
c['slavePortnum'] = 0

from twisted.python import log
for i in xrange(100):
  log.msg('this is a mighty long string and I am going to write it into the log often')
"""

class MasterLogs(unittest.TestCase, SignalMixin):
    '''Limit master log size and count.'''

    def setUp(self):
        if twisted.version < Version("twisted", 8, 2, 0):
            self.skip = True
            raise unittest.SkipTest("Twisted 8.2.0 or higher required")
        self.setUpSignalHandler()

    def tearDown(self):
        self.tearDownSignalHandler()

    def testLog(self):
        exes = which('buildbot')
        if not exes:
            raise unittest.SkipTest("Buildbot needs to be installed")
        self.buildbotexe = exes[0]
        d = getProcessValue(self.buildbotexe,
                            ['create-master', '--log-size=1000', '--log-count=2',
                             'master'])
        d.addCallback(self._master_created)
        return d

    def _master_created(self, res):
        open('master/master.cfg', 'w').write(master_cfg)
        d = getProcessOutput(self.buildbotexe,
                            ['start', 'master'])
        d.addBoth(self._master_running)
        return d

    def _master_running(self, res):
        self.addCleanup(self._stop_master)
        d = defer.Deferred()
        reactor.callLater(2, d.callback, None)
        d.addCallback(self._do_tests)
        return d

    def _do_tests(self, rv):
        '''The actual method doing the tests on the master twistd.log'''
        lf = logfile.LogFile.fromFullPath(os.path.join('master', 'twistd.log'))
        self.failUnlessEqual(lf.listLogs(), [1,2])
        lr = lf.getLog(1)
        firstline = lr.readLines()[0]
        self.failUnless(firstline.endswith("this is a mighty long string and I am going to write it into the log often\n"))

    def _stop_master(self):
        d = getProcessOutput(self.buildbotexe,
                            ['stop', 'master'])
        d.addBoth(self._master_stopped)
        return d

    def _master_stopped(self, res):
        log.msg("master stopped")

builder_cfg = """from buildbot.process import factory
from buildbot.steps.shell import ShellCommand
from buildbot.buildslave import BuildSlave

f1 = factory.BuildFactory([
    ShellCommand(command=['echo', 'really long string'*50]),
    ])

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
from buildbot.scheduler import Scheduler
c['schedulers'] = [Scheduler('dummy', None, 0.1, ['dummy'])]
c['builders'] = []
c['builders'].append({'name':'dummy', 'slavename':'bot1',
                      'builddir': 'dummy', 'factory': f1})
c['slavePortnum'] = 0
c['logMaxSize'] = 150
"""
class BuilderLogs(RunMixin, unittest.TestCase):
    '''Limit builder log size'''

    def testLogMaxSize(self):
        rmtree("basedir")
        os.mkdir("basedir")
        d = self.master.loadConfig(builder_cfg)
        d.addCallback(lambda res: self.master.startService())
        d.addCallback(lambda res: self.connectSlave())

        # Trigger a change
        def _send(res):
            cm = self.master.change_svc
            c = changes.Change("bob", ["Makefile", "foo/bar.c"],
                               "changed stuff")
            cm.addChange(c)
        d.addCallback(_send)

        # Delay for a bit, so we know we're building
        def _delay(res):
            d1 = defer.Deferred()
            reactor.callLater(0.5, d1.callback, None)
            return d1
        d.addCallback(_delay)

        # Wait until the build is done
        def _waitForBuild(res):
            b = self.master.botmaster.builders['dummy']
            if len(b.builder_status.currentBuilds) > 0:
                return b.builder_status.currentBuilds[0].waitUntilFinished()
            else:
                return defer.succeed(None)
        d.addCallback(_waitForBuild)

        def _checkLog(res):
            builder = self.master.botmaster.builders['dummy']
            build = builder.builder_status.getLastFinishedBuild()
            text = build.steps[0].logs[0].getText()
            headers = build.steps[0].logs[0].getTextWithHeaders()
            self.failIf(len(text) > 150, "Text too long")
            self.failIf("truncated" not in headers, "Truncated message not found")
        d.addCallback(_checkLog)

        return d
