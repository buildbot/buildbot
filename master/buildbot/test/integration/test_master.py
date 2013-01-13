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
from twisted.trial import unittest
from buildbot import config
from buildbot.master import BuildMaster
from buildbot.test.util import dirs

class RunMaster(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath('basdir')
        self.setUpDirs(self.basedir)
        self.configfile = os.path.join(self.basedir, 'master.cfg')
        open(self.configfile, "w").write(
            'from buildbot.test.integration.test_master \\\n'
            'import BuildmasterConfig\n')

    def tearDown(self):
        return self.tearDownDirs()

    @defer.inlineCallbacks
    def do_test_master(self):
        # create the master and set its config
        m = BuildMaster(self.basedir, self.configfile)
        m.config = config.MasterConfig.loadConfig(
                                    self.basedir, self.configfile)

        # update the DB
        yield m.db.setup(check_version=False)
        yield m.db.model.upgrade()

        # stub out m.db.setup since it was already called above
        m.db.setup = lambda : None

        # mock reactor.stop (which trial *really* doesn't
        # like test code to call!)
        mock_reactor = mock.Mock(spec=reactor)
        mock_reactor.callWhenRunning = reactor.callWhenRunning

        # start the service
        yield m.startService(_reactor=mock_reactor)
        self.failIf(mock_reactor.stop.called,
            "startService tried to stop the reactor; check logs")

        # hang out for a fraction of a second, to let startup processes run
        d = defer.Deferred()
        reactor.callLater(0.01, d.callback, None)
        yield d

        # stop the service
        yield m.stopService()

        # and shutdown the db threadpool, as is normally done at reactor stop
        m.db.pool.shutdown()

        # (trial will verify all reactor-based timers have been cleared, etc.)

    # run this test twice, to make sure the first time shut everything down
    # correctly; if this second test fails, but the first succeeds, then
    # something is not cleaning up correctly in stopService.
    def test_master1(self):
        return self.do_test_master()

    def test_master2(self):
        return self.do_test_master()

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
from buildbot.changes.filter import ChangeFilter
from buildbot.process.factory import BuildFactory
from buildbot.steps.shell import ShellCommand
from buildbot.config import BuilderConfig
from buildbot.status import html
c['slaves'] = [BuildSlave ("local1", "localpw")]
c['slavePortnum'] = 0
c['change_source'] = []
c['change_source'] = PBChangeSource()
c['schedulers'] = []
c['schedulers'].append(AnyBranchScheduler(name="all",
                            change_filter=ChangeFilter(project_re='^testy/'),
                            treeStableTimer=1*60,
                            builderNames=[ 'testy', ]))
c['schedulers'].append(ForceScheduler(
                            name="force",
                            builderNames=["testy"]))
f1 = BuildFactory()
f1.addStep(ShellCommand(command='echo hi'))
c['builders'] = []
c['builders'].append(
    BuilderConfig(name="testy",
      slavenames=["local1"],
      factory=f1))
c['status'] = []
c['status'].append(html.WebStatus(http_port=0))
c['title'] = "test"
c['titleURL'] = "test"
c['buildbotURL'] = "http://localhost:8010/"
c['db'] = {
    'db_url' : "sqlite:///state.sqlite"
}
