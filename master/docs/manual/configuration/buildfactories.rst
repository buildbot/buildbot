.. _Build-Factories:

Build Factories
===============

Each Builder is equipped with a ``build factory``, which defines the steps used to perform that particular type of build.
This factory is created in the configuration file, and attached to a Builder through the ``factory`` element of its dictionary.

The steps used by these builds are defined in the next section, :ref:`Build-Steps`.

.. note::
    Build factories are used with builders, and are not added directly to the buildmaster configuration dictionary.

.. contents::
    :depth: 1
    :local:

.. _BuildFactory:

.. index:: Build Factory

Defining a Build Factory
------------------------

A :class:`BuildFactory` defines the steps that every build will follow.
Think of it as a glorified script.
For example, a build factory which consists of an SVN checkout followed by a ``make build`` would be configured as follows::

    from buildbot.plugins import util, steps

    f = util.BuildFactory()
    f.addStep(steps.SVN(repourl="http://..", mode="incremental"))
    f.addStep(steps.Compile(command=["make", "build"]))

This factory would then be attached to one builder (or several, if desired)::

    c['builders'].append(
        BuilderConfig(name='quick', workernames=['bot1', 'bot2'], factory=f))

It is also possible to pass a list of steps into the :class:`BuildFactory` when it is created.
Using :meth:`addStep` is usually simpler, but there are cases where it is more convenient to create the list of steps ahead of time, perhaps using some Python tricks to generate the steps.

::

    from buildbot.plugins import steps, util

    all_steps = [
        steps.CVS(cvsroot=CVSROOT, cvsmodule="project", mode="update"),
        steps.Compile(command=["make", "build"]),
    ]
    f = util.BuildFactory(all_steps)

Finally, you can also add a sequence of steps all at once::

    f.addSteps(all_steps)

Attributes
~~~~~~~~~~

The following attributes can be set on a build factory after it is created, e.g.,

::

    f = util.BuildFactory()
    f.useProgress = False

:attr:`useProgress`
    (defaults to ``True``): if ``True``, the buildmaster keeps track of how long each step takes, so it can provide estimates of how long future builds will take.
    If builds are not expected to take a consistent amount of time (such as incremental builds in which a random set of files are recompiled or tested each time), this should be set to ``False`` to inhibit progress-tracking.

:attr:`workdir`
    (defaults to 'build'): workdir given to every build step created by this factory as default.
    The workdir can be overridden in a build step definition.

    If this attribute is set to a string, that string will be used for constructing the workdir (worker base + builder builddir + workdir).
    The attribute can also be a Python callable, for more complex cases, as described in :ref:`Factory-Workdir-Functions`.

.. _DynamicBuildFactories:

Dynamic Build Factories
------------------------

In some cases you may not know what commands to run until after you checkout the source tree.
For those cases you can dynamically add steps during a build from other steps.

The :class:`Build` object provides 2 functions to do this:

``addStepsAfterCurrentStep(self, step_factories)``
    This adds the steps after the step that is currently executing.

``addStepsAfterLastStep(self, step_factories)``
    This adds the steps onto the end of the build.

Both functions only accept as an argument a list of steps to add to the build.

For example lets say you have a script checked in into your source tree called build.sh.
When this script is called with the argument ``--list-stages`` it outputs a newline separated list of stage names.
This can be used to generate at runtime a step for each stage in the build.
Each stage is then run in this example using ``./build.sh --run-stage <stage name>``.

::

    from buildbot.plugins import util, steps
    from buildbot.process import buildstep, logobserver
    from twisted.internet import defer

    class GenerateStagesCommand(buildstep.ShellMixin, steps.BuildStep):

        def __init__(self, **kwargs):
            kwargs = self.setupShellMixin(kwargs)
            steps.BuildStep.__init__(self, **kwargs)
            self.observer = logobserver.BufferLogObserver()
            self.addLogObserver('stdio', self.observer)

        def extract_stages(self, stdout):
            stages = []
            for line in stdout.split('\n'):
                stage = str(line.strip())
                if stage:
                    stages.append(stage)
            return stages

        @defer.inlineCallbacks
        def run(self):
            # run './build.sh --list-stages' to generate the list of stages
            cmd = yield self.makeRemoteShellCommand()
            yield self.runCommand(cmd)

            # if the command passes extract the list of stages
            result = cmd.results()
            if result == util.SUCCESS:
                # create a ShellCommand for each stage and add them to the build
                self.build.addStepsAfterCurrentStep([
                    steps.ShellCommand(name=stage, command=["./build.sh", "--run-stage", stage])
                    for stage in self.extract_stages(self.observer.getStdout())
                ])

            defer.returnValue(result)

    f = util.BuildFactory()
    f.addStep(steps.Git(repourl=repourl))
    f.addStep(GenerateStagesCommand(
        name="Generate build stages",
        command=["./build.sh", "--list-stages"],
        haltOnFailure=True))

Predefined Build Factories
--------------------------

Buildbot includes a few predefined build factories that perform common build sequences.
In practice, these are rarely used, as every site has slightly different requirements, but the source for these factories may provide examples for implementation of those requirements.

.. _GNUAutoconf:

.. index::
   GNUAutoconf
   Build Factory; GNUAutoconf

GNUAutoconf
~~~~~~~~~~~

.. py:class:: buildbot.process.factory.GNUAutoconf

`GNU Autoconf <http://www.gnu.org/software/autoconf/>`_ is a software portability tool, intended to make it possible to write programs in C (and other languages) which will run on a variety of UNIX-like systems.
Most GNU software is built using autoconf.
It is frequently used in combination with GNU automake.
These tools both encourage a build process which usually looks like this:

.. code-block:: bash

    % CONFIG_ENV=foo ./configure --with-flags
    % make all
    % make check
    # make install

(except of course the Buildbot always skips the ``make install`` part).

The Buildbot's :class:`buildbot.process.factory.GNUAutoconf` factory is designed to build projects which use GNU autoconf and/or automake.
The configuration environment variables, the configure flags, and command lines used for the compile and test are all configurable, in general the default values will be suitable.

Example::

    f = util.GNUAutoconf(source=source.SVN(repourl=URL, mode="copy"),
                         flags=["--disable-nls"])

Required Arguments:

``source``
    This argument must be a step specification tuple that provides a BuildStep to generate the source tree.

Optional Arguments:

``configure``
    The command used to configure the tree.
    Defaults to :command:`./configure`.
    Accepts either a string or a list of shell argv elements.

``configureEnv``
    The environment used for the initial configuration step.
    This accepts a dictionary which will be merged into the worker's normal environment.
    This is commonly used to provide things like ``CFLAGS="-O2 -g"`` (to turn off debug symbols during the compile).
    Defaults to an empty dictionary.

``configureFlags``
    A list of flags to be appended to the argument list of the configure command.
    This is commonly used to enable or disable specific features of the autoconf-controlled package, like ``["--without-x"]`` to disable windowing support.
    Defaults to an empty list.

``reconf``
    use autoreconf to generate the ./configure file, set to True to use a buildbot default autoreconf command, or define the command for the ShellCommand.

``compile``
    this is a shell command or list of argv values which is used to actually compile the tree.
    It defaults to ``make all``.
    If set to ``None``, the compile step is skipped.

``test``
    this is a shell command or list of argv values which is used to run the tree's self-tests.
    It defaults to ``make check``.
    If set to None, the test step is skipped.

``distcheck``
    this is a shell command or list of argv values which is used to run the packaging test.
    It defaults to ``make distcheck``.
    If set to None, the test step is skipped.

.. _BasicBuildFactory:

.. index::
   BasicBuildFactory
   Build Factory; BasicBuildFactory

BasicBuildFactory
~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.process.factory.BasicBuildFactory

This is a subclass of :class:`GNUAutoconf` which assumes the source is in CVS, and uses ``mode='full'`` and ``method='clobber'``  to always build from a clean working copy.

.. _BasicSVN:

.. index::
   BasicSVN
   Build Factory; BasicSVN

BasicSVN
~~~~~~~~

.. py:class:: buildbot.process.factory.BasicSVN

This class is similar to :class:`QuickBuildFactory`, but uses SVN instead of CVS.

.. _QuickBuildFactory:

.. index::
   QuickBuildFactory
   Build Factory; QuickBuildFactory

QuickBuildFactory
~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.process.factory.QuickBuildFactory

The :class:`QuickBuildFactory` class is a subclass of :class:`GNUAutoconf` which assumes the source is in CVS, and uses ``mode='incremental'`` to get incremental updates.

The difference between a `full build` and a `quick build` is that quick builds are generally done incrementally, starting with the tree where the previous build was performed.
That simply means that the source-checkout step should be given a ``mode='incremental'`` flag, to do the source update in-place.

In addition to that, this class sets the :attr:`useProgress` flag to ``False``.
Incremental builds will (or at least the ought to) compile as few files as necessary, so they will take an unpredictable amount of time to run.
Therefore it would be misleading to claim to predict how long the build will take.

This class is probably not of use to new projects.

.. _Factory-CPAN:

.. index::
   CPAN
   Build Factory; CPAN

CPAN
~~~~

.. py:class:: buildbot.process.factory.CPAN

Most Perl modules available from the `CPAN <http://www.cpan.org/>`_ archive use the ``MakeMaker`` module to provide configuration, build, and test services.
The standard build routine for these modules looks like:

.. code-block:: bash

    % perl Makefile.PL
    % make
    % make test
    # make install

(except again Buildbot skips the install step)

Buildbot provides a :class:`CPAN` factory to compile and test these projects.

Arguments:

``source``
    (required): A step specification tuple, like that used by :class:`GNUAutoconf`.

``perl``
    A string which specifies the :command:`perl` executable to use.
    Defaults to just :command:`perl`.

.. _Distutils:

.. index::
   Distutils,
   Build Factory; Distutils

Distutils
~~~~~~~~~

.. py:class:: buildbot.process.factory.Distutils

Most Python modules use the ``distutils`` package to provide configuration and build services.
The standard build process looks like:

.. code-block:: bash

    % python ./setup.py build
    % python ./setup.py install

Unfortunately, although Python provides a standard unit-test framework named ``unittest``, to the best of my knowledge ``distutils`` does not provide a standardized target to run such unit tests.
(Please let me know if I'm wrong, and I will update this factory.)

The :class:`Distutils` factory provides support for running the build part of this process.
It accepts the same ``source=`` parameter as the other build factories.

Arguments:

``source``
    (required): A step specification tuple, like that used by :class:`GNUAutoconf`.

``python``
    A string which specifies the :command:`python` executable to use.
    Defaults to just :command:`python`.

``test``
    Provides a shell command which runs unit tests.
    This accepts either a string or a list.
    The default value is ``None``, which disables the test step (since there is no common default command to run unit tests in distutils modules).

.. _Trial:

.. index::
   Trial
   Build Factory; Trial

Trial
~~~~~

.. py:class:: buildbot.process.factory.Trial

Twisted provides a unit test tool named :command:`trial` which provides a few improvements over Python's built-in :mod:`unittest` module.
Many Python projects which use Twisted for their networking or application services also use trial for their unit tests.
These modules are usually built and tested with something like the following:

.. code-block:: bash

    % python ./setup.py build
    % PYTHONPATH=build/lib.linux-i686-2.3 trial -v PROJECTNAME.test
    % python ./setup.py install

Unfortunately, the :file:`build/lib` directory into which the built/copied ``.py`` files are placed is actually architecture-dependent, and I do not yet know of a simple way to calculate its value.
For many projects it is sufficient to import their libraries `in place` from the tree's base directory (``PYTHONPATH=.``).

In addition, the :samp:`{PROJECTNAME}` value where the test files are located is project-dependent: it is usually just the project's top-level library directory, as common practice suggests the unit test files are put in the :mod:`test` sub-module.
This value cannot be guessed, the :class:`Trial` class must be told where to find the test files.

The :class:`Trial` class provides support for building and testing projects which use distutils and trial.
If the test module name is specified, trial will be invoked.
The library path used for testing can also be set.

One advantage of trial is that the Buildbot happens to know how to parse trial output, letting it identify which tests passed and which ones failed.
The Buildbot can then provide fine-grained reports about how many tests have failed, when individual tests fail when they had been passing previously, etc.

Another feature of trial is that you can give it a series of source ``.py`` files, and it will search them for special ``test-case-name`` tags that indicate which test cases provide coverage for that file.
Trial can then run just the appropriate tests.
This is useful for quick builds, where you want to only run the test cases that cover the changed functionality.

Arguments:

``testpath``
    Provides a directory to add to :envvar:`PYTHONPATH` when running the unit tests, if tests are being run.
    Defaults to ``.`` to include the project files in-place.
    The generated build library is frequently architecture-dependent, but may simply be :file:`build/lib` for pure-Python modules.

``python``
    which Python executable to use.
    This list will form the start of the `argv` array that will launch trial.
    If you use this, you should set ``trial`` to an explicit path (like :file:`/usr/bin/trial` or :file:`./bin/trial`).
    The parameter defaults to ``None``, which leaves it out entirely (running ``trial args`` instead of ``python ./bin/trial args``).
    Likely values are ``['python']``, ``['python2.2']``, or ``['python', '-Wall']``.

``trial``
    provides the name of the :command:`trial` command.
    It is occasionally useful to use an alternate executable, such as :command:`trial2.2` which might run the tests under an older version of Python.
    Defaults to :command:`trial`.

``trialMode``
    a list of arguments to pass to trial, specifically to set the reporting mode.
    This defaults to ``['--reporter=bwverbose']``, which only works for Twisted-2.1.0 and later.

``trialArgs``
    a list of arguments to pass to trial, available to turn on any extra flags you like.
    Defaults to ``[]``.

``tests``
    Provides a module name or names which contain the unit tests for this project.
    Accepts a string, typically :samp:`{PROJECTNAME}.test`, or a list of strings.
    Defaults to ``None``, indicating that no tests should be run.
    You must either set this or ``testChanges``.

``testChanges``
    if ``True``, ignore the ``tests`` parameter and instead ask the Build for all the files that make up the Changes going into this build.
    Pass these filenames to trial and ask it to look for test-case-name tags, running just the tests necessary to cover the changes.

``recurse``
    If ``True``, tells Trial (with the ``--recurse`` argument) to look in all subdirectories for additional test cases.

``reactor``
    which reactor to use, like 'gtk' or 'java'.
    If not provided, the Twisted's usual platform-dependent default is used.

``randomly``
    If ``True``, tells Trial (with the ``--random=0`` argument) to run the test cases in random order, which sometimes catches subtle inter-test dependency bugs.
    Defaults to ``False``.

The step can also take any of the :class:`ShellCommand` arguments, e.g., :attr:`haltOnFailure`.

Unless one of ``tests`` or ``testChanges`` are set, the step will generate an exception.
