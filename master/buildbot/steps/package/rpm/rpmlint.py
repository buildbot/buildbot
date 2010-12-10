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
# Portions Copyright Steve 'Ashcrow' Milner <smilner+buildbot@redhat.com>
"""
Steps and objects related to rpmlint.
"""

from buildbot.steps.shell import Test


class RpmLint(Test):
    """
    Rpmlint build step.
    """

    description = ["Checking for RPM/SPEC issues"]
    descriptionDone = ["Finished checking RPM/SPEC issues"]

    def __init__(self, fileloc="*rpm", **kwargs):
        """
        Create the Rpmlint object.

        @type fileloc: str
        @param fileloc: Location glob of the specs or rpms.
        @type kwargs: dict
        @param fileloc: all other keyword arguments.
        """
        Test.__init__(self, **kwargs)
        self.command = ["/usr/bin/rpmlint", "-i"]
        self.command.append(fileloc)

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
        self.addCompleteLog('Rpmlint Warnings', "".join(warnings))
        self.addCompleteLog('Rpmlint Errors', "".join(errors))
