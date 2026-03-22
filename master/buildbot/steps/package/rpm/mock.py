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
# Portions Copyright Buildbot Team Members
# Portions Copyright Marius Rieder <marius.rieder@durchmesser.ch>


from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from twisted.internet import defer

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver

if TYPE_CHECKING:
    from collections.abc import Generator

    from buildbot.process.build import Build
    from buildbot.util.twisted import InlineCallbacksType


class MockStateObserver(logobserver.LogLineObserver):
    """Supports reading state changes from Mock state.log from mock version
    1.1.23."""

    _line_re = re.compile(r'^.*(Start|Finish): (.*)$')

    def outLineReceived(self, line: str) -> None:
        m = self._line_re.search(line.strip())
        if m:
            if m.group(1) == "Start":
                self.step.descriptionSuffix = [f"[{m.group(2)}]"]
            else:
                self.step.descriptionSuffix = None
            self.step.updateSummary()


class Mock(buildstep.ShellMixin, buildstep.CommandMixin, buildstep.BuildStep):
    """Add the mock logfiles and clean them if they already exist. Add support
    for the root and resultdir parameter of mock."""

    name = "mock"

    renderables = ["root", "resultdir"]

    haltOnFailure = True
    flunkOnFailure = True

    mock_logfiles = ['build.log', 'root.log', 'state.log']

    root = None
    resultdir = None

    def __init__(
        self, root: str | None = None, resultdir: str | None = None, **kwargs: Any
    ) -> None:
        kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
        super().__init__(**kwargs)
        if root:
            self.root = root
        if resultdir:
            self.resultdir = resultdir

        if not self.root:
            config.error("You must specify a mock root")

        self.command = ['mock', '--root', cast(str, self.root)]
        if self.resultdir:
            self.command += ['--resultdir', self.resultdir]

    @defer.inlineCallbacks
    def run(self) -> InlineCallbacksType[int]:
        # Try to remove the old mock logs first.
        build = cast("Build", self.build)
        if self.resultdir:
            for lname in self.mock_logfiles:
                self.logfiles[lname] = build.path_module.join(self.resultdir, lname)
        else:
            for lname in self.mock_logfiles:
                self.logfiles[lname] = lname
        self.addLogObserver('state.log', MockStateObserver())

        yield self.runRmdir([  # type: ignore[arg-type]
            build.path_module.join('build', self.logfiles[l]) for l in self.mock_logfiles
        ])

        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        return cmd.results()

    def getResultSummary(self) -> dict[str, str]:
        self.descriptionSuffix = None
        return super().getResultSummary()


class MockBuildSRPM(Mock):
    """Build a srpm within a mock. Requires a spec file and a sources dir."""

    name = "mockbuildsrpm"

    description = ["mock buildsrpm"]
    descriptionDone = ["mock buildsrpm"]

    spec = None
    sources = '.'

    def __init__(self, spec: str | None = None, sources: str | None = None, **kwargs: Any) -> None:
        """
        Creates the MockBuildSRPM object.

        @type spec: str
        @param spec: the path of the specfiles.
        @type sources: str
        @param sources: the path of the sources dir.
        @type kwargs: dict
        @param kwargs: All further keyword arguments.
        """
        super().__init__(**kwargs)
        if spec:
            self.spec = spec
        if sources:
            self.sources = sources

        if not self.spec:
            config.error("You must specify a spec file")
        if not self.sources:
            config.error("You must specify a sources dir")

        cast(list[str], self.command).extend([
            '--buildsrpm',
            '--spec',
            cast(str, self.spec),
            '--sources',
            self.sources,
        ])
        self.addLogObserver('stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    def logConsumer(self) -> Generator[None, tuple[str, str], None]:
        r = re.compile(r"Wrote: .*/([^/]*.src.rpm)")
        while True:
            _, line = yield
            m = r.search(line)
            if m:
                self.setProperty("srpm", m.group(1), 'MockBuildSRPM')


class MockRebuild(Mock):
    """Rebuild a srpm within a mock. Requires a srpm file."""

    name = "mock"

    description = ["mock rebuilding srpm"]
    descriptionDone = ["mock rebuild srpm"]

    srpm = None

    def __init__(self, srpm: str | None = None, **kwargs: Any) -> None:
        """
        Creates the MockRebuildRPM object.

        @type srpm: str
        @param srpm: the path of the srpm file.
        @type kwargs: dict
        @param kwargs: All further keyword arguments.
        """
        super().__init__(**kwargs)
        if srpm:
            self.srpm = srpm

        if not self.srpm:
            config.error("You must specify a srpm")

        cast(list[str], self.command).extend(['--rebuild', cast(str, self.srpm)])
