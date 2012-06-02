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
"""
Steps and objects related to mock building.
"""

import re
import os.path

from buildbot.steps.shell import ShellCommand
from buildbot.process import buildstep

class Mock(ShellCommand):
    """Add the mock logfiles and clean them if they already exist. Add support
    for the root and resultdir parameter of mock."""

    name = "mock"

    haltOnFailure = 1
    flunkOnFailure = 1

    logfiles = {
        "build.log": "build.log",
        "root.log": "root.log",
        "state.log": "state.log",
    }

    root = None
    resultdir = None

    def __init__(self,
                 root=None,
                 resultdir=None,
                 **kwargs):
        """
        Creates the Mock object.

        @type root: str
        @param root: the name of the mock buildroot
        @type resultdir: str
        @param resultdir: the path of the result dir
        @type kwargs: dict
        @param kwargs: All further keyword arguments.
        """
        ShellCommand.__init__(self, **kwargs)
        if root:
            self.root = root
        if resultdir:
            self.resultdir = resultdir
        if self.resultdir:
            for lname in self.logfiles.keys():
                self.logfiles[lname] = os.path.join(resultdir, self.logfiles[lname])

        assert self.root, "No mock root specified"

        self.command = ['mock', '--root', self.root]
        if self.resultdir:
            self.command += ['--resultdir', 'result']

    def start(self):
        """
        Try to remove the old mock logs first.
        """

        cmd = buildstep.RemoteCommand('rmdir', {'dir': ['build/'+ f for f in self.logfiles.values()] })
        d = self.runCommand(cmd)
        d.addCallback(self.removeDone)
        d.addErrback(self.failed)

    def removeDone(self, cmd):
        """
        Now run the actual mock build.
        """
        ShellCommand.start(self)

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
        Mock.__init__(self, **kwargs)
        if spec:
            self.spec = spec
        if sources:
            self.sources = sources

        assert self.spec, "No specfile specified"
        assert self.sources, "No sources dir specified"

        self.command += ['--buildsrpm', '--spec', self.spec,
                         '--sources', self.sources]

    def commandComplete(self, cmd):
        out = cmd.logs['build.log'].getText()
        m = re.search(r"Wrote: .*/([^/]*.src.rpm)", out)
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
        Mock.__init__(self, **kwargs)
        if srpm:
            self.srpm = srpm

        assert self.srpm, "No srpm specified"
        
        self.command += ['rebuild', self.srpm]
