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

from buildbot.plugins import schedulers
from buildbot.test.util.integration import RunMasterBase


# This integration test creates a master and worker environment,
# with one builders and a shellcommand step
# meant to be a template for integration steps
class ShellMaster(RunMasterBase):

    @defer.inlineCallbacks
    def test_shell(self):
        cfg = masterConfig()
        yield self.setupConfig(cfg)

        change = dict(branch="master",
                      files=["foo.c"],
                      author="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none"
                      )
        # switch the configuration of the scheduler, and make sure the correct builder is run
        cfg['schedulers'] = [
            schedulers.AnyBranchScheduler(
                name="sched1",
                builderNames=["testy2"]),
            schedulers.ForceScheduler(
                name="sched2",
                builderNames=["testy1"])
        ]
        yield self.master.reconfig()
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        builder = yield self.master.data.get(('builders', build['builderid']))
        self.assertEqual(builder['name'], 'testy2')


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps

    c['schedulers'] = [
        schedulers.AnyBranchScheduler(
            name="sched1",
            builderNames=["testy1"]),
        schedulers.ForceScheduler(
            name="sched2",
            builderNames=["testy2"])
    ]
    f = BuildFactory()
    f.addStep(steps.ShellCommand(command='echo hello'))
    c['builders'] = [
        BuilderConfig(name=name,
                      workernames=["local1"],
                      factory=f)
        for name in ['testy1', 'testy2']
    ]
    return c
