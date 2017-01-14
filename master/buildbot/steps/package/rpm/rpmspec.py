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
# Portions Copyright Dan Radez <dradez+buildbot@redhat.com>
# Portions Copyright Steve 'Ashcrow' Milner <smilner+buildbot@redhat.com>
"""
library to populate parameters from and rpmspec file into a memory structure
"""

from __future__ import absolute_import
from __future__ import print_function

import re

from buildbot.steps.shell import ShellCommand


class RpmSpec(ShellCommand):

    """
    read parameters out of an rpm spec file
    """

    # initialize spec info vars and get them from the spec file
    n_regex = re.compile(r'^Name:[ ]*([^\s]*)')
    v_regex = re.compile(r'^Version:[ ]*([0-9\.]*)')

    def __init__(self, specfile=None, **kwargs):
        """
        Creates the RpmSpec object.

        @type specfile: str
        @param specfile: the name of the specfile to get the package
            name and version from
        @type kwargs: dict
        @param kwargs: All further keyword arguments.
        """
        ShellCommand.__init__(self, **kwargs)

        self.specfile = specfile
        self._pkg_name = None
        self._pkg_version = None
        self._loaded = False

    def load(self):
        """
        call this function after the file exists to populate properties
        """
        # If we are given a string, open it up else assume it's something we
        # can call read on.
        if isinstance(self.specfile, str):
            f = open(self.specfile, 'r')
        else:
            f = self.specfile

        for line in f:
            if self.v_regex.match(line):
                self._pkg_version = self.v_regex.match(line).group(1)
            if self.n_regex.match(line):
                self._pkg_name = self.n_regex.match(line).group(1)
        f.close()
        self._loaded = True

    # Read-only properties
    loaded = property(lambda self: self._loaded)
    pkg_name = property(lambda self: self._pkg_name)
    pkg_version = property(lambda self: self._pkg_version)
