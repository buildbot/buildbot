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

import mock
import os
from twisted.internet import defer, reactor
from twisted.python import log
from twisted.trial import unittest
from buildbot import config
from buildbot.master import BuildMaster
from buildbot.test.util import dirs, www

DEBUG = False

if DEBUG:
    from sys import stdout
    log.startLogging(stdout)

# There has *got* to be a better way, but I don't see it.
# I commonly run these tests from the buildbot directory, where there exists a
# buildslave submodule.
# I need the buildslave (top-level) module to be picked up before this submodule
# that happens to be in the $PWD.
from sys import path as pythonpath
path0 = pythonpath.pop(0)
try:
    # Try to import buildslave and skip tests if we fail to import it.
    from buildslave import bot
    bot # Silence the linter.
except ImportError:
    bot = None
finally:
    pythonpath.insert(0, path0)
    

defer.setDebugging(True)
def check_running(x):
    return x.running

class RunMaster(dirs.DirsMixin, www.RequiresWwwMixin, unittest.TestCase):
    timeout = 1e100

    def setUp(self):
        super(RunMaster, self).setUp()
        if not bot:
            raise unittest.SkipTest("buildslave.bot not found.")

        self.masterdir = os.path.abspath('test-master')
        self.setUpDirs(self.masterdir)
        self.mastercfg = os.path.join(self.masterdir, 'master.cfg')
        open(self.mastercfg, "w").write(
            'from buildbot.test.integration.test_clean_shutdown \\\n'
            'import BuildmasterConfig\n')

        self.slavedir = os.path.abspath('test-slave')
        self.setUpDirs(self.slavedir)

    def tearDown(self):
        return self.tearDownDirs()

    @defer.inlineCallbacks
    def do_test_clean_shutdown(self):
        # create the master and set its config
        m = BuildMaster(self.masterdir, self.mastercfg)
        m.config = config.MasterConfig.loadConfig(
                                    self.masterdir, self.mastercfg)

        # mock reactor.stop (which trial *really* doesn't
        # like test code to call!)
        stop = mock.Mock(autospec=reactor.stop)
        self.patch(reactor, 'stop', stop)
        crash = mock.Mock(autospec=reactor.crash)
        self.patch(reactor, 'crash', crash)

        # update the DB
        yield m.db.setup(check_version=False)
        yield m.db.model.upgrade()

        # stub out m.db.setup since it was already called above
        m.db.setup = lambda : None

        # start the service
        yield m.startService()
        self.failIf(stop.called,
            "startService tried to stop the reactor; check logs")
        self.failIf(crash.called,
            "startService tried to crash the reactor; check logs")
        
        # hang out for a fraction of a second, to let startup processes run
        d = defer.Deferred()
        d.addCallback(check_running)
        reactor.callLater(0, d.callback, m)
        running = (yield d)
        self.assertEqual(running, 1)
        log.msg('master started.')
        
        # master started.
        # now start the slave.
        s = c['slaves'][0]
        s = bot.BuildSlave(
            "127.0.0.1",
            s.registration.getPort(),
            s.slavename, 
            s.password,
            self.slavedir,
            keepalive=0, usePTY=False, umask=022
        )

        yield s.startService()

        d = defer.Deferred()
        d.addCallback(check_running)
        reactor.callLater(.01, d.callback, s)
        running = (yield d)
        self.assertEqual(running, 1, 'slave should be running')
        log.msg('slave started.')

        # Send in a change. The CleanShutdown step should cause the master to stop.
        yield m.data.updates.addChange([], '(none)', 'nobody')

        log.msg('change sent.')

        timeout = 1
        epsilon = .1
        while running and timeout > 0:
            d = defer.Deferred()
            d.addCallback(check_running)
            reactor.callLater(epsilon, d.callback, m)
            running = (yield d)
            timeout -= epsilon
            log.msg('server running:', bool(running))
            log.msg('timeout:', timeout)

        log.msg('quit.')
        self.assertEqual(running, 0)
        log.msg('Yay! Master stopped all by itself!')

        # stop the slave too.
        log.msg('stopping slave.')
        d = defer.Deferred()
        d.addCallback(lambda _: s.stopService())
        reactor.callLater(0, d.callback, None)
        yield d

        self.assertEqual(s.running, 0, 'slave should be stopped')
        log.msg('slave stopped.')

        # and shutdown the db threadpool, as is normally done at reactor stop
        m.db.pool.shutdown()

        # (trial will verify all reactor-based timers have been cleared, etc.)
        log.msg('ALL DONE (I think...)')

    # run this test twice, to make sure the first time shut everything down
    # correctly; if this second test fails, but the first succeeds, then
    # something is not cleaning up correctly in stopService.
    def test_clean_shutdown1(self):
        return self.do_test_clean_shutdown()

    def test_clean_shutdown2(self):
        return self.do_test_clean_shutdown()

# A bogus little step to help trigger a clean-shutdown in the middle of the build.
from buildbot.process.buildstep import BuildStep
from buildbot.status.results import SUCCESS
class CleanShutdown(BuildStep):
    name = "clean shutdown"
    def start(self):
        self.build.builder.botmaster.cleanShutdown()
        return self.finished(SUCCESS)

# master configuration

# Note that the *same* configuration objects are used for both runs of the
# master.  This is a more strenuous test than strictly required, since a master
# will generally re-execute master.cfg on startup.  However, it's good form and
# will help to flush out any bugs that may otherwise be difficult to find.

c = BuildmasterConfig = {}
from buildbot.buildslave import BuildSlave
from buildbot.changes.pb import PBChangeSource
from buildbot.schedulers.basic import AnyBranchScheduler
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.schedulers.triggerable import Triggerable
from buildbot.process.factory import BuildFactory
from buildbot.steps.shell import ShellCommand
from buildbot.steps.trigger import Trigger
from buildbot.config import BuilderConfig
c['slaves'] = [BuildSlave ("local1", "localpw")]
c['slavePortnum'] = 0
c['change_source'] = []
c['change_source'] = PBChangeSource()
c['schedulers'] = []
c['schedulers'].append(AnyBranchScheduler(name="testy",
                            treeStableTimer=0,
                            builderNames=['testy']))
c['schedulers'].append(ForceScheduler(
                            name="force",
                            builderNames=["testy"]))
c['schedulers'].append(Triggerable(name='triggered-no-wait',
                    builderNames=['triggered-no-wait']))
c['schedulers'].append(Triggerable(name='triggered-with-wait',
                    builderNames=['triggered-with-wait']))


hi_step = ShellCommand(command='echo hi')
f1 = BuildFactory()
f1.addSteps((
        hi_step,
        CleanShutdown(),
        Trigger(
            schedulerNames=['triggered-no-wait'],
            updateSourceStamp=True,
            waitForFinish=False,
        ),
        Trigger(
            schedulerNames=['triggered-with-wait'],
            updateSourceStamp=True,
            # FIXME(#2019): if this is True, the 'testy' builder blocks indefinitely during clean-shutdown.
            # http://trac.buildbot.net/ticket/2019
            #waitForFinish=True,
            waitForFinish=False,
        ),
))
f_trivial = BuildFactory()
f_trivial.addStep(hi_step)

c['builders'] = [
    BuilderConfig(name="testy",
      slavenames=["local1"],
      factory=f1),
    BuilderConfig(name="triggered-no-wait",
      slavenames=["local1"],
      factory=f_trivial),
    BuilderConfig(name="triggered-with-wait",
      slavenames=["local1"],
      factory=f_trivial)]
c['status'] = []
c['title'] = "test"
c['titleURL'] = "test"
c['buildbotURL'] = "http://localhost:8010/"
c['db'] = {
    'db_url' : "sqlite:///state.sqlite"
}
