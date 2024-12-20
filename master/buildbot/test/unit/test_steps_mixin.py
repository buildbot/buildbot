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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process import buildstep
from buildbot.process.results import SUCCESS
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


class TestStep(buildstep.ShellMixin, buildstep.BuildStep):
    def __init__(self, text):
        self.setupShellMixin({})
        super().__init__()
        self.text = text

    @defer.inlineCallbacks
    def run(self):
        for file in self.build.allFiles():
            cmd = yield self.makeRemoteShellCommand(command=["echo", "build_file", file])
            yield self.runCommand(cmd)
        version = self.build.getWorkerCommandVersion("shell", None)
        if version != "99.99":
            cmd = yield self.makeRemoteShellCommand(command=["echo", "version", version])
            yield self.runCommand(cmd)
        cmd = yield self.makeRemoteShellCommand(command=["echo", "done", self.text])
        yield self.runCommand(cmd)
        return SUCCESS


class TestTestBuildStepMixin(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    @defer.inlineCallbacks
    def test_setup_build(self):
        self.setup_build(
            worker_version={"*": "2.9"}, worker_env={"key": "value"}, build_files=["build.txt"]
        )
        self.setup_step(TestStep("step1"))
        self.expect_commands(
            ExpectShell(
                workdir="wkdir", command=["echo", "build_file", "build.txt"], env={"key": "value"}
            ).exit(0),
            ExpectShell(
                workdir="wkdir", command=["echo", "version", "2.9"], env={"key": "value"}
            ).exit(0),
            ExpectShell(
                workdir="wkdir", command=["echo", "done", "step1"], env={"key": "value"}
            ).exit(0),
        )
        self.expect_outcome(SUCCESS)
        yield self.run_step()

    @defer.inlineCallbacks
    def test_old_setup_step_args(self):
        with assertProducesWarnings(
            DeprecatedApiWarning,
            num_warnings=3,
            message_pattern=".*has been deprecated, use setup_build\\(\\) to pass this information",
        ):
            self.setup_step(
                TestStep("step1"),
                worker_version={"*": "2.9"},
                worker_env={"key": "value"},
                build_files=["build.txt"],
            )
        self.expect_commands(
            ExpectShell(
                workdir="wkdir", command=["echo", "build_file", "build.txt"], env={"key": "value"}
            ).exit(0),
            ExpectShell(
                workdir="wkdir", command=["echo", "version", "2.9"], env={"key": "value"}
            ).exit(0),
            ExpectShell(
                workdir="wkdir", command=["echo", "done", "step1"], env={"key": "value"}
            ).exit(0),
        )
        self.expect_outcome(SUCCESS)

        yield self.run_step()

    def test_get_nth_step(self):
        self.setup_step(TestStep("step1"))
        self.assertTrue(isinstance(self.get_nth_step(0), TestStep))

        with assertProducesWarning(DeprecatedApiWarning, "step attribute has been deprecated"):
            self.assertTrue(isinstance(self.step, TestStep))

    @defer.inlineCallbacks
    def test_multiple_steps(self):
        self.setup_step(TestStep("step1"))
        self.setup_step(TestStep("step2"))
        self.expect_commands(
            ExpectShell(workdir="wkdir", command=["echo", "done", "step1"]).stdout("out1").exit(0),
            ExpectShell(workdir="wkdir", command=["echo", "done", "step2"]).stdout("out2").exit(0),
        )
        self.expect_log_file("stdio", "out1\n", step_index=0)
        self.expect_log_file("stdio", "out2\n", step_index=1)
        self.expect_outcome(SUCCESS)
        self.expect_outcome(SUCCESS)
        yield self.run_step()
