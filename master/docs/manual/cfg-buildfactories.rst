.. -*- rst -*-
.. _Build-Factories:

Build Factories
---------------

Each Builder is equipped with a ``build factory``, which is
responsible for producing the actual :class:`Build` objects that perform
each build. This factory is created in the configuration file, and
attached to a Builder through the ``factory`` element of its
dictionary.

The standard :class:`BuildFactory` object creates :class:`Build` objects
by default. These Builds will each execute a collection of :class:`BuildStep`\s
in a fixed sequence. Each step can affect the results of the build,
but in general there is little intelligence to tie the different steps
together. 

The steps used by these builds are all subclasses of :class:`BuildStep`.
The standard ones provided with Buildbot are documented later,
:ref:`Build-Steps`. You can also write your own subclasses to use in
builds.

The basic behavior for a :class:`BuildStep` is to:

  * run for a while, then stop
  * possibly invoke some RemoteCommands on the attached build slave
  * possibly produce a set of log files
  * finish with a status described by one of four values defined in
    :mod:`buildbot.status.builder`: ``SUCCESS``, ``WARNINGS``, ``FAILURE``, ``SKIPPED``
  * provide a list of short strings to describe the step

.. _BuildFactory:
  
.. index::
   BuildFactory
   Build Factory; BuildFactory
  
BuildFactory
~~~~~~~~~~~~

.. py:class:: buildbot.process.factory.BuildFactory

A :class:`BuildFactory` defines the steps that every build will follow.  Think of it as
a glorified script.  For example, a build which consists of a CVS checkout
followed by a ``make build`` would be constructed as follows::

    from buildbot.steps import source, shell
    from buildbot.process import factory
    
    f = factory.BuildFactory()
    f.addStep(source.CVS(cvsroot=CVSROOT, cvsmodule="project", mode="update"))
    f.addStep(shell.Compile(command=["make", "build"]))

It is also possible to pass a list of steps into the
:class:`BuildFactory` when it is created. Using :meth:`addStep` is
usually simpler, but there are cases where is is more convenient to
create the list of steps ahead of time, perhaps using some Python
tricks to generate the steps. ::

    from buildbot.steps import source, shell
    from buildbot.process import factory

    all_steps = [
        source.CVS(cvsroot=CVSROOT, cvsmodule="project", mode="update"),
        shell.Compile(command=["make", "build"]),
    ]
    f = factory.BuildFactory(all_steps)

Finally, you can also add a sequence of steps all at once::

    f.addSteps(all_steps)

Attributes
++++++++++

:attr:`useProgress`
    (defaults to ``True``): if ``True``, the buildmaster keeps track of how long
    each step takes, so it can provide estimates of how long future builds
    will take. If builds are not expected to take a consistent amount of
    time (such as incremental builds in which a random set of files are
    recompiled or tested each time), this should be set to ``False`` to
    inhibit progress-tracking.

:attr:`workdir`
    (defaults to 'build'): workdir given to every build step created by
    this factory as default. The workdir can be overridden in a build step
    definition.
    If this attribute is set to a string, that string will be used
    for constructing the workdir (buildslave base + builder builddir +
    workdir). If this attributed is set to a Python callable, that
    callable will be called with SourceStamp as single parameter and
    is supposed to return a string which will be used as above.
    The latter is useful in scenarios with multiple repositories
    submitting changes to BuildBot. In this case you likely will want
    to have a dedicated workdir per repository, since otherwise a
    sourcing step with mode = "update" will fail as a workdir with
    a working copy of repository A can't be "updated" for changes
    from a repository B. Here is an example how you can achive
    workdir-per-repo::

        #
        # pre-repository working directory
        #
        def workdir(source_stamp):
            return hashlib.md5 (source_stamp.repository).hexdigest()[:8]
        
        build = factory.BuildFactory()
        build.workdir = workdir
        
        build.addStep(Git(mode="update"))
        # ...
        builders.append ({'name': 'mybuilder',
                          'slavename': 'myslave',
                          'builddir': 'mybuilder',
                          'factory': build})
        
        # You'll end up with workdirs like:
        #
        # Repo1 => <buildslave-base>/mybuilder/a78890ba
        # Repo2	=> <buildslave-base>/mybuilder/0823ba88
        # ...

    You could make the :func:`workdir()` function compute other paths, based on
    parts of the repo URL in the sourcestamp, or lookup in a lookup table
    based on repo URL. As long as there is a permanent 1:1 mapping between
    repos and workdir this will work.

Implementation Note
+++++++++++++++++++

The default :class:`BuildFactory`, provided in the
:mod:`buildbot.process.factory` module, contains an internal list of
`BuildStep specifications`: a list of ``(step_class, kwargs)``
tuples for each. These specification tuples are constructed when the
config file is read, by asking the instances passed to :meth:`addStep`
for their subclass and arguments.

To support config files from buildbot-0.7.5 and earlier,
:meth:`addStep` also accepts the ``f.addStep(shell.Compile,
command=["make","build"])`` form, although its use is discouraged
because then the ``Compile`` step doesn't get to validate or
complain about its arguments until build time. The modern
pass-by-instance approach allows this validation to occur while the
config file is being loaded, where the admin has a better chance of
noticing problems.

When asked to create a :class:`Build`, the :class:`BuildFactory` puts a copy of
the list of step specifications into the new :class:`Build` object. When the
:class:`Build` is actually started, these step specifications are used to
create the actual set of :class:`BuildStep`\s, which are then executed one at a
time. This serves to give each Build an independent copy of each step.

Each step can affect the build process in the following ways:

  * If the step's :attr:`haltOnFailure` attribute is ``True``, then a failure
    in the step (i.e. if it completes with a result of ``FAILURE``) will cause
    the whole build to be terminated immediately: no further steps will be
    executed, with the exception of steps with :attr:`alwaysRun` set to
    ``True``. :attr:`haltOnFailure` is useful for setup steps upon which the
    rest of the build depends: if the CVS checkout or :command:`./configure`
    process fails, there is no point in trying to compile or test the
    resulting tree.

  * If the step's :attr:`alwaysRun` attribute is ``True``, then it will always
    be run, regardless of if previous steps have failed. This is useful
    for cleanup steps that should always be run to return the build
    directory or build slave into a good state.

  * If the :attr:`flunkOnFailure` or :attr:`flunkOnWarnings` flag is set,
    then a result of ``FAILURE`` or ``WARNINGS`` will mark the build as a whole as
    ``FAILED``. However, the remaining steps will still be executed. This is
    appropriate for things like multiple testing steps: a failure in any
    one of them will indicate that the build has failed, however it is
    still useful to run them all to completion.

  * Similarly, if the :attr:`warnOnFailure` or :attr:`warnOnWarnings` flag
    is set, then a result of ``FAILURE`` or ``WARNINGS`` will mark the build as
    having ``WARNINGS``, and the remaining steps will still be executed. This
    may be appropriate for certain kinds of optional build or test steps.
    For example, a failure experienced while building documentation files
    should be made visible with a ``WARNINGS`` result but not be serious
    enough to warrant marking the whole build with a ``FAILURE``.

In addition, each :class:`Step` produces its own results, may create logfiles,
etc. However only the flags described above have any effect on the
build as a whole.

The pre-defined :class:`BuildStep`\s like :class:`CVS` and :class:`Compile` have
reasonably appropriate flags set on them already. For example, without
a source tree there is no point in continuing the build, so the
:class:`CVS` class has the :attr:`haltOnFailure` flag set to ``True``. Look
in :file:`buildbot/steps/*.py` to see how the other :class:`Step`\s are
marked.

Each :class:`Step` is created with an additional ``workdir`` argument that
indicates where its actions should take place. This is specified as a
subdirectory of the slave builder's base directory, with a default
value of :file:`build`. This is only implemented as a step argument (as
opposed to simply being a part of the base directory) because the
CVS/SVN steps need to perform their checkouts from the parent
directory.

.. _GNUAutoconf:

.. index::
   GNUAutoconf
   Build Factory; GNUAutoconf

GNUAutoconf
~~~~~~~~~~~

.. py:class:: buildbot.process.factory.GNUAutoconf

`GNU Autoconf <http://www.gnu.org/software/autoconf/>`_ is a
software portability tool, intended to make it possible to write
programs in C (and other languages) which will run on a variety of
UNIX-like systems. Most GNU software is built using autoconf. It is
frequently used in combination with GNU automake. These tools both
encourage a build process which usually looks like this:

.. code-block:: bash

    % CONFIG_ENV=foo ./configure --with-flags
    % make all
    % make check
    # make install

(except of course the Buildbot always skips the ``make install``
part).

The Buildbot's :class:`buildbot.process.factory.GNUAutoconf` factory is
designed to build projects which use GNU autoconf and/or automake. The
configuration environment variables, the configure flags, and command
lines used for the compile and test are all configurable, in general
the default values will be suitable.

Example::

    f = factory.GNUAutoconf(source=source.SVN(svnurl=URL, mode="copy"),
                            flags=["--disable-nls"])

Required Arguments:

``source``
    This argument must be a step specification tuple that provides a
    BuildStep to generate the source tree.

Optional Arguments:

``configure``
    The command used to configure the tree. Defaults to
    :command:`./configure`. Accepts either a string or a list of shell argv
    elements.

``configureEnv``
    The environment used for the initial configuration step. This accepts
    a dictionary which will be merged into the buildslave's normal
    environment. This is commonly used to provide things like
    ``CFLAGS="-O2 -g"`` (to turn off debug symbols during the compile).
    Defaults to an empty dictionary.

``configureFlags``
    A list of flags to be appended to the argument list of the configure
    command. This is commonly used to enable or disable specific features
    of the autoconf-controlled package, like ``["--without-x"]`` to
    disable windowing support. Defaults to an empty list.

``compile``
    this is a shell command or list of argv values which is used to
    actually compile the tree. It defaults to ``make all``. If set to
    ``None``, the compile step is skipped.

``test``
    this is a shell command or list of argv values which is used to run
    the tree's self-tests. It defaults to @code{make check}. If set to
    None, the test step is skipped.

.. _BasicBuildFactory:
    
.. index::
   BasicBuildFactory
   Build Factory; BasicBuildFactory
    
BasicBuildFactory
~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.process.factory.BasicBuildFactory

This is a subclass of :class:`GNUAutoconf` which assumes the source is in CVS,
and uses ``mode='clobber'``  to always build from a clean working copy.

.. _BasicSVN:

.. index::
   BasicSVN
   Build Factory; BasicSVN

BasicSVN
~~~~~~~~

.. py:class:: buildbot.process.factory.BasicSVN

This class is similar to :class:`BasicBuildFactory`, but uses SVN instead of CVS.

.. _QuickBuildFactory:

.. index::
   QuickBuildFactory
   Build Factory; QuickBuildFactory

QuickBuildFactory
~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.process.factory.QuickBuildFactory

The :class:`QuickBuildFactory` class is a subclass of :class:`GNUAutoconf` which
assumes the source is in CVS, and uses ``mode='update'`` to get incremental
updates.

The difference between a `full build` and a `quick build` is that
quick builds are generally done incrementally, starting with the tree
where the previous build was performed. That simply means that the
source-checkout step should be given a ``mode='update'`` flag, to
do the source update in-place.

In addition to that, this class sets the :attr:`useProgress` flag to ``False``.
Incremental builds will (or at least the ought to) compile as few files as
necessary, so they will take an unpredictable amount of time to run. Therefore
it would be misleading to claim to predict how long the build will take.

This class is probably not of use to new projects.

.. _Factory-CPAN:

.. index::
   CPAN
   Build Factory; CPAN

CPAN
~~~~

.. py:class:: buildbot.process.factory.CPAN

Most Perl modules available from the `CPAN <http://www.cpan.org/>`_
archive use the ``MakeMaker`` module to provide configuration,
build, and test services. The standard build routine for these modules
looks like:

.. code-block:: bash

    % perl Makefile.PL
    % make
    % make test
    # make install

(except again Buildbot skips the install step)

Buildbot provides a :class:`CPAN` factory to compile and test these
projects.

Arguments:

``source``
    (required): A step specification tuple, like that used by :class:`GNUAutoconf`.

``perl``
    A string which specifies the :command:`perl` executable to use. Defaults
    to just :command:`perl`.

.. _Distutils:

.. index::
   Distutils,
   Build Factory; Distutils
    
Distutils
~~~~~~~~~

.. py:class:: buildbot.process.factory.Distutils

Most Python modules use the ``distutils`` package to provide
configuration and build services. The standard build process looks
like:

.. code-block:: bash

    % python ./setup.py build
    % python ./setup.py install

Unfortunately, although Python provides a standard unit-test framework
named ``unittest``, to the best of my knowledge ``distutils``
does not provide a standardized target to run such unit tests. (Please
let me know if I'm wrong, and I will update this factory.)

The :class:`Distutils` factory provides support for running the build
part of this process. It accepts the same ``source=`` parameter as
the other build factories.

Arguments:

``source``
    (required): A step specification tuple, like that used by :class:`GNUAutoconf`.

``python``
    A string which specifies the :command:`python` executable to use. Defaults
    to just :command:`python`.

``test``
    Provides a shell command which runs unit tests. This accepts either a
    string or a list. The default value is ``None``, which disables the test
    step (since there is no common default command to run unit tests in
    distutils modules).

.. _Trial:

.. index::
   Trial
   Build Factory; Trial

Trial
~~~~~

.. py:class:: buildbot.process.factory.Trial

Twisted provides a unit test tool named :command:`trial` which provides a
few improvements over Python's built-in :mod:`unittest` module. Many
python projects which use Twisted for their networking or application
services also use trial for their unit tests. These modules are
usually built and tested with something like the following:

.. code-block:: bash

    % python ./setup.py build
    % PYTHONPATH=build/lib.linux-i686-2.3 trial -v PROJECTNAME.test
    % python ./setup.py install

Unfortunately, the :file:`build/lib` directory into which the
built/copied ``.py`` files are placed is actually architecture-dependent,
and I do not yet know of a simple way to calculate its value. For many
projects it is sufficient to import their libraries `in place` from
the tree's base directory (``PYTHONPATH=.``).

In addition, the :samp:`{PROJECTNAME}` value where the test files are
located is project-dependent: it is usually just the project's
top-level library directory, as common practice suggests the unit test
files are put in the :mod:`test` sub-module. This value cannot be
guessed, the :class:`Trial` class must be told where to find the test
files.

The :class:`Trial` class provides support for building and testing
projects which use distutils and trial. If the test module name is
specified, trial will be invoked. The library path used for testing
can also be set.

One advantage of trial is that the Buildbot happens to know how to
parse trial output, letting it identify which tests passed and which
ones failed. The Buildbot can then provide fine-grained reports about
how many tests have failed, when individual tests fail when they had
been passing previously, etc.

Another feature of trial is that you can give it a series of source
``.py`` files, and it will search them for special ``test-case-name``
tags that indicate which test cases provide coverage for that file.
Trial can then run just the appropriate tests. This is useful for
quick builds, where you want to only run the test cases that cover the
changed functionality.

Arguments:

``testpath``
    Provides a directory to add to :envvar:`PYTHONPATH` when running the unit
    tests, if tests are being run. Defaults to ``.`` to include the
    project files in-place. The generated build library is frequently
    architecture-dependent, but may simply be :file:`build/lib` for
    pure-python modules.

``python``
    which python executable to use. This list will form the start of
    the `argv` array that will launch trial. If you use this,
    you should set ``trial`` to an explicit path (like
    :file:`/usr/bin/trial` or :file:`./bin/trial`). The parameter defaults
    to ``None``, which
    leaves it out entirely (running ``trial args`` instead of
    ``python ./bin/trial args``). Likely values are ``['python']``,
    ``['python2.2']``, or ``['python', '-Wall']``.

``trial``
    provides the name of the :command:`trial` command. It is occasionally
    useful to use an alternate executable, such as :command:`trial2.2` which
    might run the tests under an older version of Python. Defaults to
    :command:`trial`.

``trialMode``
    a list of arguments to pass to trial, specifically to set the reporting mode.
    This defaults to ``['--reporter=bwverbose']``, which only works for
    Twisted-2.1.0 and later.

``trialArgs``
    a list of arguments to pass to trial, available to turn on any extra flags you
    like. Defaults to ``[]``.

``tests``
    Provides a module name or names which contain the unit tests for this
    project. Accepts a string, typically :samp:`{PROJECTNAME}.test`, or a
    list of strings. Defaults to ``None``, indicating that no tests should be
    run. You must either set this or ``testChanges``.

``testChanges``
    if ``True``, ignore the ``tests`` parameter and instead ask the Build for all
    the files that make up the Changes going into this build. Pass these filenames
    to trial and ask it to look for test-case-name tags, running just the tests
    necessary to cover the changes.

``recurse``
    If ``True``, tells Trial (with the ``--recurse`` argument) to look in all
    subdirectories for additional test cases.

``reactor``
    which reactor to use, like 'gtk' or 'java'. If not provided, the Twisted's
    usual platform-dependent default is used.

``randomly``
    If ``True``, tells Trial (with the ``--random=0`` argument) to
    run the test cases in random order, which sometimes catches subtle
    inter-test dependency bugs. Defaults to ``False``.

The step can also take any of the :class:`ShellCommand` arguments, e.g.,
:attr:`haltOnFailure`.

Unless one of ``tests`` or ``testChanges`` are set, the step will
generate an exception.

