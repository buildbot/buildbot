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

from buildbot.steps.shell import Test
from buildbot import config

class DebLintian(Test):
    name = "lintian"
    description = ["Lintian running"]
    descriptionDone = ["Lintian"]

    warningPattern = '.*W: .*'

    fileloc = None

    def __init__(self, fileloc=None, **kwargs):
        """
        Create the DebLintian object.
        
        @type fileloc: str
        @param fileloc: Location of the .deb or .changes to test.
        @type kwargs: dict
        @param kwargs: all other keyword arguments.
        """
        Test.__init__(self, **kwargs)
        if fileloc:
            self.fileloc = fileloc

        if not self.fileloc:
            config.error("You must specify a fileloc")

        self.command = ["lintian", "-v", self.fileloc]

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
