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

from twisted.trial import unittest

import re

from buildbot.steps.shell import WarningCountingShellCommand


class TestWarningCountingShellCommand(unittest.TestCase):

    # Makes sure that it is possible to supress warnings even if the
    # warning extractor does not provie line information
    def testSuppressingLinelessWarningsPossible(self):
        # Use a warningExtractor that does not provide line
        # information
        w = WarningCountingShellCommand()

        # Add suppression manually instead of using suppressionFile
        fileRe = None
        warnRe = ".*SUPPRESS.*"
        start = None
        end = None
        suppression = (fileRe, warnRe, start, end)
        w.addSuppression([suppression])

        # Now call maybeAddWarning
        line = "this warning should be SUPPRESSed"
        match = re.match(".*warning.*", line)
        # Make sure the suppressed warning was *not* added to the list of warnings
        self.assertEquals(w.parseLine(line, match, w.warningExtractor), None)
