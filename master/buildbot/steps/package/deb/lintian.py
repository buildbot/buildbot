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

from buildbot.steps.shell import WarningCountingShellCommand
from buildbot import config

class DebLintian(WarningCountingShellCommand):
    name = "lintian"
    description = ["Lintian running"]
    descriptionDone = ["Lintian"]

    warningPattern = '.*W: .*'

    fileloc = None
    suppressTags = []

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
        WarningCountingShellCommand.__init__(self, **kwargs)
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

    def createSummary(self, log):
        """
        Create nice summary logs.
        
        @param log: log to create summary off of.
        """
        warnings = []
        errors = []
        for line in log.readlines():
            if ' W: ' in line:
                warnings.append(line)
            elif ' E: ' in line:
                errors.append(line)

        if warnings:
            self.addCompleteLog('%d Warnings' % len(warnings), "".join(warnings))
        if errors:
            self.addCompleteLog('%d Errors' % len(errors), "".join(errors))
