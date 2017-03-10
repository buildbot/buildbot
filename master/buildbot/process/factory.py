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

import warnings

from twisted.python import deprecate
from twisted.python import versions

from buildbot import interfaces
from buildbot import util
from buildbot.process.build import Build
from buildbot.process.buildstep import BuildStep
from buildbot.steps.shell import Compile
from buildbot.steps.shell import Configure
from buildbot.steps.shell import PerlModuleTest
from buildbot.steps.shell import ShellCommand
from buildbot.steps.shell import Test
from buildbot.steps.source.cvs import CVS
from buildbot.steps.source.svn import SVN


# deprecated, use BuildFactory.addStep
@deprecate.deprecated(versions.Version("buildbot", 0, 8, 6))
def s(steptype, **kwargs):
    # convenience function for master.cfg files, to create step
    # specification tuples
    return interfaces.IBuildStepFactory(steptype(**kwargs))


class BuildFactory(util.ComparableMixin):

    """
    @cvar  buildClass: class to use when creating builds
    @type  buildClass: L{buildbot.process.build.Build}
    """
    buildClass = Build
    useProgress = 1
    workdir = "build"
    compare_attrs = ('buildClass', 'steps', 'useProgress', 'workdir')

    def __init__(self, steps=None):
        self.steps = []
        if steps:
            self.addSteps(steps)

    def newBuild(self, requests):
        """Create a new Build instance.

        @param requests: a list of buildrequest dictionaries describing what is
        to be built
        """
        b = self.buildClass(requests)
        b.useProgress = self.useProgress
        b.workdir = self.workdir
        b.setStepFactories(self.steps)
        return b

    def addStep(self, step, **kwargs):
        if kwargs or (isinstance(step, type(BuildStep)) and issubclass(step, BuildStep)):
            warnings.warn(
                "Passing a BuildStep subclass to factory.addStep is "
                "deprecated. Please pass a BuildStep instance instead.",
                DeprecationWarning, stacklevel=2)
            step = step(**kwargs)
        self.steps.append(interfaces.IBuildStepFactory(step))

    def addSteps(self, steps):
        for s in steps:
            self.addStep(s)

# BuildFactory subclasses for common build tools


class _DefaultCommand(object):
    # Used to indicate a default command to the step.
    pass


class GNUAutoconf(BuildFactory):

    def __init__(self, source, configure="./configure",
                 configureEnv=None,
                 configureFlags=None,
                 reconf=None,
                 compile=_DefaultCommand,
                 test=_DefaultCommand,
                 distcheck=_DefaultCommand):
        if configureEnv is None:
            configureEnv = {}
        if configureFlags is None:
            configureFlags = []
        if compile is _DefaultCommand:
            compile = ["make", "all"]
        if test is _DefaultCommand:
            test = ["make", "check"]
        if distcheck is _DefaultCommand:
            distcheck = ["make", "distcheck"]

        BuildFactory.__init__(self, [source])

        if reconf is True:
            reconf = ["autoreconf", "-si"]
        if reconf is not None:
            self.addStep(
                ShellCommand(name="autoreconf", command=reconf, env=configureEnv))

        if configure is not None:
            # we either need to wind up with a string (which will be
            # space-split), or with a list of strings (which will not). The
            # list of strings is the preferred form.
            if isinstance(configure, str):
                if configureFlags:
                    assert " " not in configure  # please use list instead
                    command = [configure] + configureFlags
                else:
                    command = configure
            else:
                assert isinstance(configure, (list, tuple))
                command = configure + configureFlags
            self.addStep(Configure(command=command, env=configureEnv))
        if compile is not None:
            self.addStep(Compile(command=compile, env=configureEnv))
        if test is not None:
            self.addStep(Test(command=test, env=configureEnv))
        if distcheck is not None:
            self.addStep(Test(command=distcheck, env=configureEnv))


class CPAN(BuildFactory):

    def __init__(self, source, perl="perl"):
        BuildFactory.__init__(self, [source])
        self.addStep(Configure(command=[perl, "Makefile.PL"]))
        self.addStep(Compile(command=["make"]))
        self.addStep(PerlModuleTest(command=["make", "test"]))


class Distutils(BuildFactory):

    def __init__(self, source, python="python", test=None):
        BuildFactory.__init__(self, [source])
        self.addStep(Compile(command=[python, "./setup.py", "build"]))
        if test is not None:
            self.addStep(Test(command=test))


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
                 buildpython=None, trialpython=None, trial=None,
                 testpath=".", randomly=None, recurse=None,
                 tests=None, useTestCaseNames=False, env=None):
        BuildFactory.__init__(self, [source])
        assert tests or useTestCaseNames, "must use one or the other"
        if buildpython is None:
            buildpython = ["python"]
        if trialpython is None:
            trialpython = []
        if trial is not None:
            self.trial = trial
        if randomly is not None:
            self.randomly = randomly
        if recurse is not None:
            self.recurse = recurse

        from buildbot.steps.python_twisted import Trial
        buildcommand = buildpython + ["./setup.py", "build"]
        self.addStep(Compile(command=buildcommand, env=env))
        self.addStep(Trial(
                     python=trialpython, trial=self.trial,
                     testpath=testpath,
                     tests=tests, testChanges=useTestCaseNames,
                     randomly=self.randomly,
                     recurse=self.recurse,
                     env=env,
                     ))


# compatibility classes, will go away. Note that these only offer
# compatibility at the constructor level: if you have subclassed these
# factories, your subclasses are unlikely to still work correctly.

ConfigurableBuildFactory = BuildFactory


class BasicBuildFactory(GNUAutoconf):
    # really a "GNU Autoconf-created tarball -in-CVS tree" builder

    def __init__(self, cvsroot, cvsmodule,
                 configure=None, configureEnv=None,
                 compile="make all",
                 test="make check", cvsCopy=False):
        if configureEnv is None:
            configureEnv = {}
        mode = "full"
        method = "clobber"
        if cvsCopy:
            method = "copy"
        source = CVS(
            cvsroot=cvsroot, cvsmodule=cvsmodule, mode=mode, method=method)
        GNUAutoconf.__init__(self, source,
                             configure=configure, configureEnv=configureEnv,
                             compile=compile,
                             test=test)


class QuickBuildFactory(BasicBuildFactory):
    useProgress = False

    def __init__(self, cvsroot, cvsmodule,
                 configure=None, configureEnv=None,
                 compile="make all",
                 test="make check", cvsCopy=False):
        if configureEnv is None:
            configureEnv = {}
        mode = "incremental"
        source = CVS(cvsroot=cvsroot, cvsmodule=cvsmodule, mode=mode)
        GNUAutoconf.__init__(self, source,
                             configure=configure, configureEnv=configureEnv,
                             compile=compile,
                             test=test)


class BasicSVN(GNUAutoconf):

    def __init__(self, svnurl,
                 configure=None, configureEnv=None,
                 compile="make all",
                 test="make check"):
        if configureEnv is None:
            configureEnv = {}
        source = SVN(svnurl=svnurl, mode="incremental")
        GNUAutoconf.__init__(self, source,
                             configure=configure, configureEnv=configureEnv,
                             compile=compile,
                             test=test)
