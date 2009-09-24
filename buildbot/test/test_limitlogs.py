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
