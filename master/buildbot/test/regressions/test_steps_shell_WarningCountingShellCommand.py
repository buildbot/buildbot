from twisted.trial import unittest

import re
from buildbot.steps.shell import WarningCountingShellCommand

class TestWarningCountingShellCommand(unittest.TestCase):

    # Makes sure that it is possible to supress warnings even if the
    # warning extractor does not provie line information
    def testSuppressingLinelessWarningsPossible(self):
        # Use a warningExtractor that does not provide line
        # information
        w = WarningCountingShellCommand(
            warningExtractor=WarningCountingShellCommand.warnExtractWholeLine)

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
        self.assertEquals(len(warnings), expectedWarnings)
