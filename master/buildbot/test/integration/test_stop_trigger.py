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


from __future__ import annotations

import sys
import textwrap
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.internet import reactor

from buildbot.config import BuilderConfig
from buildbot.plugins import schedulers
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.process.results import CANCELLED
from buildbot.test.util.integration import RunMasterBase

if TYPE_CHECKING:
    from collections.abc import Callable

    from buildbot.util.twisted import InlineCallbacksType


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

    @defer.inlineCallbacks
    def setup_trigger_config(
        self,
        triggeredFactory: BuildFactory,
        nextBuild: Callable[..., defer.Deferred[None | dict[str, Any]]] | None = None,
    ) -> InlineCallbacksType[None]:
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

        triggeredBuilder = BuilderConfig(**triggeredBuilderKwargs)  # type: ignore[arg-type]

        c['builders'] = [mainBuilder, triggeredBuilder]
        yield self.setup_master(c)

    @defer.inlineCallbacks
    def setup_config_trigger_runs_forever(self) -> InlineCallbacksType[None]:
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

        yield self.setup_trigger_config(f2)

    @defer.inlineCallbacks
    def setup_config_triggered_build_not_created(self) -> InlineCallbacksType[None]:
        f2 = BuildFactory()
        f2.addStep(steps.ShellCommand(command="echo 'hello'"))

        def nextBuild(*args: Any, **kwargs: Any) -> defer.Deferred[None]:
            return defer.succeed(None)

        yield self.setup_trigger_config(f2, nextBuild=nextBuild)  # type: ignore[arg-type]

    def assertBuildIsCancelled(self, b: dict[str, Any]) -> None:
        self.assertTrue(b['complete'])
        self.assertEqual(b['results'], CANCELLED, repr(b))

    @defer.inlineCallbacks
    def runTest(  # type: ignore[override]
        self,
        newBuildCallback: Callable[[tuple[str, ...], dict[str, Any]], None],
        flushErrors: bool = False,
    ) -> InlineCallbacksType[None]:
        newConsumer = yield self.master.mq.startConsuming(newBuildCallback, ('builds', None, 'new'))
        build = yield self.doForceBuild(wantSteps=True, useChange=self.change, wantLogs=True)
        self.assertBuildIsCancelled(build)
        newConsumer.stopConsuming()
        builds = yield self.master.data.get(("builds",))
        for b in builds:
            self.assertBuildIsCancelled(b)
        if flushErrors:
            self.flushLoggedErrors()

    @defer.inlineCallbacks
    def testTriggerRunsForever(self) -> InlineCallbacksType[None]:
        yield self.setup_config_trigger_runs_forever()
        self.higherBuild = None

        def newCallback(_: tuple[str, ...], data: dict[str, Any]) -> None:
            if self.higherBuild is None:
                self.higherBuild = data['buildid']
            else:
                self.master.data.control("stop", {}, ("builds", self.higherBuild))
                self.higherBuild = None

        yield self.runTest(newCallback, flushErrors=True)

    @defer.inlineCallbacks
    def testTriggerRunsForeverAfterCmdStarted(self) -> InlineCallbacksType[None]:
        yield self.setup_config_trigger_runs_forever()
        self.higherBuild = None

        def newCallback(_: tuple[str, ...], data: dict[str, Any]) -> None:
            if self.higherBuild is None:
                self.higherBuild = data['buildid']
            else:

                def f() -> None:
                    self.master.data.control("stop", {}, ("builds", self.higherBuild))
                    self.higherBuild = None

                reactor.callLater(5.0, f)  # type: ignore[attr-defined]

        yield self.runTest(newCallback, flushErrors=True)

    @defer.inlineCallbacks
    def testTriggeredBuildIsNotCreated(self) -> InlineCallbacksType[None]:
        yield self.setup_config_triggered_build_not_created()

        def newCallback(_: tuple[str, ...], data: dict[str, Any]) -> None:
            self.master.data.control("stop", {}, ("builds", data['buildid']))

        yield self.runTest(newCallback)
