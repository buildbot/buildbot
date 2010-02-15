
from zope.interface import implements
from twisted.trial.itrial import IReporter
from twisted.plugin import IPlugin

# register a plugin that can create our CoverageReporter. The reporter itself
# lives separately, in buildbot/test/trial_figleaf.py

# note that this buildbot_trial.py file is *not* in a package: there is no
# __init__.py in our parent directory. This is important, because otherwise
# ours would fight with Twisted's. When trial looks for plugins, it merely
# executes all the *.py files it finds in any twisted/plugins/ subdirectories
# of anything on sys.path . The namespace that results from executing these
# .py files is examined for instances which provide both IPlugin and the
# target interface (in this case, trial is looking for IReporter instances).
# Each such instance tells the application how to create a plugin by naming
# the module and class that should be instantiated.

# When installing our package via setup.py, arrange for this file to be
# installed to the system-wide twisted/plugins/ directory.

class _Reporter(object):
    implements(IPlugin, IReporter)

    def __init__(self, name, module, description, longOpt, shortOpt, klass):
        self.name = name
        self.module = module
        self.description = description
        self.longOpt = longOpt
        self.shortOpt = shortOpt
        self.klass = klass


bwcov = _Reporter("Code-Coverage Reporter (colorless)",
                  "buildbot.test.trial_coverage",
                  description="Colorless verbose output (with 'coverage' coverage)",
                  longOpt="bwverbose-coverage",
                  shortOpt=None,
                  klass="CoverageTextReporter")

