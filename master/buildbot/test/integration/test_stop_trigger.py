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


import sys
import textwrap

from twisted.internet import defer
from twisted.internet import reactor

from buildbot.config import BuilderConfig
from buildbot.plugins import schedulers
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.process.results import CANCELLED
from buildbot.test.util.integration import RunMasterBase


# This integration test creates a master and worker environment,
# with two builders and a trigger step linking them. the triggered build never ends
# so that we can reliably stop it recursively
class TriggeringMaster(RunMasterBase):
    timeout = 120
    change = {
        "branch": "master",
        "files": ["foo.c"],
        "author": "me@foo.com",
        "committer": "me@foo.com",
        "comments": "good stuff",
        "revision": "HEAD",
        "project": "none",
    }

    async def setup_trigger_config(self, triggeredFactory, nextBuild=None):
        c = {}

        c['schedulers'] = [
            schedulers.Triggerable(name="trigsched", builderNames=["triggered"]),
            schedulers.AnyBranchScheduler(name="sched", builderNames=["main"]),
        ]

        f = BuildFactory()
        f.addStep(
            steps.Trigger(schedulerNames=['trigsched'], waitForFinish=True, updateSourceStamp=True)
        )
        f.addStep(steps.ShellCommand(command='echo world'))

        mainBuilder = BuilderConfig(name="main", workernames=["local1"], factory=f)

        triggeredBuilderKwargs = {
            'name': "triggered",
            'workernames': ["local1"],
            'factory': triggeredFactory,
        }

        if nextBuild is not None:
            triggeredBuilderKwargs['nextBuild'] = nextBuild

        triggeredBuilder = BuilderConfig(**triggeredBuilderKwargs)

        c['builders'] = [mainBuilder, triggeredBuilder]
        await self.setup_master(c)

    async def setup_config_trigger_runs_forever(self):
        f2 = BuildFactory()

        # Infinite sleep command.
        if sys.platform == 'win32':
            # Ping localhost infinitely.
            # There are other options, however they either don't work in
            # non-interactive mode (e.g. 'pause'), or doesn't available on all
            # Windows versions (e.g. 'timeout' and 'choice' are available
            # starting from Windows 7).
            cmd = 'ping -t 127.0.0.1'.split()
        else:
            cmd = textwrap.dedent("""\
                while :
                do
                  echo "sleeping";
                  sleep 1;
                done
                """)

        f2.addStep(steps.ShellCommand(command=cmd))

        await self.setup_trigger_config(f2)

    async def setup_config_triggered_build_not_created(self):
        f2 = BuildFactory()
        f2.addStep(steps.ShellCommand(command="echo 'hello'"))

        def nextBuild(*args, **kwargs):
            return defer.succeed(None)

        await self.setup_trigger_config(f2, nextBuild=nextBuild)

    def assertBuildIsCancelled(self, b):
        self.assertTrue(b['complete'])
        self.assertEqual(b['results'], CANCELLED, repr(b))

    async def runTest(self, newBuildCallback, flushErrors=False):
        newConsumer = await self.master.mq.startConsuming(newBuildCallback, ('builds', None, 'new'))
        build = await self.doForceBuild(wantSteps=True, useChange=self.change, wantLogs=True)
        self.assertBuildIsCancelled(build)
        newConsumer.stopConsuming()
        builds = await self.master.data.get(("builds",))
        for b in builds:
            self.assertBuildIsCancelled(b)
        if flushErrors:
            self.flushLoggedErrors()

    async def testTriggerRunsForever(self):
        await self.setup_config_trigger_runs_forever()
        self.higherBuild = None

        def newCallback(_, data):
            if self.higherBuild is None:
                self.higherBuild = data['buildid']
            else:
                self.master.data.control("stop", {}, ("builds", self.higherBuild))
                self.higherBuild = None

        await self.runTest(newCallback, flushErrors=True)

    async def testTriggerRunsForeverAfterCmdStarted(self):
        await self.setup_config_trigger_runs_forever()
        self.higherBuild = None

        def newCallback(_, data):
            if self.higherBuild is None:
                self.higherBuild = data['buildid']
            else:

                def f():
                    self.master.data.control("stop", {}, ("builds", self.higherBuild))
                    self.higherBuild = None

                reactor.callLater(5.0, f)

        await self.runTest(newCallback, flushErrors=True)

    async def testTriggeredBuildIsNotCreated(self):
        await self.setup_config_triggered_build_not_created()

        def newCallback(_, data):
            self.master.data.control("stop", {}, ("builds", data['buildid']))

        await self.runTest(newCallback)
