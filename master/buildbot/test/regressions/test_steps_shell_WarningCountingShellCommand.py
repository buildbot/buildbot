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

from __future__ import absolute_import
from __future__ import print_function

import re

from twisted.trial import unittest

from buildbot.steps.shell import WarningCountingShellCommand


class TestWarningCountingShellCommand(unittest.TestCase):

    # Makes sure that it is possible to suppress warnings even if the
    # warning extractor does not provide line information

    def testSuppressingLinelessWarningsPossible(self):
        # Use a warningExtractor that does not provide line
        # information
        w = WarningCountingShellCommand(
            warningExtractor=WarningCountingShellCommand.warnExtractWholeLine,
            command="echo")

        # Add suppression manually instead of using suppressionFile
        fileRe = None
        warnRe = ".*SUPPRESS.*"
        start = None
        end = None
        suppression = (fileRe, warnRe, start, end)
        w.addSuppression([suppression])

        # Now call maybeAddWarning
        warnings = []
        line = "this warning should be SUPPRESSed"
        match = re.match(".*warning.*", line)
        w.maybeAddWarning(warnings, line, match)

        # Finally make the suppressed warning was *not* added to the
        # list of warnings
        expectedWarnings = 0
        self.assertEqual(len(warnings), expectedWarnings)
