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


import re

from twisted.internet import defer

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver


class MockStateObserver(logobserver.LogLineObserver):
    """Supports reading state changes from Mock state.log from mock version
    1.1.23."""

    _line_re = re.compile(r'^.*(Start|Finish): (.*)$')

    def outLineReceived(self, line):
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

    haltOnFailure = 1
    flunkOnFailure = 1

    mock_logfiles = ['build.log', 'root.log', 'state.log']

    root = None
    resultdir = None

    def __init__(self,
                 root=None,
                 resultdir=None,
                 **kwargs):
        kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
        super().__init__(**kwargs)
        if root:
            self.root = root
        if resultdir:
            self.resultdir = resultdir

        if not self.root:
            config.error("You must specify a mock root")

        self.command = ['mock', '--root', self.root]
        if self.resultdir:
            self.command += ['--resultdir', self.resultdir]

    @defer.inlineCallbacks
    def run(self):
        # Try to remove the old mock logs first.
        if self.resultdir:
            for lname in self.mock_logfiles:
                self.logfiles[lname] = self.build.path_module.join(self.resultdir, lname)
        else:
            for lname in self.mock_logfiles:
                self.logfiles[lname] = lname
        self.addLogObserver('state.log', MockStateObserver())

        yield self.runRmdir([self.build.path_module.join('build', self.logfiles[l])
                             for l in self.mock_logfiles])

        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        return cmd.results()

    def getResultSummary(self):
        self.descriptionSuffix = None
        return super().getResultSummary()


class MockBuildSRPM(Mock):

    """Build a srpm within a mock. Requires a spec file and a sources dir."""

    name = "mockbuildsrpm"

    description = ["mock buildsrpm"]
    descriptionDone = ["mock buildsrpm"]

    spec = None
    sources = '.'

    def __init__(self,
                 spec=None,
                 sources=None,
                 **kwargs):
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

        self.command += ['--buildsrpm', '--spec', self.spec,
                         '--sources', self.sources]
        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    def logConsumer(self):
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

    def __init__(self, srpm=None, **kwargs):
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

        self.command += ['--rebuild', self.srpm]
