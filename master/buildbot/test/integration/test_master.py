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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.task import deferLater

from buildbot.changes.filter import ChangeFilter
from buildbot.changes.pb import PBChangeSource
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.schedulers.basic import AnyBranchScheduler
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.steps.shell import ShellCommand
from buildbot.test.util import www
from buildbot.test.util.integration import RunMasterBase
from buildbot.worker import Worker


class RunMaster(RunMasterBase, www.RequiresWwwMixin):

    proto = 'pb'

    @defer.inlineCallbacks
    def do_test_master(self):
        yield self.setupConfig(BuildmasterConfig, startWorker=False)

        # hang out for a fraction of a second, to let startup processes run
        yield deferLater(reactor, 0.01, lambda: None)

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
c['workers'] = [Worker("local1", "localpw")]
c['protocols'] = {'pb': {'port': 'tcp:0'}}
c['change_source'] = []
c['change_source'] = PBChangeSource()
c['schedulers'] = []
c['schedulers'].append(AnyBranchScheduler(name="all",
                                          change_filter=ChangeFilter(
                                              project_re='^testy/'),
                                          treeStableTimer=1 * 60,
                                          builderNames=['testy', ]))
c['schedulers'].append(ForceScheduler(
    name="force",
    builderNames=["testy"]))
f1 = BuildFactory()
f1.addStep(ShellCommand(command='echo hi'))
c['builders'] = []
c['builders'].append(
    BuilderConfig(name="testy",
                  workernames=["local1"],
                  factory=f1))
c['status'] = []
c['title'] = "test"
c['titleURL'] = "test"
c['buildbotURL'] = "http://localhost:8010/"
