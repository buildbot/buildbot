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

from typing import TYPE_CHECKING

from twisted.internet import defer

from buildbot.plugins import steps
from buildbot.process.results import EXCEPTION
from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase

if TYPE_CHECKING:
    from buildbot.interfaces import IBuildStepFactory
    from buildbot.process.buildstep import BuildStep
    from buildbot.util.twisted import InlineCallbacksType


class TestLog(RunMasterBase):
    # master configuration

    @defer.inlineCallbacks
    def setup_config(self, step: BuildStep | IBuildStepFactory) -> InlineCallbacksType[None]:
        c = {}
        from buildbot.config import BuilderConfig  # noqa: PLC0415
        from buildbot.plugins import schedulers  # noqa: PLC0415
        from buildbot.process.factory import BuildFactory  # noqa: PLC0415

        c['schedulers'] = [schedulers.AnyBranchScheduler(name="sched", builderNames=["testy"])]

        f = BuildFactory()
        f.addStep(step)
        c['builders'] = [BuilderConfig(name="testy", workernames=["local1"], factory=f)]
        yield self.setup_master(c)

    @defer.inlineCallbacks
    def test_shellcommand(self) -> InlineCallbacksType[None]:
        testcase = self

        class MyStep(steps.ShellCommand):  # type: ignore[name-defined]
            def _newLog(
                self, name: str, type: str, logid: int, logEncoding: str | None = None
            ) -> None:
                r = super()._newLog(name, type, logid, logEncoding)
                testcase.curr_log = r  # type: ignore[attr-defined]
                return r

        step = MyStep(command='echo hello')

        yield self.setup_config(step)

        change = {
            "branch": "master",
            "files": ["foo.c"],
            "author": "me@foo.com",
            "committer": "me@foo.com",
            "comments": "good stuff",
            "revision": "HEAD",
            "project": "none",
        }
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(build['results'], SUCCESS)
        self.assertTrue(self.curr_log.finished)  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_mastershellcommand(self) -> InlineCallbacksType[None]:
        testcase = self

        class MyStep(steps.MasterShellCommand):  # type: ignore[name-defined]
            def _newLog(
                self, name: str, type: str, logid: int, logEncoding: str | None = None
            ) -> None:
                r = super()._newLog(name, type, logid, logEncoding)
                testcase.curr_log = r  # type: ignore[attr-defined]
                return r

        step = MyStep(command='echo hello')

        yield self.setup_config(step)

        change = {
            "branch": "master",
            "files": ["foo.c"],
            "author": "me@foo.com",
            "committer": "me@foo.com",
            "comments": "good stuff",
            "revision": "HEAD",
            "project": "none",
        }
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(build['results'], SUCCESS)
        self.assertTrue(self.curr_log.finished)  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_mastershellcommand_issue(self) -> InlineCallbacksType[None]:
        testcase = self

        class MyStep(steps.MasterShellCommand):  # type: ignore[name-defined]
            def _newLog(
                self, name: str, type: str, logid: int, logEncoding: str | None = None
            ) -> None:
                r = super()._newLog(name, type, logid, logEncoding)
                testcase.curr_log = r  # type: ignore[attr-defined]
                testcase.patch(r, "finish", lambda: defer.fail(RuntimeError('Could not finish')))
                return r

        step = MyStep(command='echo hello')

        yield self.setup_config(step)

        change = {
            "branch": "master",
            "files": ["foo.c"],
            "author": "me@foo.com",
            "committer": "me@foo.com",
            "comments": "good stuff",
            "revision": "HEAD",
            "project": "none",
        }
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertFalse(self.curr_log.finished)  # type: ignore[attr-defined]
        self.assertEqual(build['results'], EXCEPTION)
        errors = self.flushLoggedErrors()
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertEqual(error.getErrorMessage(), 'Could not finish')
