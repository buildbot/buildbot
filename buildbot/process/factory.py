# -*- test-case-name: buildbot.test.test_step -*-

from buildbot import util
from buildbot.process.base import Build
from buildbot.process.buildstep import BuildStep
from buildbot.steps.source import CVS, SVN
from buildbot.steps.shell import Configure, Compile, Test, PerlModuleTest

# deprecated, use BuildFactory.addStep
def s(steptype, **kwargs):
    # convenience function for master.cfg files, to create step
    # specification tuples
    return (steptype, kwargs)

class ArgumentsInTheWrongPlace(Exception):
    """When calling BuildFactory.addStep(stepinstance), addStep() only takes
    one argument. You passed extra arguments to addStep(), which you probably
    intended to pass to your BuildStep constructor instead. For example, you
    should do::

     f.addStep(ShellCommand(command=['echo','stuff'], haltOnFailure=True))

    instead of::

     f.addStep(ShellCommand(command=['echo','stuff']), haltOnFailure=True)
    """

class BuildFactory(util.ComparableMixin):
    """
    @cvar  buildClass: class to use when creating builds
    @type  buildClass: L{buildbot.process.base.Build}
    """
    buildClass = Build
    useProgress = 1
    compare_attrs = ['buildClass', 'steps', 'useProgress']

    def __init__(self, steps=None):
        if steps is None:
            steps = []
        self.steps = [self._makeStepFactory(s) for s in steps]

    def _makeStepFactory(self, step_or_factory):
        if isinstance(step_or_factory, BuildStep):
            return step_or_factory.getStepFactory()
        return step_or_factory

    def newBuild(self, request):
        """Create a new Build instance.
        @param request: a L{base.BuildRequest} describing what is to be built
        """
        b = self.buildClass(request)
        b.useProgress = self.useProgress
        b.setStepFactories(self.steps)
        return b

    def addStep(self, step_or_factory, **kwargs):
        if isinstance(step_or_factory, BuildStep):
            if kwargs:
                raise ArgumentsInTheWrongPlace()
            s = step_or_factory.getStepFactory()
        else:
            s = (step_or_factory, dict(kwargs))
        self.steps.append(s)

    def addSteps(self, steps):
        self.steps.extend([ s.getStepFactory() for s in steps ])

# BuildFactory subclasses for common build tools

class GNUAutoconf(BuildFactory):
    def __init__(self, source, configure="./configure",
                 configureEnv={},
                 configureFlags=[],
                 compile=["make", "all"],
                 test=["make", "check"]):
        BuildFactory.__init__(self, [source])
        if configure is not None:
            # we either need to wind up with a string (which will be
            # space-split), or with a list of strings (which will not). The
            # list of strings is the preferred form.
            if type(configure) is str:
                if configureFlags:
                    assert not " " in configure # please use list instead
                    command = [configure] + configureFlags
                else:
                    command = configure
            else:
                assert isinstance(configure, (list, tuple))
                command = configure + configureFlags
            self.addStep(Configure, command=command, env=configureEnv)
        if compile is not None:
            self.addStep(Compile, command=compile)
        if test is not None:
            self.addStep(Test, command=test)

class CPAN(BuildFactory):
    def __init__(self, source, perl="perl"):
        BuildFactory.__init__(self, [source])
        self.addStep(Configure, command=[perl, "Makefile.PL"])
        self.addStep(Compile, command=["make"])
        self.addStep(PerlModuleTest, command=["make", "test"])

class Distutils(BuildFactory):
    def __init__(self, source, python="python", test=None):
        BuildFactory.__init__(self, [source])
        self.addStep(Compile, command=[python, "./setup.py", "build"])
        if test is not None:
            self.addStep(Test, command=test)

class Trial(BuildFactory):
    """Build a python module that uses distutils and trial. Set 'tests' to
    the module in which the tests can be found, or set useTestCaseNames=True
    to always have trial figure out which tests to run (based upon which
    files have been changed).

    See docs/factories.xhtml for usage samples. Not all of the Trial
    BuildStep options are available here, only the most commonly used ones.
    To get complete access, you will need to create a custom
    BuildFactory."""

    trial = "trial"
    randomly = False
    recurse = False

    def __init__(self, source,
                 buildpython=["python"], trialpython=[], trial=None,
                 testpath=".", randomly=None, recurse=None,
                 tests=None,  useTestCaseNames=False, env=None):
        BuildFactory.__init__(self, [source])
        assert tests or useTestCaseNames, "must use one or the other"
        if trial is not None:
            self.trial = trial
        if randomly is not None:
            self.randomly = randomly
        if recurse is not None:
            self.recurse = recurse

        from buildbot.steps.python_twisted import Trial
        buildcommand = buildpython + ["./setup.py", "build"]
        self.addStep(Compile, command=buildcommand, env=env)
        self.addStep(Trial,
                     python=trialpython, trial=self.trial,
                     testpath=testpath,
                     tests=tests, testChanges=useTestCaseNames,
                     randomly=self.randomly,
                     recurse=self.recurse,
                     env=env,
                     )


# compatibility classes, will go away. Note that these only offer
# compatibility at the constructor level: if you have subclassed these
# factories, your subclasses are unlikely to still work correctly.

ConfigurableBuildFactory = BuildFactory

class BasicBuildFactory(GNUAutoconf):
    # really a "GNU Autoconf-created tarball -in-CVS tree" builder

    def __init__(self, cvsroot, cvsmodule,
                 configure=None, configureEnv={},
                 compile="make all",
                 test="make check", cvsCopy=False):
        mode = "clobber"
        if cvsCopy:
            mode = "copy"
        source = s(CVS, cvsroot=cvsroot, cvsmodule=cvsmodule, mode=mode)
        GNUAutoconf.__init__(self, source,
                             configure=configure, configureEnv=configureEnv,
                             compile=compile,
                             test=test)

class QuickBuildFactory(BasicBuildFactory):
    useProgress = False

    def __init__(self, cvsroot, cvsmodule,
                 configure=None, configureEnv={},
                 compile="make all",
                 test="make check", cvsCopy=False):
        mode = "update"
        source = s(CVS, cvsroot=cvsroot, cvsmodule=cvsmodule, mode=mode)
        GNUAutoconf.__init__(self, source,
                             configure=configure, configureEnv=configureEnv,
                             compile=compile,
                             test=test)

class BasicSVN(GNUAutoconf):

    def __init__(self, svnurl,
                 configure=None, configureEnv={},
                 compile="make all",
                 test="make check"):
        source = s(SVN, svnurl=svnurl, mode="update")
        GNUAutoconf.__init__(self, source,
                             configure=configure, configureEnv=configureEnv,
                             compile=compile,
                             test=test)
