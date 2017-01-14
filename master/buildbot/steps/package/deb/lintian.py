# This program is free software; you can
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
Steps and objects related to lintian
"""

from __future__ import absolute_import
from __future__ import print_function

from buildbot import config
from buildbot.process import buildstep
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps.package import util as pkgutil
from buildbot.steps.shell import ShellCommand


class MaxQObserver(buildstep.LogLineObserver):

    def __init__(self):
        buildstep.LogLineObserver.__init__(self)
        self.failures = 0

    def outLineReceived(self, line):
        if line.startswith('TEST FAILURE:'):
            self.failures += 1


class DebLintian(ShellCommand):
    name = "lintian"
    description = ["Lintian running"]
    descriptionDone = ["Lintian"]

    fileloc = None
    suppressTags = []

    warnCount = 0
    errCount = 0

    flunkOnFailure = False
    warnOnFailure = True

    def __init__(self, fileloc=None, suppressTags=None, **kwargs):
        """
        Create the DebLintian object.

        @type fileloc: str
        @param fileloc: Location of the .deb or .changes to test.
        @type suppressTags: list
        @param suppressTags: List of tags to suppress.
        @type kwargs: dict
        @param kwargs: all other keyword arguments.
        """
        ShellCommand.__init__(self, **kwargs)
        if fileloc:
            self.fileloc = fileloc
        if suppressTags:
            self.suppressTags = suppressTags

        if not self.fileloc:
            config.error("You must specify a fileloc")

        self.command = ["lintian", "-v", self.fileloc]

        if self.suppressTags:
            for tag in self.suppressTags:
                self.command += ['--suppress-tags', tag]

        self.obs = pkgutil.WEObserver()
        self.addLogObserver('stdio', self.obs)

    def createSummary(self, log):
        """
        Create nice summary logs.

        @param log: log to create summary off of.
        """
        warnings = self.obs.warnings
        errors = self.obs.errors

        if warnings:
            self.addCompleteLog('%d Warnings' % len(warnings), "\n".join(warnings))
            self.warnCount = len(warnings)
        if errors:
            self.addCompleteLog('%d Errors' % len(errors), "\n".join(errors))
            self.errCount = len(errors)

    def evaluateCommand(self, cmd):
        if (cmd.rc != 0 or self.errCount):
            return FAILURE
        if self.warnCount:
            return WARNINGS
        return SUCCESS
