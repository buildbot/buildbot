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

from __future__ import absolute_import
from __future__ import print_function

from buildbot.steps.package import util as pkgutil
from buildbot.steps.shell import Test


class RpmLint(Test):

    """
    Rpmlint build step.
    """

    name = "rpmlint"

    description = ["Checking for RPM/SPEC issues"]
    descriptionDone = ["Finished checking RPM/SPEC issues"]

    fileloc = '.'
    config = None

    def __init__(self,
                 fileloc=None,
                 config=None,
                 **kwargs):
        """
        Create the Rpmlint object.

        @type fileloc: str
        @param fileloc: Location glob of the specs or rpms.
        @type config: str
        @param config: path to the rpmlint user config.
        @type kwargs: dict
        @param fileloc: all other keyword arguments.
        """
        Test.__init__(self, **kwargs)
        if fileloc:
            self.fileloc = fileloc
        if config:
            self.config = config
        self.addFactoryArguments(fileloc=fileloc, config=config)

        self.command = ["rpmlint", "-i"]
        if self.config:
            self.command += ['-f', self.config]
        self.command.append(self.fileloc)

        self.obs = pkgutil.WEObserver()
        self.addLogObserver('stdio', self.obs)

    def createSummary(self, log):
        """
        Create nice summary logs.

        @param log: log to create summary off of.
        """
        warnings = self.obs.warnings
        errors = []
        if warnings:
            self.addCompleteLog('%d Warnings' % len(warnings), "\n".join(warnings))
        if errors:
            self.addCompleteLog('%d Errors' % len(errors), "\n".join(errors))
