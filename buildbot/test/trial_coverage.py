
"""A Trial IReporter plugin that gathers coverage.py code-coverage information.

Once this plugin is installed, trial can be invoked a new --reporter option:

  trial --reporter-bwverbose-coverage ARGS

Once such a test run has finished, there will be a .coverage file in the
top-level directory. This file can be turned into a directory of .html files
(with index.html as the starting point) by running:

 coverage html -d OUTPUTDIR --omit=PREFIX1,PREFIX2,..

The 'coverage' tool thinks in terms of absolute filenames. 'coverage' doesn't
record data for files that come with Python, but it does record data for all
the various site-package directories. To show only information for Tahoe
source code files, you should provide --omit prefixes for everything else.
This probably means something like:

  --omit=/System/,/Library/,support/

Before using this, you need to install the 'coverage' package, which will
provide an executable tool named 'coverage' (as well as an importable
library). 'coverage report' will produce a basic text summary of the coverage
data. Our 'misc/coverage2text.py' tool produces a slightly more useful
summary, and 'misc/coverage2html.py' will produce a more useful HTML report.

"""

from twisted.trial.reporter import VerboseTextReporter

# These plugins are registered via twisted/plugins/allmydata_trial.py . See
# the notes there for an explanation of how that works.

# Some notes about how trial Reporters are used:
# * Reporters don't really get told about the suite starting and stopping.
# * The Reporter class is imported before the test classes are.
# * The test classes are imported before the Reporter is created. To get
#   control earlier than that requires modifying twisted/scripts/trial.py
# * Then Reporter.__init__ is called.
# * Then tests run, calling things like write() and addSuccess(). Each test is
#   framed by a startTest/stopTest call.
# * Then the results are emitted, calling things like printErrors,
#   printSummary, and wasSuccessful.
# So for code-coverage (not including import), start in __init__ and finish
# in printSummary. To include import, we have to start in our own import and
# finish in printSummary.

import coverage
cov = coverage.coverage()
cov.start()


class CoverageTextReporter(VerboseTextReporter):
    def __init__(self, *args, **kwargs):
        VerboseTextReporter.__init__(self, *args, **kwargs)

    def stop_coverage(self):
        cov.stop()
        cov.save()
        print "Coverage results written to .coverage"
    def printSummary(self):
        # for twisted-2.5.x
        self.stop_coverage()
        return VerboseTextReporter.printSummary(self)
    def done(self):
        # for twisted-8.x
        self.stop_coverage()
        return VerboseTextReporter.done(self)
