.. _Build-Steps:

Build Steps
===========

:class:`BuildStep`\s are usually specified in the buildmaster's configuration file, in a list that goes into the :class:`BuildFactory`.
The :class:`BuildStep` instances in this list are used as templates to construct new independent copies for each build (so that state can be kept on the :class:`BuildStep` in one build without affecting a later build).
Each :class:`BuildFactory` can be created with a list of steps, or the factory can be created empty and then steps added to it using the :meth:`addStep` method::

    from buildbot.plugins import util, steps

    f = util.BuildFactory()
    f.addSteps([
        steps.SVN(repourl="http://svn.example.org/Trunk/"),
        steps.ShellCommand(command=["make", "all"]),
        steps.ShellCommand(command=["make", "test"])
    ])

The basic behavior for a :class:`BuildStep` is to:

* run for a while, then stop
* possibly invoke some RemoteCommands on the attached worker
* possibly produce a set of log files
* finish with a status described by one of four values defined in :mod:`buildbot.status.builder`: ``SUCCESS``, ``WARNINGS``, ``FAILURE``, ``SKIPPED``
* provide a list of short strings to describe the step

The rest of this section describes all the standard :class:`BuildStep` objects available for use in a :class:`Build`, and the parameters which can be used to control each.
A full list of build steps is available in the :bb:index:`step`.

.. contents::
    :depth: 2
    :local:

.. index:: Buildstep Parameter

.. _Buildstep-Common-Parameters:

Common Parameters
-----------------

All :class:`BuildStep`\s accept some common parameters.
Some of these control how their individual status affects the overall build.
Others are used to specify which `Locks` (see :ref:`Interlocks`) should be acquired before allowing the step to run.

Arguments common to all :class:`BuildStep` subclasses:

``name``
    the name used to describe the step on the status display.
    It is also used to give a name to any :class:`LogFile`\s created by this step.

.. index:: Buildstep Parameter; haltOnFailure

``haltOnFailure``
    if ``True``, a ``FAILURE`` of this build step will cause the build to halt immediately.
    Steps with ``alwaysRun=True`` are still run.
    Generally speaking, ``haltOnFailure`` implies ``flunkOnFailure`` (the default for most :class:`BuildStep`\s).
    In some cases, particularly series of tests, it makes sense to ``haltOnFailure`` if something fails early on but not ``flunkOnFailure``.
    This can be achieved with ``haltOnFailure=True``, ``flunkOnFailure=False``.

.. index:: Buildstep Parameter; flunkOnWarnings

``flunkOnWarnings``
    when ``True``, a ``WARNINGS`` or ``FAILURE`` of this build step will mark the overall build as ``FAILURE``.
    The remaining steps will still be executed.

.. index:: Buildstep Parameter; flunkOnFailure

``flunkOnFailure``
    when ``True``, a ``FAILURE`` of this build step will mark the overall build as a ``FAILURE``.
    The remaining steps will still be executed.

.. index:: Buildstep Parameter; warnOnWarnings

``warnOnWarnings``
    when ``True``, a ``WARNINGS`` or ``FAILURE`` of this build step will mark the overall build as having ``WARNINGS``.
    The remaining steps will still be executed.

.. index:: Buildstep Parameter; warnOnFailure

``warnOnFailure``
    when ``True``, a ``FAILURE`` of this build step will mark the overall build as having ``WARNINGS``.
    The remaining steps will still be executed.

.. index:: Buildstep Parameter; alwaysRun

``alwaysRun``
    if ``True``, this build step will always be run, even if a previous buildstep with ``haltOnFailure=True`` has failed.

.. index:: Buildstep Parameter; description

``description``
    This will be used to describe the command (on the Waterfall display) while the command is still running.
    It should be a single imperfect-tense verb, like `compiling` or `testing`.
    The preferred form is a single, short string, but for historical reasons a list of strings is also acceptable.

.. index:: Buildstep Parameter; descriptionDone

``descriptionDone``
    This will be used to describe the command once it has finished.
    A simple noun like `compile` or `tests` should be used.
    Like ``description``, this may either be a string or a list of short strings.

    If neither ``description`` nor ``descriptionDone`` are set, the actual command arguments will be used to construct the description.
    This may be a bit too wide to fit comfortably on the Waterfall display.

    All subclasses of :py:class:`BuildStep` will contain the description attributes.
    Consequently, you could add a :bb:step:`ShellCommand` step like so::

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(command=["make", "test"],
                                     description="testing",
                                     descriptionDone="tests"))

.. index:: Buildstep Parameter; descriptionSuffix

``descriptionSuffix``
    This is an optional suffix appended to the end of the description (ie, after ``description`` and ``descriptionDone``).
    This can be used to distinguish between build steps that would display the same descriptions in the waterfall.
    This parameter may be a string, a list of short strings or ``None``.

    For example, a builder might use the :bb:step:`Compile` step to build two different codebases.
    The ``descriptionSuffix`` could be set to `projectFoo` and `projectBar`, respectively for each step, which will result in the full descriptions `compiling projectFoo` and `compiling projectBar` to be shown in the waterfall.

.. index:: Buildstep Parameter; doStepIf

``doStepIf``
    A step can be configured to only run under certain conditions.
    To do this, set the step's ``doStepIf`` to a boolean value, or to a function that returns a boolean value or Deferred.
    If the value or function result is false, then the step will return ``SKIPPED`` without doing anything.
    Otherwise, the step will be executed normally.
    If you set ``doStepIf`` to a function, that function should accept one parameter, which will be the :class:`Step` object itself.

.. index:: Buildstep Parameter; hideStepIf

``hideStepIf``
    A step can be optionally hidden from the waterfall and build details web pages.
    To do this, set the step's ``hideStepIf`` to a boolean value, or to a function that takes two parameters -- the results and the :class:`BuildStep` -- and returns a boolean value.
    Steps are always shown while they execute, however after the step as finished, this parameter is evaluated (if a function) and if the value is True, the step is hidden.
    For example, in order to hide the step if the step has been skipped::

        factory.addStep(Foo(..., hideStepIf=lambda results, s: results==SKIPPED))

.. index:: Buildstep Parameter; locks

``locks``
    a list of ``Locks`` (instances of :class:`buildbot.locks.WorkerLock` or :class:`buildbot.locks.MasterLock`) that should be acquired before starting this :py:class:`BuildStep`.
    Alternatively this could be a renderable that returns this list during build execution.
    This lets you defer picking the locks to acquire until the build step is about to start running.
    The ``Locks`` will be released when the step is complete.
    Note that this is a list of actual :class:`Lock` instances, not names.
    Also note that all Locks must have unique names.
    See :ref:`Interlocks`.

.. index:: Buildstep Parameter; logEncoding

``logEncoding``
    The character encoding to use to decode logs produced during the execution of this step.
    This overrides the default :bb:cfg:`logEncoding`; see :ref:`Log-Encodings`.

.. _Source-Checkout:

Source Checkout
---------------

.. py:module:: buildbot.steps.source

.. caution::

    Support for the old worker-side source checkout steps was removed in Buildbot-0.9.0.

    The old source steps used to be imported like this::

        from buildbot.steps.source.oldsource import Git

        ... Git ...

    or::

        from buildbot.steps.source import Git

    while new source steps are in separate Python modules for each version-control system and, using the plugin infrastructure are available as::

        from buildbot.plugins import steps

        ... steps.Git ...

Common Parameters
+++++++++++++++++

All source checkout steps accept some common parameters to control how they get the sources and where they should be placed.
The remaining per-VC-system parameters are mostly to specify where exactly the sources are coming from.

``mode``
``method``

    These two parameters specify the means by which the source is checked out.
    ``mode`` specifies the type of checkout and ``method`` tells about the way to implement it.

    ::

        from buildbot.plugins import steps

        factory = BuildFactory()
        factory.addStep(steps.Mercurial(repourl='path/to/repo', mode='full',
                                        method='fresh'))

    The ``mode`` parameter a string describing the kind of VC operation that is desired, defaulting to ``incremental``.
    The options are

    ``incremental``
        Update the source to the desired revision, but do not remove any other files generated by previous builds.
        This allows compilers to take advantage of object files from previous builds.
        This mode is exactly same as the old ``update`` mode.

    ``full``
        Update the source, but delete remnants of previous builds.
        Build steps that follow will need to regenerate all object files.

    Methods are specific to the version-control system in question, as they may take advantage of special behaviors in that version-control system that can make checkouts more efficient or reliable.

``workdir``
    like all Steps, this indicates the directory where the build will take place.
    Source Steps are special in that they perform some operations outside of the workdir (like creating the workdir itself).

``alwaysUseLatest``
    if True, bypass the usual behavior of checking out the revision in the source stamp, and always update to the latest revision in the repository instead.

``retry``
    If set, this specifies a tuple of ``(delay, repeats)`` which means that when a full VC checkout fails, it should be retried up to ``repeats`` times, waiting ``delay`` seconds between attempts.
    If you don't provide this, it defaults to ``None``, which means VC operations should not be retried.
    This is provided to make life easier for workers which are stuck behind poor network connections.

``repository``
    The name of this parameter might vary depending on the Source step you are running.
    The concept explained here is common to all steps and applies to ``repourl`` as well as for ``baseURL`` (when applicable).

    A common idiom is to pass ``Property('repository', 'url://default/repo/path')`` as repository.
    This grabs the repository from the source stamp of the build.
    This can be a security issue, if you allow force builds from the web, or have the :class:`WebStatus` change hooks enabled; as the worker will download code from an arbitrary repository.

``codebase``
    This specifies which codebase the source step should use to select the right source stamp.
    The default codebase value is ``''``.
    The codebase must correspond to a codebase assigned by the :bb:cfg:`codebaseGenerator`.
    If there is no codebaseGenerator defined in the master then codebase doesn't need to be set, the default value will then match all changes.

``timeout``
    Specifies the timeout for worker-side operations, in seconds.
    If your repositories are particularly large, then you may need to increase this  value from its default of 1200 (20 minutes).

``logEnviron``
    If this option is true (the default), then the step's logfile will describe the environment variables on the worker.
    In situations where the environment is not relevant and is long, it may be easier to set ``logEnviron=False``.

``env``
    a dictionary of environment strings which will be added to the child command's environment.
    The usual property interpolations can be used in environment variable names and values - see :ref:`Properties`.

.. bb:step:: Mercurial

.. _Step-Mercurial:

Mercurial
+++++++++

.. py:class:: buildbot.steps.source.mercurial.Mercurial

The :bb:step:`Mercurial` build step performs a `Mercurial <http://selenic.com/mercurial>`_ (aka ``hg``) checkout or update.

Branches are available in two modes: ``dirname``, where the name of the branch is a suffix of the name of the repository, or ``inrepo``, which uses Hg's named-branches support.
Make sure this setting matches your changehook, if you have that installed.

::

    from buildbot.plugins import steps

    factory.addStep(steps.Mercurial(repourl='path/to/repo', mode='full',
                                    method='fresh', branchType='inrepo'))

The Mercurial step takes the following arguments:

``repourl``
   where the Mercurial source repository is available.

``defaultBranch``
   this specifies the name of the branch to use when a Build does not provide one of its own.
   This will be appended to ``repourl`` to create the string that will be passed to the ``hg clone`` command.

``branchType``
   either 'dirname' (default) or 'inrepo' depending on whether the branch name should be appended to the ``repourl`` or the branch is a Mercurial named branch and can be found within the ``repourl``.

``clobberOnBranchChange``
   boolean, defaults to ``True``.
   If set and using inrepos branches, clobber the tree at each branch change.
   Otherwise, just update to the branch.

``mode``
``method``

   Mercurial's incremental mode does not require a method.
   The full mode has three methods defined:


   ``clobber``
      It removes the build directory entirely then makes full clone from repo.
      This can be slow as it need to clone whole repository

   ``fresh``
      This remove all other files except those tracked by VCS.
      First it does :command:`hg purge --all` then pull/update

   ``clean``
      All the files which are tracked by Mercurial and listed ignore files are not deleted.
      Remaining all other files will be deleted before pull/update.
      This is equivalent to :command:`hg purge` then pull/update.

.. bb:step:: Git

.. _Step-Git:

Git
+++

.. py:class:: buildbot.steps.source.git.Git

The :bb:step:`Git` build step clones or updates a `Git <http://git.or.cz/>`_ repository and checks out the specified branch or revision.


.. note::

    The Buildbot supports Git version 1.2.0 and later: earlier versions (such as the one shipped in Ubuntu 'Dapper') do not support the :command:`git init` command that the Buildbot uses.

::

    from buildbot.plugins import steps

    factory.addStep(steps.Git(repourl='git://path/to/repo', mode='full',
                              method='clobber', submodules=True))

The Git step takes the following arguments:

``repourl``
   (required): the URL of the upstream Git repository.

``branch``
   (optional): this specifies the name of the branch to use when a Build does not provide one of its own.
   If this this parameter is not specified, and the Build does not provide a branch, the default branch of the remote repository will be used.

``submodules``
   (optional): when initializing/updating a Git repository, this tells Buildbot whether to handle Git submodules.
   Default: ``False``.

``shallow``
   (optional): instructs git to attempt shallow clones (``--depth 1``).
   This option can be used only in full builds with clobber method.

``reference``
   (optional): use the specified string as a path to a reference repository on the local machine.
   Git will try to grab objects from this path first instead of the main repository, if they exist.

``origin``
   (optional): By default, any clone will use the name "origin" as the remote repository (eg, "origin/master").
   This renderable option allows that to be configured to an alternate name.

``progress``
   (optional): passes the (``--progress``) flag to (:command:`git fetch`).
   This solves issues of long fetches being killed due to lack of output, but requires Git 1.7.2 or later.

``retryFetch``
   (optional): defaults to ``False``.
   If true, if the ``git fetch`` fails then buildbot retries to fetch again instead of failing the entire source checkout.

``clobberOnFailure``
   (optional): defaults to ``False``.
   If a fetch or full clone fails we can checkout source removing everything.
   This way new repository will be cloned.
   If retry fails it fails the source checkout step.

``mode``

  (optional): defaults to ``'incremental'``.
  Specifies whether to clean the build tree or not.

    ``incremental``
      The source is update, but any built files are left untouched.

    ``full``
      The build tree is clean of any built files.
      The exact method for doing this is controlled by the ``method`` argument.


``method``

   (optional): defaults to ``fresh`` when mode is ``full``.
   Git's incremental mode does not require a method.
   The full mode has four methods defined:


   ``clobber``
      It removes the build directory entirely then makes full clone from repo.
      This can be slow as it need to clone whole repository.
      To make faster clones enable ``shallow`` option.
      If shallow options is enabled and build request have unknown revision value, then this step fails.

   ``fresh``
      This remove all other files except those tracked by Git.
      First it does :command:`git clean -d -f -f -x` then fetch/checkout to a specified revision(if any).
      This option is equal to update mode with ``ignore_ignores=True`` in old steps.

   ``clean``
      All the files which are tracked by Git and listed ignore files are not deleted.
      Remaining all other files will be deleted before fetch/checkout.
      This is equivalent to :command:`git clean -d -f -f` then fetch.
      This is equivalent to ``ignore_ignores=False`` in old steps.

   ``copy``
      This first checkout source into source directory then copy the ``source`` directory to ``build`` directory then performs the build operation in the copied directory.
      This way we make fresh builds with very less bandwidth to download source.
      The behavior of source checkout follows exactly same as incremental.
      It performs all the incremental checkout behavior in ``source`` directory.

``getDescription``

   (optional) After checkout, invoke a `git describe` on the revision and save the result in a property; the property's name is either ``commit-description`` or ``commit-description-foo``, depending on whether the ``codebase`` argument was also provided.
   The argument should either be a ``bool`` or ``dict``, and will change how `git describe` is called:

   * ``getDescription=False``: disables this feature explicitly
   * ``getDescription=True`` or empty ``dict()``: Run `git describe` with no args
   * ``getDescription={...}``: a dict with keys named the same as the Git option.
     Each key's value can be ``False`` or ``None`` to explicitly skip that argument.

     For the following keys, a value of ``True`` appends the same-named Git argument:

      * ``all`` : `--all`
      * ``always``: `--always`
      * ``contains``: `--contains`
      * ``debug``: `--debug`
      * ``long``: `--long``
      * ``exact-match``: `--exact-match`
      * ``tags``: `--tags`
      * ``dirty``: `--dirty`

     For the following keys, an integer or string value (depending on what Git expects) will set the argument's parameter appropriately.
     Examples show the key-value pair:

      * ``match=foo``: `--match foo`
      * ``abbrev=7``: `--abbrev=7`
      * ``candidates=7``: `--candidates=7`
      * ``dirty=foo``: `--dirty=foo`

``config``

   (optional) A dict of git configuration settings to pass to the remote git commands.

.. bb:step:: SVN

.. _Step-SVN:

SVN
+++

.. py:class:: buildbot.steps.source.svn.SVN

The :bb:step:`SVN` build step performs a `Subversion <http://subversion.tigris.org>`_ checkout or update.
There are two basic ways of setting up the checkout step, depending upon whether you are using multiple branches or not.

The :bb:step:`SVN` step should be created with the ``repourl`` argument:

``repourl``
   (required): this specifies the ``URL`` argument that will be given to the :command:`svn checkout` command.
   It dictates both where the repository is located and which sub-tree should be extracted.
   One way to specify the branch is to use ``Interpolate``.
   For example, if you wanted to check out the trunk repository, you could use ``repourl=Interpolate("http://svn.example.com/repos/%(src::branch)s")``.
   Alternatively, if you are using a remote Subversion repository which is accessible through HTTP at a URL of ``http://svn.example.com/repos``, and you wanted to check out the ``trunk/calc`` sub-tree, you would directly use ``repourl="http://svn.example.com/repos/trunk/calc"`` as an argument to your :bb:step:`SVN` step.

If you are building from multiple branches, then you should create the :bb:step:`SVN` step with the ``repourl`` and provide branch information with :ref:`Interpolate`::

    from buildbot.plugins import steps, util

    factory.addStep(steps.SVN(mode='incremental',
                    repourl=util.Interpolate('svn://svn.example.org/svn/%(src::branch)s/myproject')))

Alternatively, the ``repourl`` argument can be used to create the :bb:step:`SVN` step without :ref:`Interpolate`::

    from buildbot.plugins import steps

    factory.addStep(steps.SVN(mode='full',
                    repourl='svn://svn.example.org/svn/myproject/trunk'))

``username``
   (optional): if specified, this will be passed to the ``svn`` binary with a ``--username`` option.

``password``
   (optional): if specified, this will be passed to the ``svn`` binary with a ``--password`` option.

``extra_args``
   (optional): if specified, an array of strings that will be passed as extra arguments to the ``svn`` binary.

``keep_on_purge``
   (optional): specific files or directories to keep between purges, like some build outputs that can be reused between builds.

``depth``
   (optional): Specify depth argument to achieve sparse checkout.
   Only available if worker has Subversion 1.5 or higher.

   If set to ``empty`` updates will not pull in any files or subdirectories not already present.
   If set to ``files``, updates will pull in any files not already present, but not directories.
   If set to ``immediates``, updates will pull in any files or subdirectories not already present, the new subdirectories will have depth: empty.
   If set to ``infinity``, updates will pull in any files or subdirectories not already present; the new subdirectories will have depth-infinity.
   Infinity is equivalent to SVN default update behavior, without specifying any depth argument.

``preferLastChangedRev``
   (optional): By default, the ``got_revision`` property is set to the repository's global revision ("Revision" in the `svn info` output).
   Set this parameter to ``True`` to have it set to the "Last Changed Rev" instead.

``mode``
``method``

   SVN's incremental mode does not require a method.
   The full mode has five methods defined:

   ``clobber``
      It removes the working directory for each build then makes full checkout.

   ``fresh``
      This always always purges local changes before updating.
      This deletes unversioned files and reverts everything that would appear in a :command:`svn status --no-ignore`.
      This is equivalent to the old update mode with ``always_purge``.

   ``clean``
      This is same as fresh except that it deletes all unversioned files generated by :command:`svn status`.

   ``copy``
      This first checkout source into source directory then copy the ``source`` directory to ``build`` directory then performs the build operation in the copied directory.
      This way we make fresh builds with very less bandwidth to download source.
      The behavior of source checkout follows exactly same as incremental.
      It performs all the incremental checkout behavior in ``source`` directory.

   ``export``
      Similar to ``method='copy'``, except using ``svn export`` to create build directory so that there are no ``.svn`` directories in the build directory.

If you are using branches, you must also make sure your ``ChangeSource`` will report the correct branch names.

.. bb:step:: CVS

.. _Step-CVS:

CVS
+++

.. py:class:: buildbot.steps.source.cvs.CVS

The :bb:step:`CVS` build step performs a `CVS <http://www.nongnu.org/cvs/>`_ checkout or update.

::

    from buildbot.plugins import steps

    factory.addStep(steps.CVS(mode='incremental',
                    cvsroot=':pserver:me@cvs.example.net:/cvsroot/myproj',
                    cvsmodule='buildbot'))

This step takes the following arguments:

``cvsroot``
    (required): specify the CVSROOT value, which points to a CVS repository, probably on a remote machine.
    For example, if Buildbot was hosted in CVS then the CVSROOT value you would use to get a copy of the Buildbot source code might be ``:pserver:anonymous@cvs.example.net:/cvsroot/buildbot``.

``cvsmodule``
    (required): specify the cvs ``module``, which is generally a subdirectory of the :file:`CVSROOT`.
    The cvsmodule for the Buildbot source code is ``buildbot``.

``branch``
    a string which will be used in a ``-r`` argument.
    This is most useful for specifying a branch to work on.
    Defaults to ``HEAD``.

``global_options``
    a list of flags to be put before the argument ``checkout`` in the CVS command.

``extra_options``
    a list of flags to be put after the ``checkout`` in the CVS command.

``mode``
``method``

    No method is needed for incremental mode.
    For full mode, ``method`` can take the values shown below.
    If no value is given, it defaults to ``fresh``.

    ``clobber``
        This specifies to remove the ``workdir`` and make a full checkout.

    ``fresh``
        This method first runs ``cvsdisard`` in the build directory, then updates it.
        This requires ``cvsdiscard`` which is a part of the cvsutil package.

    ``clean``
        This method is the same as ``method='fresh'``, but it runs ``cvsdiscard --ignore`` instead of ``cvsdiscard``.

    ``copy``
        This maintains a ``source`` directory for source, which it updates copies to the build directory.
        This allows Buildbot to start with a fresh directory, without downloading the entire repository on every build.

``login``
    Password to use while performing login to the remote CVS server.
    Default is ``None`` meaning that no login needs to be peformed.

.. bb:step:: Bzr

.. _Step-Bzr:

Bzr
+++

.. py:class:: buildbot.steps.source.bzr.Bzr

`bzr <http://bazaar.canonical.com/en/>`_ is a descendant of Arch/Baz, and is frequently referred to as simply `Bazaar`.
The repository-vs-workspace model is similar to Darcs, but it uses a strictly linear sequence of revisions (one history per branch) like Arch.
Branches are put in subdirectories.
This makes it look very much like Mercurial.

::

    from buildbot.plugins import steps

    factory.addStep(steps.Bzr(mode='incremental',
                              repourl='lp:~knielsen/maria/tmp-buildbot-test'))

The step takes the following arguments:

``repourl``
    (required unless ``baseURL`` is provided): the URL at which the Bzr source repository is available.

``baseURL``
    (required unless ``repourl`` is provided): the base repository URL, to which a branch name will be appended.
    It should probably end in a slash.

``defaultBranch``
    (allowed if and only if ``baseURL`` is provided): this specifies the name of the branch to use when a Build does not provide one of its own.
    This will be appended to ``baseURL`` to create the string that will be passed to the ``bzr checkout`` command.

``mode``
``method``

    No method is needed for incremental mode.
    For full mode, ``method`` can take the values shown below.
    If no value is given, it defaults to ``fresh``.

    ``clobber``
        This specifies to remove the ``workdir`` and make a full checkout.

    ``fresh``
        This method first runs ``bzr clean-tree`` to remove all the unversioned files then ``update`` the repo.
        This remove all unversioned files including those in .bzrignore.

    ``clean``
        This is same as fresh except that it doesn't remove the files mentioned in :file:`.bzrginore` i.e, by running ``bzr clean-tree --ignore``.

    ``copy``
        A local bzr repository is maintained and the repo is copied to ``build`` directory for each build.
        Before each build the local bzr repo is updated then copied to ``build`` for next steps.


.. bb:step:: P4

P4
++

.. py:class:: buildbot.steps.source.p4.P4

The :bb:step:`P4` build step creates a `Perforce <http://www.perforce.com/>`_ client specification and performs an update.

::

    from buildbot.plugins import steps, util

    factory.addStep(steps.P4(p4port=p4port,
                             p4client=util.WithProperties('%(P4USER)s-%(workername)s-%(buildername)s'),
                             p4user=p4user,
                             p4base='//depot',
                             p4viewspec=p4viewspec,
                             mode='incremental'))

You can specify the client spec in two different ways.
You can use the ``p4base``, ``p4branch``, and (optionally) ``p4extra_views`` to build up the viewspec, or you can utilize the ``p4viewspec`` to specify the whole viewspec as a set of tuples.

Using ``p4viewspec`` will allow you to add lines such as:

.. code-block:: none

    //depot/branch/mybranch/...             //<p4client>/...
    -//depot/branch/mybranch/notthisdir/... //<p4client>/notthisdir/...


If you specify ``p4viewspec`` and any of ``p4base``, ``p4branch``, and/or ``p4extra_views`` you will receive a configuration error exception.

``p4base``
    A view into the Perforce depot without branch name or trailing ``/...``.
    Typically ``//depot/proj``.

``p4branch``
    (optional): A single string, which is appended to the p4base as follows ``<p4base>/<p4branch>/...`` to form the first line in the viewspec

``p4extra_views``
    (optional): a list of ``(depotpath, clientpath)`` tuples containing extra views to be mapped into the client specification.
    Both will have ``/...`` appended automatically.
    The client name and source directory will be prepended to the client path.

``p4viewspec``
    This will override any p4branch, p4base, and/or p4extra_views specified.
    The viewspec will be an array of tuples as follows::

        [('//depot/main/','')]

    It yields a viewspec with just:

    .. code-block:: none

        //depot/main/... //<p4client>/...

``p4viewspec_suffix``
    (optional): The ``p4viewspec`` lets you customize the client spec for a builder but, as the previous example shows, it automatically adds ``...`` at the end of each line.
    If you need to also specify file-level remappings, you can set the ``p4viewspec_suffix`` to ``None`` so that nothing is added to your viewspec::

        [('//depot/main/...', '...'),
         ('-//depot/main/config.xml', 'config.xml'),
         ('//depot/main/config.vancouver.xml', 'config.xml')]

    It yields a viewspec with:

    .. code-block:: none

        //depot/main/...                  //<p4client>/...
        -//depot/main/config.xml          //<p4client/main/config.xml
        //depot/main/config.vancouver.xml //<p4client>/main/config.xml

    Note how, with ``p4viewspec_suffix`` set to ``None``, you need to manually add ``...`` where you need it.

``p4client_spec_options``
    (optional): By default, clients are created with the ``allwrite rmdir`` options.
    This string lets you change that.

``p4port``
    (optional): the :samp:`{host}:{port}` string describing how to get to the P4 Depot (repository), used as the option `-p` argument for all p4 commands.

``p4user``
    (optional): the Perforce user, used as the option `-u` argument to all p4 commands.

``p4passwd``
    (optional): the Perforce password, used as the option `-p` argument to all p4 commands.

``p4client``
    (optional): The name of the client to use.
    In ``mode='full'`` and ``mode='incremental'``, it's particularly important that a unique name is used for each checkout directory to avoid incorrect synchronization.
    For this reason, Python percent substitution will be performed on this value to replace ``%(prop:workername)s`` with the worker name and ``%(prop:buildername)s`` with the builder name.
    The default is ``buildbot_%(prop:workername)s_%(prop:buildername)s``.

``p4line_end``
    (optional): The type of line ending handling P4 should use.
    This is added directly to the client spec's ``LineEnd`` property.
    The default is ``local``.

``p4extra_args``
    (optional): Extra arguments to be added to the P4 command-line for the ``sync`` command.
    So for instance if you want to sync only to populate a Perforce proxy (without actually syncing files to disk), you can do::

        P4(p4extra_args=['-Zproxyload'], ...)

``use_tickets``
    Set to ``True`` to use ticket-based authentication, instead of passwords (but you still need to specify ``p4passwd``).

.. index:: double: Gerrit integration; Repo Build Step

.. bb:step:: Repo

Repo
++++

.. py:class:: buildbot.steps.source.repo.Repo

The :bb:step:`Repo` build step performs a `Repo <http://lwn.net/Articles/304488/>`_ init and sync.

The Repo step takes the following arguments:

``manifestURL``
    (required): the URL at which the Repo's manifests source repository is available.

``manifestBranch``
    (optional, defaults to ``master``): the manifest repository branch on which repo will take its manifest.
    Corresponds to the ``-b`` argument to the :command:`repo init` command.

``manifestFile``
    (optional, defaults to ``default.xml``): the manifest filename.
    Corresponds to the ``-m`` argument to the :command:`repo init` command.

``tarball``
    (optional, defaults to ``None``): the repo tarball used for fast bootstrap.
    If not present the tarball will be created automatically after first sync.
    It is a copy of the ``.repo`` directory which contains all the Git objects.
    This feature helps to minimize network usage on very big projects with lots of workers.

``jobs``
    (optional, defaults to ``None``): Number of projects to fetch simultaneously while syncing.
    Passed to repo sync subcommand with "-j".

``syncAllBranches``
    (optional, defaults to ``False``): renderable boolean to control whether ``repo`` syncs all branches.
    I.e. ``repo sync -c``

``depth``
    (optional, defaults to 0): Depth argument passed to repo init.
    Specifies the amount of git history to store.
    A depth of 1 is useful for shallow clones.
    This can save considerable disk space on very large projects.

``updateTarballAge``
    (optional, defaults to "one week"): renderable to control the policy of updating of the tarball given properties.
    Returns: max age of tarball in seconds, or ``None``, if we want to skip tarball update.
    The default value should be good trade off on size of the tarball, and update frequency compared to cost of tarball creation

``repoDownloads``
    (optional, defaults to None): list of ``repo download`` commands to perform at the end of the Repo step each string in the list will be prefixed ``repo download``, and run as is.
    This means you can include parameter in the string.
    For example:

    * ``["-c project 1234/4"]`` will cherry-pick patchset 4 of patch 1234 in project ``project``
    * ``["-f project 1234/4"]`` will enforce fast-forward on patchset 4 of patch 1234 in project ``project``

.. py:class:: buildbot.steps.source.repo.RepoDownloadsFromProperties

``util.repo.DownloadsFromProperties`` can be used as a renderable of the ``repoDownload`` parameter it will look in passed properties for string with following possible format:

*  ``repo download project change_number/patchset_number``
*  ``project change_number/patchset_number``
*  ``project/change_number/patchset_number``

All of these properties will be translated into a :command:`repo download`.
This feature allows integrators to build with several pending interdependent changes, which at the moment cannot be described properly in Gerrit, and can only be described by humans.

.. py:class:: buildbot.steps.source.repo.RepoDownloadsFromChangeSource

``util.repo.DownloadsFromChangeSource`` can be used as a renderable of the ``repoDownload`` parameter

This rendereable integrates with :bb:chsrc:`GerritChangeSource`, and will automatically use the :command:`repo download` command of repo to download the additionnal changes introduced by a pending changeset.

.. note::

   You can use the two above Rendereable in conjuction by using the class ``buildbot.process.properties.FlattenList``

For example::

    from buildbot.plugins import steps, util

    factory.addStep(steps.Repo(manifestURL='git://gerrit.example.org/manifest.git',
                               repoDownloads=util.FlattenList([
                                    util.RepoDownloadsFromChangeSource(),
                                    util.RepoDownloadsFromProperties("repo_downloads")
                               ])))

.. bb:step:: Gerrit

.. _Step-Gerrit:

Gerrit
++++++

.. py:class:: buildbot.steps.source.gerrit.Gerrit

:bb:step:`Gerrit` step is exactly like the :bb:step:`Git` step, except that it integrates with :bb:chsrc:`GerritChangeSource`, and will automatically checkout the additional changes.

Gerrit integration can be also triggered using forced build with property named ``gerrit_change`` with values in format ``change_number/patchset_number``.
This property will be translated into a branch name.
This feature allows integrators to build with several pending interdependent changes, which at the moment cannot be described properly in Gerrit, and can only be described by humans.

.. bb:step:: Darcs

.. _Step-Darcs:

Darcs
+++++

.. py:class:: buildbot.steps.source.darcs.Darcs

The :bb:step:`Darcs` build step performs a `Darcs <http://darcs.net/>`_ checkout or update.

::

    from buildbot.plugins import steps

    factory.addStep(steps.Darcs(repourl='http://path/to/repo',
                                mode='full', method='clobber', retry=(10, 1)))

Darcs step takes the following arguments:

``repourl``
    (required): The URL at which the Darcs source repository is available.

``mode``

    (optional): defaults to ``'incremental'``.
    Specifies whether to clean the build tree or not.

    ``incremental``
      The source is update, but any built files are left untouched.

    ``full``
      The build tree is clean of any built files.
      The exact method for doing this is controlled by the ``method`` argument.

``method``
   (optional): defaults to ``copy`` when mode is ``full``.
   Darcs' incremental mode does not require a method.
   The full mode has two methods defined:

   ``clobber``
      It removes the working directory for each build then makes full checkout.

   ``copy``
      This first checkout source into source directory then copy the ``source`` directory to ``build`` directory then performs the build operation in the copied directory.
      This way we make fresh builds with very less bandwidth to download source.
      The behavior of source checkout follows exactly same as incremental.
      It performs all the incremental checkout behavior in ``source`` directory.

.. bb:step:: Monotone

.. _Step-Monotone:

Monotone
++++++++

.. py:class:: buildbot.steps.source.mtn.Monotone

The :bb:step:`Monotone` build step performs a `Monotone <http://www.monotone.ca/>`_ checkout or update.

::

    from buildbot.plugins import steps

    factory.addStep(steps.Monotone(repourl='http://path/to/repo',
                                   mode='full', method='clobber',
                                   branch='some.branch.name', retry=(10, 1)))


Monotone step takes the following arguments:

``repourl``
    the URL at which the Monotone source repository is available.

``branch``
    this specifies the name of the branch to use when a Build does not provide one of its own.

``progress``
    this is a boolean that has a pull from the repository use ``--ticker=dot`` instead of the default ``--ticker=none``.

``mode``

  (optional): defaults to ``'incremental'``.
  Specifies whether to clean the build tree or not.
  In any case, the worker first pulls from the given remote repository
  to synchronize (or possibly initialize) its local database. The mode
  and method only affect how the build tree is checked-out or updated
  from the local database.

    ``incremental``
      The source is update, but any built files are left untouched.

    ``full``
      The build tree is clean of any built files.
      The exact method for doing this is controlled by the ``method`` argument.
      Even in this mode, the revisions already pulled remain in the database
      and a fresh pull is rarely needed.

``method``

   (optional): defaults to ``copy`` when mode is ``full``.
   Monotone's incremental mode does not require a method.
   The full mode has four methods defined:

   ``clobber``
      It removes the build directory entirely then makes fresh checkout from
      the database.

   ``clean``
      This remove all other files except those tracked and ignored by Monotone.
      It will remove all the files that appear in :command:`mtn ls unknown`.
      Then it will pull from remote and update the working directory.

   ``fresh``
      This remove all other files except those tracked by Monotone.
      It will remove all the files that appear in :command:`mtn ls ignored` and :command:`mtn ls unknows`.
      Then pull and update similar to ``clean``

   ``copy``
      This first checkout source into source directory then copy the ``source`` directory to ``build`` directory then performs the build operation in the copied directory.
      This way we make fresh builds with very less bandwidth to download source.
      The behavior of source checkout follows exactly same as incremental.
      It performs all the incremental checkout behavior in ``source`` directory.

.. bb:step:: ShellCommand

ShellCommand
------------

Most interesting steps involve executing a process of some sort on the worker.
The :bb:step:`ShellCommand` class handles this activity.

Several subclasses of :bb:step:`ShellCommand` are provided as starting points for common build steps.

Using ShellCommands
+++++++++++++++++++

.. py:class:: buildbot.steps.shell.ShellCommand

This is a useful base class for just about everything you might want to do during a build (except for the initial source checkout).
It runs a single command in a child shell on the worker.
All stdout/stderr is recorded into a :class:`LogFile`.
The step usually finishes with a status of ``FAILURE`` if the command's exit code is non-zero, otherwise it has a status of ``SUCCESS``.

The preferred way to specify the command is with a list of argv strings, since this allows for spaces in filenames and avoids doing any fragile shell-escaping.
You can also specify the command with a single string, in which case the string is given to :samp:`/bin/sh -c {COMMAND}` for parsing.

On Windows, commands are run via ``cmd.exe /c`` which works well.
However, if you're running a batch file, the error level does not get propagated correctly unless you add 'call' before your batch file's name: ``cmd=['call', 'myfile.bat', ...]``.

The :bb:step:`ShellCommand` arguments are:

``command``
    a list of strings (preferred) or single string (discouraged) which specifies the command to be run.
    A list of strings is preferred because it can be used directly as an argv array.
    Using a single string (with embedded spaces) requires the worker to pass the string to :command:`/bin/sh` for interpretation, which raises all sorts of difficult questions about how to escape or interpret shell metacharacters.

    If ``command`` contains nested lists (for example, from a properties substitution), then that list will be flattened before it is executed.

``workdir``
    All ShellCommands are run by default in the ``workdir``, which defaults to the :file:`build` subdirectory of the worker builder's base directory.
    The absolute path of the workdir will thus be the worker's basedir (set as an option to ``buildslave create-slave``, :ref:`Creating-a-worker`) plus the builder's basedir (set in the builder's ``builddir`` key in :file:`master.cfg`) plus the workdir itself (a class-level attribute of the BuildFactory, defaults to :file:`build`).

    For example::

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(command=["make", "test"],
                                     workdir="build/tests"))

``env``
    a dictionary of environment strings which will be added to the child command's environment.
    For example, to run tests with a different i18n language setting, you might use::

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(command=["make", "test"],
                                     env={'LANG': 'fr_FR'}))

    These variable settings will override any existing ones in the worker's environment or the environment specified in the :class:`Builder`.
    The exception is :envvar:`PYTHONPATH`, which is merged with (actually prepended to) any existing :envvar:`PYTHONPATH` setting.
    The following example will prepend :file:`/home/buildbot/lib/python` to any existing :envvar:`PYTHONPATH`::

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(
                      command=["make", "test"],
                      env={'PYTHONPATH': "/home/buildbot/lib/python"}))

    To avoid the need of concatenating path together in the master config file, if the value is a list, it will be joined together using the right platform dependant separator.

    Those variables support expansion so that if you just want to prepend :file:`/home/buildbot/bin` to the :envvar:`PATH` environment variable, you can do it by putting the value ``${PATH}`` at the end of the value like in the example below.
    Variables that don't exist on the worker will be replaced by ``""``.

    ::

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(
                      command=["make", "test"],
                      env={'PATH': ["/home/buildbot/bin",
                                    "${PATH}"]}))

    Note that environment values must be strings (or lists that are turned into strings).
    In particular, numeric properties such as ``buildnumber`` must be substituted using :ref:`Interpolate`.

``want_stdout``
    if ``False``, stdout from the child process is discarded rather than being sent to the buildmaster for inclusion in the step's :class:`LogFile`.

``want_stderr``
    like ``want_stdout`` but for :file:`stderr`.
    Note that commands run through a PTY do not have separate :file:`stdout`/:file:`stderr` streams: both are merged into :file:`stdout`.

``usePTY``
    Should this command be run in a ``pty``?
    ``False`` by default.
    This option is not available on Windows.

    In general, you do not want to use a pseudo-terminal.
    This is is *only* useful for running commands that require a terminal - for example, testing a command-line application that will only accept passwords read from a terminal.
    Using a pseudo-terminal brings lots of compatibility problems, and prevents Buildbot from distinguishing the standard error (red) and standard output (black) streams.

    In previous versions, the advantage of using a pseudo-terminal was that ``grandchild`` processes were more likely to be cleaned up if the build was interrupted or times out.
    This occurred because using a pseudo-terminal incidentally puts the command into its own process group.

    As of Buildbot-0.8.4, all commands are placed in process groups, and thus grandchild processes will be cleaned up properly.

``logfiles``
    Sometimes commands will log interesting data to a local file, rather than emitting everything to stdout or stderr.
    For example, Twisted's :command:`trial` command (which runs unit tests) only presents summary information to stdout, and puts the rest into a file named :file:`_trial_temp/test.log`.
    It is often useful to watch these files as the command runs, rather than using :command:`/bin/cat` to dump their contents afterwards.

    The ``logfiles=`` argument allows you to collect data from these secondary logfiles in near-real-time, as the step is running.
    It accepts a dictionary which maps from a local Log name (which is how the log data is presented in the build results) to either a remote filename (interpreted relative to the build's working directory), or a dictionary of options.
    Each named file will be polled on a regular basis (every couple of seconds) as the build runs, and any new text will be sent over to the buildmaster.

    If you provide a dictionary of options instead of a string, you must specify the ``filename`` key.
    You can optionally provide a ``follow`` key which is a boolean controlling whether a logfile is followed or concatenated in its entirety.
    Following is appropriate for logfiles to which the build step will append, where the pre-existing contents are not interesting.
    The default value for ``follow`` is ``False``, which gives the same behavior as just providing a string filename.

    ::

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(
                           command=["make", "test"],
                           logfiles={"triallog": "_trial_temp/test.log"}))

    The above example will add a log named 'triallog' on the master, based on :file:`_trial_temp/test.log` on the worker.

    ::

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(command=["make", "test"],
                                     logfiles={
                                         "triallog": {
                                            "filename": "_trial_temp/test.log",
                                            "follow": True
                                         }
                                     }))


``lazylogfiles``
    If set to ``True``, logfiles will be tracked lazily, meaning that they will only be added when and if something is written to them.
    This can be used to suppress the display of empty or missing log files.
    The default is ``False``.

``timeout``
    if the command fails to produce any output for this many seconds, it is assumed to be locked up and will be killed.
    This defaults to 1200 seconds.
    Pass ``None`` to disable.

``maxTime``
    if the command takes longer than this many seconds, it will be killed.
    This is disabled by default.

``logEnviron``
    If this option is ``True`` (the default), then the step's logfile will describe the environment variables on the worker.
    In situations where the environment is not relevant and is long, it may be easier to set ``logEnviron=False``.

``interruptSignal``
    If the command should be interrupted (either by buildmaster or timeout etc.), what signal should be sent to the process, specified by name.
    By default this is "KILL" (9).
    Specify "TERM" (15) to give the process a chance to cleanup.
    This functionality requires a 0.8.6 worker or newer.

``sigtermTime``

    If set, when interrupting, try to kill the command with SIGTERM and wait for sigtermTime seconds before firing ``interuptSignal``.
    If None, ``interruptSignal`` will be fired immediately on interrupt.

``initialStdin``
    If the command expects input on stdin, that can be supplied a a string with this parameter.
    This value should not be excessively large, as it is handled as a single string throughout Buildbot -- for example, do not pass the contents of a tarball with this parameter.

``decodeRC``
    This is a dictionary that decodes exit codes into results value.
    For example, ``{0:SUCCESS,1:FAILURE,2:WARNINGS}``, will treat the exit code ``2`` as WARNINGS.
    The default is to treat just 0 as successful.
    (``{0:SUCCESS}``) any exit code not present in the dictionary will be treated as ``FAILURE``

.. bb:step:: ShellSequence

Shell Sequence
++++++++++++++

Some steps have a specific purpose, but require multiple shell commands to implement them.
For example, a build is often ``configure; make; make install``.
We have two ways to handle that:

* Create one shell command with all these.
  To put the logs of each commands in separate logfiles, we need to re-write the script as ``configure 1> configure_log; ...`` and to add these ``configure_log`` files as ``logfiles`` argument of the buildstep.
  This has the drawback of complicating the shell script, and making it harder to maintain as the logfile name is put in different places.

* Create three :bb:step:`ShellCommand` instances, but this loads the build UI unnecessarily.

:bb:step:`ShellSequence` is a class to execute not one but a sequence of shell commands during a build.
It takes as argument a renderable, or list of commands which are :class:`~buildbot.steps.shellsequence.ShellArg` objects.
Each such object represents a shell invocation.

The single :bb:step:`ShellSequence` argument aside from the common parameters is:

``commands``

A list of :class:`~buildbot.steps.shellsequence.ShellArg` objects or a renderable the returns a list of :class:`~buildbot.steps.shellsequence.ShellArg` objects.

::

    from buildbot.plugins import steps, util

    f.addStep(steps.ShellSequence(
        commands=[
            util.ShellArg(command=['configure']),
            util.ShellArg(command=['make'], logfile='make'),
            util.ShellArg(command=['make', 'check_warning'], logfile='warning', warnOnFailure=True),
            util.ShellArg(command=['make', 'install'], logfile='make install')
        ]))

All these commands share the same configuration of ``environment``, ``workdir`` and ``pty`` usage that can be setup the same way as in :bb:step:`ShellCommand`.

.. py:class:: buildbot.steps.shellsequence.ShellArg(self, command=None, logfile=None, haltOnFailure=False, flunkOnWarnings=False, flunkOnFailure=False, warnOnWarnings=False, warnOnFailure=False)

    :param command: (see the :bb:step:`ShellCommand` ``command`` argument),
    :param logfile: optional log file name, used as the stdio log of the command

    The ``haltOnFailure``, ``flunkOnWarnings``, ``flunkOnFailure``, ``warnOnWarnings``, ``warnOnFailure`` parameters drive the execution of the sequence, the same way steps are scheduled in the build.
    They have the same default values as for buildsteps - see :ref:`Buildstep-Common-Parameters`.

    Any of the arguments to this class can be renderable.

    Note that if ``logfile`` name does not start with the prefix ``stdio``, that prefix will be set like ``stdio <logfile>``.


The two :bb:step:`ShellSequence` methods below tune the behavior of how the list of shell commands are executed, and can be overridden in subclasses.

.. py:class:: buildbot.steps.shellsequence.ShellSequence

    .. py:method:: shouldRunTheCommand(oneCmd)

        :param oneCmd: a string or a list of strings, as rendered from a :py:class:`~buildbot.steps.shellsequence.ShellArg` instance's ``command`` argument.

        Determine whether the command ``oneCmd`` should be executed.
        If ``shouldRunTheCommand`` returns ``False``, the result of the command will be recorded as SKIPPED.
        The default methods skips all empty strings and empty lists.

    .. py:method:: getFinalState()

        Return the status text of the step in the end.
        The default value is to set the text describing the execution of the last shell command.

    .. py:method:: runShellSequence(commands):

        :param commands: list of shell args

        This method actually runs the shell sequence.
        The default ``run`` method calls ``runShellSequence``, but subclasses can override ``run`` to perform other operations, if desired.

.. bb:step:: Configure

Configure
+++++++++

.. py:class:: buildbot.steps.shell.Configure

This is intended to handle the :command:`./configure` step from autoconf-style projects, or the ``perl Makefile.PL`` step from perl :file:`MakeMaker.pm`-style modules.
The default command is :command:`./configure` but you can change this by providing a ``command=`` parameter.
The arguments are identical to :bb:step:`ShellCommand`.

::

    from buildbot.plugins import steps

    f.addStep(steps.Configure())

.. bb:step:: CMake

CMake
+++++

.. py:class:: buildbot.steps.cmake.CMake

This is intended to handle the :command:`cmake` step for projects that use `CMake-based build systems <http://cmake.org>`_.

.. note::

   Links below point to the latest CMake documentation.
   Make sure that you check the documentation for the CMake you use.

In addition to the parameters :bb:step:`ShellCommand` supports, this step accepts the following parameters:

``path``
    Either a path to a source directory to (re-)generate a build system for it in the current working directory.
    Or an existing build directory to re-generate its build system.

``generator``
    A build system generator.
    See `cmake-generators(7) <https://cmake.org/cmake/help/latest/manual/cmake-generators.7.html>`_ for available options.

``definitions``
    A dictionary that contains parameters that will be converted to ``-D{name}={value}`` when passed to CMake.
    Refer to `cmake(1) <https://cmake.org/cmake/help/latest/manual/cmake.1.html>`_ for more information.

``options``
    A list or a tuple that contains options that will be passed to CMake as is.
    Refer to `cmake(1) <https://cmake.org/cmake/help/latest/manual/cmake.1.html>`_ for more information.

``cmake``
    Path to the CMake binary.
    Default is :command:`cmake`

.. code-block:: python

    from buildbot.plugins import steps

    ...

    factory.addStep(
        steps.CMake(
            generator='Ninja',
            definitions={
                'CMAKE_BUILD_TYPE': Property('BUILD_TYPE')
            },
            options=[
                '-Wno-dev'
            ]
        )
    )

    ...

.. bb:step:: Compile

Compile
+++++++

.. index:: Properties; warnings-count

This is meant to handle compiling or building a project written in C.
The default command is ``make all``.
When the compilation is finished, the log file is scanned for GCC warning messages, a summary log is created with any problems that were seen, and the step is marked as WARNINGS if any were discovered.
Through the :class:`WarningCountingShellCommand` superclass, the number of warnings is stored in a Build Property named `warnings-count`, which is accumulated over all :bb:step:`Compile` steps (so if two warnings are found in one step, and three are found in another step, the overall build will have a `warnings-count` property of 5).
Each step can be optionally given a maximum number of warnings via the maxWarnCount parameter.
If this limit is exceeded, the step will be marked as a failure.

The default regular expression used to detect a warning is ``'.*warning[: ].*'`` , which is fairly liberal and may cause false-positives.
To use a different regexp, provide a ``warningPattern=`` argument, or use a subclass which sets the ``warningPattern`` attribute::

    from buildbot.plugins import steps

    f.addStep(steps.Compile(command=["make", "test"],
                            warningPattern="^Warning: "))

The ``warningPattern=`` can also be a pre-compiled Python regexp object: this makes it possible to add flags like ``re.I`` (to use case-insensitive matching).

Note that the compiled ``warningPattern`` will have its :meth:`match` method called, which is subtly different from a :meth:`search`.
Your regular expression must match the from the beginning of the line.
This means that to look for the word "warning" in the middle of a line, you will need to prepend ``'.*'`` to your regular expression.

The ``suppressionFile=`` argument can be specified as the (relative) path of a file inside the workdir defining warnings to be suppressed from the warning counting and log file.
The file will be uploaded to the master from the worker before compiling, and any warning matched by a line in the suppression file will be ignored.
This is useful to accept certain warnings (e.g. in some special module of the source tree or in cases where the compiler is being particularly stupid), yet still be able to easily detect and fix the introduction of new warnings.

The file must contain one line per pattern of warnings to ignore.
Empty lines and lines beginning with ``#`` are ignored.
Other lines must consist of a regexp matching the file name, followed by a colon (``:``), followed by a regexp matching the text of the warning.
Optionally this may be followed by another colon and a line number range.
For example:

.. code-block:: none

    # Sample warning suppression file

    mi_packrec.c : .*result of 32-bit shift implicitly converted to 64 bits.* : 560-600
    DictTabInfo.cpp : .*invalid access to non-static.*
    kernel_types.h : .*only defines private constructors and has no friends.* : 51

If no line number range is specified, the pattern matches the whole file; if only one number is given it matches only on that line.

The default warningPattern regexp only matches the warning text, so line numbers and file names are ignored.
To enable line number and file name matching, provide a different regexp and provide a function (callable) as the argument of ``warningExtractor=``.
The function is called with three arguments: the :class:`BuildStep` object, the line in the log file with the warning, and the ``SRE_Match`` object of the regexp search for ``warningPattern``.
It should return a tuple ``(filename, linenumber, warning_test)``.
For example::

    f.addStep(Compile(command=["make"],
                      warningPattern="^(.\*?):([0-9]+): [Ww]arning: (.\*)$",
                      warningExtractor=Compile.warnExtractFromRegexpGroups,
                      suppressionFile="support-files/compiler_warnings.supp"))

(``Compile.warnExtractFromRegexpGroups`` is a pre-defined function that returns the filename, linenumber, and text from groups (1,2,3) of the regexp match).

In projects with source files in multiple directories, it is possible to get full path names for file names matched in the suppression file, as long as the build command outputs the names of directories as they are entered into and left again.
For this, specify regexps for the arguments ``directoryEnterPattern=`` and ``directoryLeavePattern=``.
The ``directoryEnterPattern=`` regexp should return the name of the directory entered into in the first matched group.
The defaults, which are suitable for GNU Make, are these::

    directoryEnterPattern="make.*: Entering directory [\"`'](.*)['`\"]"
    directoryLeavePattern="make.*: Leaving directory"

(TODO: this step needs to be extended to look for GCC error messages as well, and collect them into a separate logfile, along with the source code filenames involved).

.. index:: Visual Studio, Visual C++
.. bb:step:: VC6
.. bb:step:: VC7
.. bb:step:: VC8
.. bb:step:: VC9
.. bb:step:: VC10
.. bb:step:: VC11
.. bb:step:: VC12
.. bb:step:: VS2003
.. bb:step:: VS2005
.. bb:step:: VS2008
.. bb:step:: VS2010
.. bb:step:: VS2012
.. bb:step:: VS2013
.. bb:step:: VCExpress9
.. bb:step:: MsBuild4
.. bb:step:: MsBuild12

Visual C++
++++++++++

These steps are meant to handle compilation using Microsoft compilers.
VC++ 6-12 (aka Visual Studio 2003-2013 and VCExpress9) are supported via calling ``devenv``.
Msbuild as well as Windows Driver Kit 8 are supported via the ``MsBuild4`` and ``MsBuild12`` steps.
These steps will take care of setting up a clean compilation environment, parsing the generated output in real time, and delivering as detailed as possible information about the compilation executed.

All of the classes are in :mod:`buildbot.steps.vstudio`.
The available classes are:

* ``VC6``
* ``VC7``
* ``VC8``
* ``VC9``
* ``VC10``
* ``VC11``
* ``VC12``
* ``VS2003``
* ``VS2005``
* ``VS2008``
* ``VS2010``
* ``VS2012``
* ``VS2013``
* ``VCExpress9``
* ``MsBuild4``
* ``MsBuild12``

The available constructor arguments are

``mode``
    The mode default to ``rebuild``, which means that first all the remaining object files will be cleaned by the compiler.
    The alternate values are ``build``, where only the updated files will be recompiled, and ``clean``, where the current build files are removed and no compilation occurs.

``projectfile``
    This is a mandatory argument which specifies the project file to be used during the compilation.

``config``
    This argument defaults to ``release`` an gives to the compiler the configuration to use.

``installdir``
    This is the place where the compiler is installed.
    The default value is compiler specific and is the default place where the compiler is installed.

``useenv``
    This boolean parameter, defaulting to ``False`` instruct the compiler to use its own settings or the one defined through the environment variables :envvar:`PATH`, :envvar:`INCLUDE`, and :envvar:`LIB`.
    If any of the ``INCLUDE`` or  ``LIB`` parameter is defined, this parameter automatically switches to ``True``.

``PATH``
    This is a list of path to be added to the :envvar:`PATH` environment variable.
    The default value is the one defined in the compiler options.

``INCLUDE``
    This is a list of path where the compiler will first look for include files.
    Then comes the default paths defined in the compiler options.

``LIB``
    This is a list of path where the compiler will first look for libraries.
    Then comes the default path defined in the compiler options.

``arch``
    That one is only available with the class VS2005 (VC8).
    It gives the target architecture of the built artifact.
    It defaults to ``x86`` and does not apply to ``MsBuild4`` or ``MsBuild12``.
    Please see ``platform`` below.

``project``
    This gives the specific project to build from within a workspace.
    It defaults to building all projects.
    This is useful for building cmake generate projects.

``platform``
    This is a mandatory argument for ``MsBuild4`` and ``MsBuild12`` specifying the target platform such as 'Win32', 'x64' or 'Vista Debug'.
    The last one is an example of driver targets that appear once Windows Driver Kit 8 is installed.

Here is an example on how to drive compilation with Visual Studio 2013::

    from buildbot.plugins import steps

    f.addStep(
        steps.VS2013(projectfile="project.sln", config="release",
            arch="x64", mode="build",
               INCLUDE=[r'C:\3rd-party\libmagic\include'],
               LIB=[r'C:\3rd-party\libmagic\lib-x64']))

Here is a similar example using "MsBuild12"::

    from buildbot.plugins import steps

    # Build one project in Release mode for Win32
    f.addStep(
        steps.MsBuild12(projectfile="trunk.sln", config="Release", platform="Win32",
                workdir="trunk",
                project="tools\\protoc"))

    # Build the entire solution in Debug mode for x64
    f.addStep(
        steps.MsBuild12(projectfile="trunk.sln", config='Debug', platform='x64',
                workdir="trunk"))


.. bb:step:: Cppcheck

Cppcheck
++++++++

This step runs ``cppcheck``, analyse its output, and set the outcome in :ref:`Properties`.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Cppcheck(enable=['all'], inconclusive=True]))

This class adds the following arguments:

``binary``
    (Optional, default to ``cppcheck``)
    Use this if you need to give the full path to the cppcheck binary or if your binary is called differently.

``source``
    (Optional, default to ``['.']``)
    This is the list of paths for the sources to be checked by this step.

``enable``
    (Optional)
    Use this to give a list of the message classes that should be in cppcheck report.
    See the cppcheck man page for more information.

``inconclusive``
    (Optional)
    Set this to ``True`` if you want cppcheck to also report inconclusive results.
    See the cppcheck man page for more information.

``extra_args``
    (Optional)
    This is the list of extra arguments to be given to the cppcheck command.

All other arguments are identical to :bb:step:`ShellCommand`.

.. bb:step:: Robocopy

Robocopy
++++++++

.. py:class:: buildbot.steps.mswin.Robocopy

This step runs ``robocopy`` on Windows.

`Robocopy <http://technet.microsoft.com/en-us/library/cc733145.aspx>`_ is available in versions of Windows starting with Windows Vista and Windows Server 2008.
For previous versions of Windows, it's available as part of the `Windows Server 2003 Resource Kit Tools <http://www.microsoft.com/en-us/download/details.aspx?id=17657>`_.

::

    from buildbot.plugins import steps, util

    f.addStep(
        steps.Robocopy(
            name='deploy_binaries',
            description='Deploying binaries...',
            descriptionDone='Deployed binaries.',
            source=util.Interpolate('Build\\Bin\\%(prop:configuration)s'),
            destination=util.Interpolate('%(prop:deploy_dir)\\Bin\\%(prop:configuration)s'),
            mirror=True
        )
    )

Available constructor arguments are:

``source``
    The path to the source directory (mandatory).

``destination``
    The path to the destination directory (mandatory).

``files``
    An array of file names or patterns to copy.

``recursive``
    Copy files and directories recursively (``/E`` parameter).

``mirror``
    Mirror the source directory in the destination directory, including removing files that don't exist anymore (``/MIR`` parameter).

``move``
    Delete the source directory after the copy is complete (``/MOVE`` parameter).

``exclude_files``
    An array of file names or patterns to exclude from the copy (``/XF`` parameter).

``exclude_dirs``
    An array of directory names or patterns to exclude from the copy (``/XD`` parameter).

``custom_opts``
    An array of custom parameters to pass directly to the ``robocopy`` command.

``verbose``
    Whether to output verbose information (``/V /TS /TP`` parameters).

Note that parameters ``/TEE /NP`` will always be appended to the command to signify, respectively, to output logging to the console, use Unicode logging, and not print any percentage progress information for each file.

.. bb:step:: Test

Test
++++

::

    from buildbot.plugins import steps

    f.addStep(steps.Test())

This is meant to handle unit tests.
The default command is :command:`make test`, and the ``warnOnFailure`` flag is set.
The other arguments are identical to :bb:step:`ShellCommand`.

.. bb:step:: TreeSize

.. index:: Properties; tree-size-KiB

TreeSize
++++++++

::

    from buildbot.plugins import steps

    f.addStep(steps.TreeSize())

This is a simple command that uses the :command:`du` tool to measure the size of the code tree.
It puts the size (as a count of 1024-byte blocks, aka 'KiB' or 'kibibytes') on the step's status text, and sets a build property named ``tree-size-KiB`` with the same value.
All arguments are identical to :bb:step:`ShellCommand`.

.. bb:step:: PerlModuleTest

PerlModuleTest
++++++++++++++

::

    from buildbot.plugins import steps

    f.addStep(steps.PerlModuleTest())

This is a simple command that knows how to run tests of perl modules.
It parses the output to determine the number of tests passed and failed and total number executed, saving the results for later query.
The command is ``prove --lib lib -r t``, although this can be overridden with the ``command`` argument.
All other arguments are identical to those for :bb:step:`ShellCommand`.

.. bb:step:: MTR

MTR (mysql-test-run)
++++++++++++++++++++

The :bb:step:`MTR` class is a subclass of :bb:step:`Test`.
It is used to run test suites using the mysql-test-run program, as used in MySQL, Drizzle, MariaDB, and MySQL storage engine plugins.

The shell command to run the test suite is specified in the same way as for the :bb:step:`Test` class.
The :bb:step:`MTR` class will parse the output of running the test suite, and use the count of tests executed so far to provide more accurate completion time estimates.
Any test failures that occur during the test are summarized on the Waterfall Display.

Server error logs are added as additional log files, useful to debug test failures.

Optionally, data about the test run and any test failures can be inserted into a database for further analysis and report generation.
To use this facility, create an instance of :class:`twisted.enterprise.adbapi.ConnectionPool` with connections to the database.
The necessary tables can be created automatically by setting ``autoCreateTables`` to ``True``, or manually using the SQL found in the :file:`mtrlogobserver.py` source file.

One problem with specifying a database is that each reload of the configuration will get a new instance of ``ConnectionPool`` (even if the connection parameters are the same).
To avoid that Buildbot thinks the builder configuration has changed because of this, use the :class:`steps.mtrlogobserver.EqConnectionPool` subclass of :class:`ConnectionPool`, which implements an equiality operation that avoids this problem.

Example use::

    from buildbot.plugins import steps, util

    myPool = util.EqConnectionPool("MySQLdb", "host", "buildbot", "password", "db")
    myFactory.addStep(steps.MTR(workdir="mysql-test", dbpool=myPool,
                                command=["perl", "mysql-test-run.pl", "--force"]))

The :bb:step:`MTR` step's arguments are:

``textLimit``
    Maximum number of test failures to show on the waterfall page (to not flood the page in case of a large number of test failures.
    Defaults to 5.

``testNameLimit``
    Maximum length of test names to show unabbreviated in the waterfall page, to avoid excessive column width.
    Defaults to 16.

``parallel``
    Value of option `--parallel` option used for :file:`mysql-test-run.pl` (number of processes used to run the test suite in parallel).
    Defaults to 4.
    This is used to determine the number of server error log files to download from the worker.
    Specifying a too high value does not hurt (as nonexisting error logs will be ignored), however if using option `--parallel` value greater than the default it needs to be specified, or some server error logs will be missing.

``dbpool``
    An instance of :class:`twisted.enterprise.adbapi.ConnectionPool`, or ``None``.
    Defaults to ``None``.
    If specified, results are inserted into the database using the :class:`ConnectionPool`.

``autoCreateTables``
    Boolean, defaults to ``False``.
    If ``True`` (and ``dbpool`` is specified), the necessary database tables will be created automatically if they do not exist already.
    Alternatively, the tables can be created manually from the SQL statements found in the :file:`mtrlogobserver.py` source file.

``test_type``
    Short string that will be inserted into the database in the row for the test run.
    Defaults to the empty string, but can be specified to identify different types of test runs.

``test_info``
    Descriptive string that will be inserted into the database in the row for the test run.
    Defaults to the empty string, but can be specified as a user-readable description of this particular test run.

``mtr_subdir``
    The subdirectory in which to look for server error log files.
    Defaults to :file:`mysql-test`, which is usually correct.
    :ref:`Interpolate` is supported.

.. bb:step:: SubunitShellCommand

.. _Step-SubunitShellCommand:

SubunitShellCommand
+++++++++++++++++++

.. py:class:: buildbot.steps.subunit.SubunitShellCommand

This buildstep is similar to :bb:step:`ShellCommand`, except that it runs the log content through a subunit filter to extract test and failure counts.

::

    from buildbot.plugins import steps

    f.addStep(steps.SubunitShellCommand(command="make test"))

This runs ``make test`` and filters it through subunit.
The 'tests' and 'test failed' progress metrics will now accumulate test data from the test run.

If ``failureOnNoTests`` is ``True``, this step will fail if no test is run.
By default ``failureOnNoTests`` is False.

.. _Worker-Filesystem-Steps:

Worker Filesystem Steps
-----------------------

Here are some buildsteps for manipulating the worker's filesystem.

.. bb:step:: FileExists

FileExists
++++++++++

This step will assert that a given file exists, failing if it does not.
The filename can be specified with a property.

::

    from buildbot.plugins import steps

    f.addStep(steps.FileExists(file='test_data'))

This step requires worker version 0.8.4 or later.

.. bb:step:: CopyDirectory

CopyDirectory
+++++++++++++

This command copies a directory on the worker.

::

    from buildbot.plugins import steps

    f.addStep(steps.CopyDirectory(src="build/data", dest="tmp/data"))

This step requires worker version 0.8.5 or later.

The CopyDirectory step takes the following arguments:

``timeout``
    if the copy command fails to produce any output for this many seconds, it is assumed to be locked up and will be killed.
    This defaults to 120 seconds.
    Pass ``None`` to disable.

``maxTime``
    if the command takes longer than this many seconds, it will be killed.
    This is disabled by default.

.. bb:step:: RemoveDirectory

RemoveDirectory
+++++++++++++++

This command recursively deletes a directory on the worker.

::

    from buildbot.plugins import steps

    f.addStep(steps.RemoveDirectory(dir="build/build"))

This step requires worker version 0.8.4 or later.

.. bb:step:: MakeDirectory

MakeDirectory
+++++++++++++

This command creates a directory on the worker.

::

    from buildbot.plugins import steps

    f.addStep(steps.MakeDirectory(dir="build/build"))

This step requires worker version 0.8.5 or later.

.. _Python-BuildSteps:

Python BuildSteps
-----------------

Here are some :class:`BuildStep`\s that are specifically useful for projects
implemented in Python.

.. bb:step:: BuildEPYDoc

.. _Step-BuildEPYDoc:

BuildEPYDoc
+++++++++++

.. py:class:: buildbot.steps.python.BuildEPYDoc

`epydoc <http://epydoc.sourceforge.net/>`_ is a tool for generating
API documentation for Python modules from their docstrings.
It reads all the :file:`.py` files from your source tree, processes the docstrings therein, and creates a large tree of :file:`.html` files (or a single :file:`.pdf` file).

The :bb:step:`BuildEPYDoc` step will run :command:`epydoc` to produce this API documentation, and will count the errors and warnings from its output.

You must supply the command line to be used.
The default is ``make epydocs``, which assumes that your project has a :file:`Makefile` with an `epydocs` target.
You might wish to use something like :samp:`epydoc -o apiref source/{PKGNAME}` instead.
You might also want to add option `--pdf` to generate a PDF file instead of a large tree of HTML files.

The API docs are generated in-place in the build tree (under the workdir, in the subdirectory controlled by the option `-o` argument).
To make them useful, you will probably have to copy them to somewhere they can be read.
A command like ``rsync -ad apiref/ dev.example.com:~public_html/current-apiref/`` might be useful.
You might instead want to bundle them into a tarball and publish it in the same place where the generated install tarball is placed.

::

    from buildbot.plugins import steps

    f.addStep(steps.BuildEPYDoc(command=["epydoc", "-o", "apiref", "source/mypkg"]))

.. bb:step:: PyFlakes

.. _Step-PyFlake:

PyFlakes
++++++++

.. py:class:: buildbot.steps.python.PyFlakes

`PyFlakes <http://divmod.org/trac/wiki/DivmodPyflakes>`_ is a tool to perform basic static analysis of Python code to look for simple errors, like missing imports and references of undefined names.
It is like a fast and simple form of the C :command:`lint` program.
Other tools (like `pychecker <http://pychecker.sourceforge.net/>`_\) provide more detailed results but take longer to run.

The :bb:step:`PyFlakes` step will run pyflakes and count the various kinds of errors and warnings it detects.

You must supply the command line to be used.
The default is ``make pyflakes``, which assumes you have a top-level :file:`Makefile` with a ``pyflakes`` target.
You might want to use something like ``pyflakes .`` or ``pyflakes src``.

::

    from buildbot.plugins import steps

    f.addStep(steps.PyFlakes(command=["pyflakes", "src"]))

.. bb:step:: Sphinx

.. _Step-Sphinx:

Sphinx
++++++

.. py:class:: buildbot.steps.python.Sphinx

`Sphinx <http://sphinx.pocoo.org/>`_ is the Python Documentation Generator.
It uses `RestructuredText <http://docutils.sourceforge.net/rst.html>`_ as input format.

The :bb:step:`Sphinx` step will run :program:`sphinx-build` or any other program specified in its ``sphinx`` argument and count the various warnings and error it detects.

::

    from buildbot.plugins import steps

    f.addStep(steps.Sphinx(sphinx_builddir="_build"))

This step takes the following arguments:

``sphinx_builddir``
   (required) Name of the directory where the documentation will be generated.

``sphinx_sourcedir``
   (optional, defaulting to ``.``), Name the directory where the :file:`conf.py` file will be found

``sphinx_builder``
   (optional) Indicates the builder to use.

``sphinx``
   (optional, defaulting to :program:`sphinx-build`) Indicates the executable to run.

``tags``
   (optional) List of ``tags`` to pass to :program:`sphinx-build`

``defines``
   (optional) Dictionary of defines to overwrite values of the :file:`conf.py` file.

``mode``
   (optional) String, one of ``full`` or ``incremental`` (the default).
   If set to ``full``, indicates to Sphinx to rebuild everything without re-using the previous build results.

.. bb:step:: PyLint

.. _Step-PyLint:

PyLint
++++++

Similarly, the :bb:step:`PyLint` step will run :command:`pylint` and analyze the results.

You must supply the command line to be used.
There is no default.

::

    from buildbot.plugins import steps

    f.addStep(steps.PyLint(command=["pylint", "src"]))

.. bb:step:: Trial

.. _Step-Trial:

Trial
+++++

.. py:class:: buildbot.steps.python_twisted.Trial

This step runs a unit test suite using :command:`trial`, a unittest-like testing framework that is a component of Twisted Python.
Trial is used to implement Twisted's own unit tests, and is the unittest-framework of choice for many projects that use Twisted internally.

Projects that use trial typically have all their test cases in a 'test' subdirectory of their top-level library directory.
For example, for a package ``petmail``, the tests might be in :file:`petmail/test/test_*.py`.
More complicated packages (like Twisted itself) may have multiple test directories, like :file:`twisted/test/test_*.py` for the core functionality and :file:`twisted/mail/test/test_*.py` for the email-specific tests.

To run trial tests manually, you run the :command:`trial` executable and tell it where the test cases are located.
The most common way of doing this is with a module name.
For petmail, this might look like :command:`trial petmail.test`, which would locate all the :file:`test_*.py` files under :file:`petmail/test/`, running every test case it could find in them.
Unlike the ``unittest.py`` that comes with Python, it is not necessary to run the :file:`test_foo.py` as a script; you always let trial do the importing and running.
The step's ``tests``` parameter controls which tests trial will run: it can be a string or a list of strings.

To find the test cases, the Python search path must allow something like ``import petmail.test`` to work.
For packages that don't use a separate top-level :file:`lib` directory, ``PYTHONPATH=.`` will work, and will use the test cases (and the code they are testing) in-place.
``PYTHONPATH=build/lib`` or ``PYTHONPATH=build/lib.somearch`` are also useful when you do a ``python setup.py build`` step first.
The ``testpath`` attribute of this class controls what :envvar:`PYTHONPATH` is set to before running :command:`trial`.

Trial has the ability, through the ``--testmodule`` flag, to run only the set of test cases named by special ``test-case-name`` tags in source files.
We can get the list of changed source files from our parent Build and provide them to trial, thus running the minimal set of test cases needed to cover the Changes.
This is useful for quick builds, especially in trees with a lot of test cases.
The ``testChanges`` parameter controls this feature: if set, it will override ``tests``.

The trial executable itself is typically just :command:`trial`, and is typically found in the shell search path.
It can be overridden with the ``trial`` parameter.
This is useful for Twisted's own unittests, which want to use the copy of bin/trial that comes with the sources.

To influence the version of Python being used for the tests, or to add flags to the command, set the ``python`` parameter.
This can be a string (like ``python2.2``) or a list (like ``['python2.3', '-Wall']``).

Trial creates and switches into a directory named :file:`_trial_temp/` before running the tests, and sends the twisted log (which includes all exceptions) to a file named :file:`test.log`.
This file will be pulled up to the master where it can be seen as part of the status output.

::

    from buildbot.plugins import steps

    f.addStep(steps.Trial(tests='petmail.test'))

Trial has the ability to run tests on several workers in parallel (beginning with Twisted 12.3.0).
Set ``jobs`` to the number of workers you want to run.
Note that running :command:`trial` in this way will create multiple log files (named :file:`test.N.log`, :file:`err.N.log` and :file:`out.N.log` starting with ``N=0``) rather than a single :file:`test.log`.

This step takes the following arguments:

``jobs``
   (optional) Number of worker-resident trial workers to use when running the tests.
   Defaults to 1 worker.
   Only works with Twisted>=12.3.0.

.. bb:step:: RemovePYCs

RemovePYCs
++++++++++

.. py:class:: buildbot.steps.python_twisted.RemovePYCs

This is a simple built-in step that will remove ``.pyc`` files from the workdir.
This is useful in builds that update their source (and thus do not automatically delete ``.pyc`` files) but where some part of the build process is dynamically searching for Python modules.
Notably, trial has a bad habit of finding old test modules.

::

    from buildbot.plugins import steps

    f.addStep(steps.RemovePYCs())

.. index:: File Transfer

.. bb:step:: FileUpload
.. bb:step:: FileDownload

Transferring Files
------------------

.. py:class:: buildbot.steps.transfer.FileUpload
.. py:class:: buildbot.steps.transfer.FileDownload

Most of the work involved in a build will take place on the worker.
But occasionally it is useful to do some work on the buildmaster side.
The most basic way to involve the buildmaster is simply to move a file from the worker to the master, or vice versa.
There are a pair of steps named :bb:step:`FileUpload` and :bb:step:`FileDownload` to provide this functionality.
:bb:step:`FileUpload` moves a file *up to* the master, while :bb:step:`FileDownload` moves a file *down from* the master.

As an example, let's assume that there is a step which produces an HTML file within the source tree that contains some sort of generated project documentation.
We want to move this file to the buildmaster, into a :file:`~/public_html` directory, so it can be visible to developers.
This file will wind up in the worker-side working directory under the name :file:`docs/reference.html`.
We want to put it into the master-side :file:`~/public_html/ref.html`, and add a link to the HTML status to the uploaded file.

::

    from buildbot.plugins import steps

    f.addStep(steps.ShellCommand(command=["make", "docs"]))
    f.addStep(steps.FileUpload(workersrc="docs/reference.html",
                               masterdest="/home/bb/public_html/ref.html",
                               url="http://somesite/~buildbot/ref.html"))

The ``masterdest=`` argument will be passed to :meth:`os.path.expanduser`, so things like ``~`` will be expanded properly.
Non-absolute paths will be interpreted relative to the buildmaster's base directory.
Likewise, the ``workersrc=`` argument will be expanded and interpreted relative to the builder's working directory.

.. note::

   The copied file will have the same permissions on the master as on the worker, look at the ``mode=`` parameter to set it differently.

To move a file from the master to the worker, use the :bb:step:`FileDownload` command.
For example, let's assume that some step requires a configuration file that, for whatever reason, could not be recorded in the source code repository or generated on the worker side::

    from buildbot.plugins import steps

    f.addStep(steps.FileDownload(mastersrc="~/todays_build_config.txt",
                                 workerdest="build_config.txt"))
    f.addStep(steps.ShellCommand(command=["make", "config"]))

Like :bb:step:`FileUpload`, the ``mastersrc=`` argument is interpreted relative to the buildmaster's base directory, and the ``workerdest=`` argument is relative to the builder's working directory.
If the worker is running in :file:`~worker`, and the builder's ``builddir`` is something like :file:`tests-i386`, then the workdir is going to be :file:`~worker/tests-i386/build`, and a ``workerdest=`` of :file:`foo/bar.html` will get put in :file:`~worker/tests-i386/build/foo/bar.html`.
Both of these commands will create any missing intervening directories.

Other Parameters
++++++++++++++++

The ``maxsize=`` argument lets you set a maximum size for the file to be transferred.
This may help to avoid surprises: transferring a 100MB coredump when you were expecting to move a 10kB status file might take an awfully long time.
The ``blocksize=`` argument controls how the file is sent over the network: larger blocksizes are slightly more efficient but also consume more memory on each end, and there is a hard-coded limit of about 640kB.

The ``mode=`` argument allows you to control the access permissions of the target file, traditionally expressed as an octal integer.
The most common value is probably ``0755``, which sets the `x` executable bit on the file (useful for shell scripts and the like).
The default value for ``mode=`` is None, which means the permission bits will default to whatever the umask of the writing process is.
The default umask tends to be fairly restrictive, but at least on the worker you can make it less restrictive with a --umask command-line option at creation time (:ref:`Worker-Options`).

The ``keepstamp=`` argument is a boolean that, when ``True``, forces the modified and accessed time of the destination file to match the times of the source file.
When ``False`` (the default), the modified and accessed times of the destination file are set to the current time on the buildmaster.

The ``url=`` argument allows you to specify an url that will be displayed in the HTML status.
The title of the url will be the name of the item transferred (directory for :class:`DirectoryUpload` or file for :class:`FileUpload`).
This allows the user to add a link to the uploaded item if that one is uploaded to an accessible place.

.. bb:step:: DirectoryUpload

Transfering Directories
+++++++++++++++++++++++

.. py:class:: buildbot.steps.transfer.DirectoryUpload

To transfer complete directories from the worker to the master, there is a :class:`BuildStep` named :bb:step:`DirectoryUpload`.
It works like :bb:step:`FileUpload`, just for directories.
However it does not support the ``maxsize``, ``blocksize`` and ``mode`` arguments.
As an example, let's assume an generated project documentation, which consists of many files (like the output of :command:`doxygen` or :command:`epydoc`).
We want to move the entire documentation to the buildmaster, into a :file:`~/public_html/docs` directory, and add a link to the uploaded documentation on the HTML status page.
On the worker-side the directory can be found under :file:`docs`::

    from buildbot.plugins import steps

    f.addStep(steps.ShellCommand(command=["make", "docs"]))
    f.addStep(steps.DirectoryUpload(workersrc="docs",
                                    masterdest="~/public_html/docs",
                                    url="~buildbot/docs"))

The :bb:step:`DirectoryUpload` step will create all necessary directories and transfers empty directories, too.

The ``maxsize`` and ``blocksize`` parameters are the same as for :bb:step:`FileUpload`, although note that the size of the transferred data is implementation-dependent, and probably much larger than you expect due to the encoding used (currently tar).

The optional ``compress`` argument can be given as ``'gz'`` or ``'bz2'`` to compress the datastream.

.. note::

   The permissions on the copied files will be the same on the master as originally on the worker, see option `buildslave create-slave --umask` to change the default one.

.. bb:step:: MultipleFileUpload

Transferring Multiple Files At Once
+++++++++++++++++++++++++++++++++++

.. py:class:: buildbot.steps.transfer.MultipleFileUpload

In addition to the :bb:step:`FileUpload` and :bb:step:`DirectoryUpload` steps there is the :bb:step:`MultipleFileUpload` step for uploading a bunch of files (and directories) in a single :class:`BuildStep`.
The step supports all arguments that are supported by :bb:step:`FileUpload` and :bb:step:`DirectoryUpload`, but instead of a the single ``workersrc`` parameter it takes a (plural) ``workersrcs`` parameter.
This parameter should either be a list, or something that can be rendered as a list.::

    from buildbot.plugins import steps

    f.addStep(steps.ShellCommand(command=["make", "test"]))
    f.addStep(steps.ShellCommand(command=["make", "docs"]))
    f.addStep(steps.MultipleFileUpload(workersrcs=["docs", "test-results.html"],
                                       masterdest="~/public_html",
                                       url="~buildbot"))

The ``url=`` parameter, can be used to specify a link to be displayed in the HTML status of the step.

The way URLs are added to the step can be customized by extending the :bb:step:`MultipleFileUpload` class.
The `allUploadsDone` method is called after all files have been uploaded and sets the URL.
The `uploadDone` method is called once for each uploaded file and can be used to create file-specific links.

::

    import os

    from buildbot.plugins import steps

    class CustomFileUpload(steps.MultipleFileUpload):
        linkTypes = ('.html', '.txt')

        def linkFile(self, basename):
            name, ext = os.path.splitext(basename)
            return ext in self.linkTypes

        def uploadDone(self, result, source, masterdest):
            if self.url:
                basename = os.path.basename(source)
                if self.linkFile(basename):
                    self.addURL(self.url + '/' + basename, basename)

        def allUploadsDone(self, result, sources, masterdest):
            if self.url:
                notLinked = filter(lambda src: not self.linkFile(src), sources)
                numFiles = len(notLinked)
                if numFiles:
                    self.addURL(self.url, '... %d more' % numFiles)


.. bb:step:: StringDownload
.. bb:step:: JSONStringDownload
.. bb:step:: JSONPropertiesDownload

Transfering Strings
-------------------

.. py:class:: buildbot.steps.transfer.StringDownload
.. py:class:: buildbot.steps.transfer.JSONStringDownload
.. py:class:: buildbot.steps.transfer.JSONPropertiesDownload

Sometimes it is useful to transfer a calculated value from the master to the worker.
Instead of having to create a temporary file and then use FileDownload, you can use one of the string download steps.

::

    from buildbot.plugins import steps, util

    f.addStep(steps.StringDownload(util.Interpolate("%(src::branch)s-%(prop:got_revision)s\n"),
            workerdest="buildid.txt"))

:bb:step:`StringDownload` works just like :bb:step:`FileDownload` except it takes a single argument, ``s``, representing the string to download instead of a ``mastersrc`` argument.

::

    from buildbot.plugins import steps

    buildinfo = {
        'branch': Property('branch'),
        'got_revision': Property('got_revision')
    }
    f.addStep(steps.JSONStringDownload(buildinfo, workerdest="buildinfo.json"))

:bb:step:`JSONStringDownload` is similar, except it takes an ``o`` argument, which must be JSON serializable, and transfers that as a JSON-encoded string to the worker.

.. index:: Properties; JSONPropertiesDownload

::

    from buildbot.plugins import steps

    f.addStep(steps.JSONPropertiesDownload(workerdest="build-properties.json"))

:bb:step:`JSONPropertiesDownload` transfers a json-encoded string that represents a dictionary where properties maps to a dictionary of build property ``name`` to property ``value``; and ``sourcestamp`` represents the build's sourcestamp.

.. bb:step:: MasterShellCommand

Running Commands on the Master
------------------------------

.. py:class:: buildbot.steps.master.MasterShellCommand

Occasionally, it is useful to execute some task on the master, for example to create a directory, deploy a build result, or trigger some other centralized processing.
This is possible, in a limited fashion, with the :bb:step:`MasterShellCommand` step.

This step operates similarly to a regular :bb:step:`ShellCommand`, but executes on the master, instead of the worker.
To be clear, the enclosing :class:`Build` object must still have a worker object, just as for any other step -- only, in this step, the worker does not do anything.

In this example, the step renames a tarball based on the day of the week.

::

    from buildbot.plugins import steps

    f.addStep(steps.FileUpload(workersrc="widgetsoft.tar.gz",
                         masterdest="/var/buildoutputs/widgetsoft-new.tar.gz"))
    f.addStep(steps.MasterShellCommand(
        command="mv widgetsoft-new.tar.gz widgetsoft-`date +%a`.tar.gz",
        workdir="/var/buildoutputs"))

.. note::

   By default, this step passes a copy of the buildmaster's environment variables to the subprocess.
   To pass an explicit environment instead, add an ``env={..}`` argument.

Environment variables constructed using the ``env`` argument support expansion so that if you just want to prepend  :file:`/home/buildbot/bin` to the :envvar:`PATH` environment variable, you can do it by putting the value ``${PATH}`` at the end of the value like in the example below.
Variables that don't exist on the master will be replaced by ``""``.

::

    from buildbot.plugins import steps

    f.addStep(steps.MasterShellCommand(
                  command=["make", "www"],
                  env={'PATH': ["/home/buildbot/bin",
                                "${PATH}"]}))

Note that environment values must be strings (or lists that are turned into strings).
In particular, numeric properties such as ``buildnumber`` must be substituted using :ref:`Interpolate`.

``workdir``
   (optional) The directory from which the command will be ran.

``interruptSignal``
   (optional) Signal to use to end the process, if the step is interrupted.

.. bb:step:: LogRenderable

LogRenderable
+++++++++++++

.. py:class:: buildbot.steps.master.LogRenderable

This build step takes content which can be renderable and logs it in a pretty-printed format.
It can be useful for debugging properties during a build.

.. index:: Properties; from steps

.. _Setting-Properties:

Setting Properties
------------------

These steps set properties on the master based on information from the worker.

.. bb:step:: SetProperty

.. _Step-SetProperty:

SetProperty
+++++++++++

.. py:class:: buildbot.steps.master.SetProperty

SetProperty takes two arguments of ``property`` and ``value`` where the ``value`` is to be assigned to the ``property`` key.
It is usually called with the ``value`` argument being specifed as a :ref:`Interpolate` object which allows the value to be built from other property values::

    from buildbot.plugins import steps, util

    f.addStep(
        steps.SetProperty(
            property="SomeProperty",
            value=util.Interpolate("sch=%(prop:scheduler)s, worker=%(prop:workername)s")
        )
    )

.. bb:step:: SetPropertyFromCommand

SetPropertyFromCommand
++++++++++++++++++++++

.. py:class:: buildbot.steps.shell.SetPropertyFromCommand

This buildstep is similar to :bb:step:`ShellCommand`, except that it captures the output of the command into a property.
It is usually used like this::

    from buildbot.plugins import steps

    f.addStep(steps.SetPropertyFromCommand(command="uname -a", property="uname"))

This runs ``uname -a`` and captures its stdout, stripped of leading and trailing whitespace, in the property ``uname``.
To avoid stripping, add ``strip=False``.

The ``property`` argument can be specified as a  :ref:`Interpolate` object, allowing the property name to be built from other property values.

Passing ``includeStdout=False`` (default ``True``) stops capture from stdout.

Passing ``includeStderr=True`` (default ``False``) allows capture from stderr.

The more advanced usage allows you to specify a function to extract properties from the command output.
Here you can use regular expressions, string interpolation, or whatever you would like.
In this form, :func:`extract_fn` should be passed, and not :class:`Property`.
The :func:`extract_fn` function is called with three arguments: the exit status of the command, its standard output as a string, and its standard error as a string.
It should return a dictionary containing all new properties.

Note that passing in :func:`extract_fn` will set ``includeStderr`` to ``True``.

::

    def glob2list(rc, stdout, stderr):
        jpgs = [l.strip() for l in stdout.split('\n')]
        return {'jpgs': jpgs}

    f.addStep(SetPropertyFromCommand(command="ls -1 *.jpg", extract_fn=glob2list))

Note that any ordering relationship of the contents of stdout and stderr is lost.
For example, given::

    f.addStep(SetPropertyFromCommand(
        command="echo output1; echo error >&2; echo output2",
        extract_fn=my_extract))

Then ``my_extract`` will see ``stdout="output1\noutput2\n"`` and ``stderr="error\n"``.

Avoid using the ``extract_fn`` form of this step with commands that produce a great deal of output, as the output is buffered in memory until complete.

.. bb:step:: SetPropertiesFromEnv

.. py:class:: buildbot.steps.worker.SetPropertiesFromEnv

SetPropertiesFromEnv
++++++++++++++++++++

Buildbot workers (later than version 0.8.3) provide their environment variables to the master on connect.
These can be copied into Buildbot properties with the :bb:step:`SetPropertiesFromEnv` step.
Pass a variable or list of variables in the ``variables`` parameter, then simply use the values as properties in a later step.

Note that on Windows, environment variables are case-insensitive, but Buildbot property names are case sensitive.
The property will have exactly the variable name you specify, even if the underlying environment variable is capitalized differently.
If, for example, you use ``variables=['Tmp']``, the result will be a property named ``Tmp``, even though the environment variable is displayed as :envvar:`TMP` in the Windows GUI.

::

    from buildbot.plugins import steps, util

    f.addStep(steps.SetPropertiesFromEnv(variables=["SOME_JAVA_LIB_HOME", "JAVAC"]))
    f.addStep(steps.Compile(commands=[util.Interpolate("%(prop:JAVAC)s"),
                                      "-cp",
                                      util.Interpolate("%(prop:SOME_JAVA_LIB_HOME)s")]))

Note that this step requires that the Buildslave be at least version 0.8.3.
For previous versions, no environment variables are available (the worker environment will appear to be empty).

.. index:: Properties; triggering schedulers

.. bb:step:: Trigger

.. _Triggering-Schedulers:

Triggering Schedulers
---------------------

.. py:class:: buildbot.steps.trigger.Trigger

The counterpart to the :bb:Sched:`Triggerable` scheduler is the :bb:step:`Trigger` build step::

    from buildbot.plugins import steps

    f.addStep(steps.Trigger(schedulerNames=['build-prep'],
                            waitForFinish=True,
                            updateSourceStamp=True,
                            set_properties={ 'quick' : False }))

The SourceStamps to use for the triggered build are controlled by the arguments ``updateSourceStamp``, ``alwaysUseLatest``, and ``sourceStamps``.

Hyperlinks are added to the build detail web pages for each triggered build.

``schedulerNames``
    lists the :bb:sched:`Triggerable` schedulers that should be triggered when this step is executed.

    .. note::

        It is possible, but not advisable, to create a cycle where a build continually triggers itself, because the schedulers are specified by name.

``waitForFinish``
    If ``True``, the step will not finish until all of the builds from the triggered schedulers have finished.

    If ``False`` (the default) or not given, then the buildstep succeeds immediately after triggering the schedulers.

``updateSourceStamp``
    If ``True`` (the default), then step updates the source stamps given to the :bb:sched:`Triggerable` schedulers to include ``got_revision`` (the revision actually used in this build) as ``revision`` (the revision to use in the triggered builds).
    This is useful to ensure that all of the builds use exactly the same source stamps, even if other :class:`Change`\s have occurred while the build was running.

    If ``False`` (and neither of the other arguments are specified), then the exact same SourceStamps are used.

``alwaysUseLatest``
    If ``True``, then no SourceStamps are given, corresponding to using the latest revisions of the repositories specified in the Source steps.
    This is useful if the triggered builds use to a different source repository.

``sourceStamps``
    Accepts a list of dictionaries containing the keys ``branch``, ``revision``, ``repository``, ``project``, and optionally ``patch_level``, ``patch_body``, ``patch_subdir``, ``patch_author`` and ``patch_comment`` and creates the corresponding SourceStamps.
    If only one sourceStamp has to be specified then the argument ``sourceStamp`` can be used for a dictionary containing the keys mentioned above.
    The arguments ``updateSourceStamp``, ``alwaysUseLatest``, and ``sourceStamp`` can be specified using properties.

``set_properties``
    allows control of the properties that are passed to the triggered scheduler.
    The parameter takes a dictionary mapping property names to values.
    You may use :ref:`Interpolate` here to dynamically construct new property values.
    For the simple case of copying a property, this might look like::

        set_properties={"my_prop1" : Property("my_prop1")}

    .. note::

        The ``copy_properties`` parameter, given a list of properties to copy into the new build request, has been deprecated in favor of explicit use of ``set_properties``.

Dynamic Trigger
+++++++++++++++

Sometimes it is desirable to select which scheduler to trigger, and which properties to set dynamically, at the time of the build.
For this purpose, Trigger step supports a method that you can customize in order to override statically defined ``schedulernames``, and ``set_properties``.

.. py:method:: getSchedulersAndProperties()

    :returns: list of tuples (schedulerName, propertiesDict) optionally via deferred

    This methods returns a list of tuples describing what scheduler to trigger, with which properties.
    The properties should already be rendered (ie, concrete value, not objects wrapped by ``Interpolate`` or
    ``Property``). Since this function happens at build-time, the property values are available from the
    step and can be used to decide what schedulers or properties to use.

    With this method, you can also trigger the same scheduler multiple times with different set of properties.
    The sourcestamp configuration is however the same for each triggered build request.


RPM-Related Steps
-----------------

These steps work with RPMs and spec files.

.. bb:step:: RpmBuild

RpmBuild
++++++++

The :bb:step:`RpmBuild` step builds RPMs based on a spec file::

    from buildbot.plugins import steps

    f.addStep(steps.RpmBuild(specfile="proj.spec", dist='.el5'))

The step takes the following parameters

``specfile``
    The ``.spec`` file to build from

``topdir``
    Definition for ``_topdir``, defaulting to the workdir.

``builddir``
    Definition for ``_builddir``, defaulting to the workdir.

``rpmdir``
    Definition for ``_rpmdir``, defaulting to the workdir.

``sourcedir``
    Definition for ``_sourcedir``, defaulting to the workdir.

``srcrpmdir``
    Definition for ``_srcrpmdir``, defaulting to the workdir.

``dist``
    Distribution to build, used as the definition for ``_dist``.

``autoRelease``
    If true, use the auto-release mechanics.

``vcsRevision``
    If true, use the version-control revision mechanics.
    This uses the ``got_revision`` property to determine the revision and define ``_revision``.
    Note that this will not work with multi-codebase builds.

.. bb:step:: RpmLint

RpmLint
+++++++

The :bb:step:`RpmLint` step checks for common problems in RPM packages or spec files::

    from buildbot.plugins import steps

    f.addStep(steps.RpmLint())

The step takes the following parameters

``fileloc``
    The file or directory to check.
    In case of a directory, it is recursively searched for RPMs and spec files to check.

``config``
    Path to a rpmlint config file.
    This is passed as the user configuration file if present.

Mock Steps
++++++++++

Mock (http://fedoraproject.org/wiki/Projects/Mock) creates chroots and builds packages in them.
It populates the changeroot with a basic system and the packages listed as build requirement.
The type of chroot to build is specified with the ``root`` parameter.
To use mock your Buildbot user must be added to the ``mock`` group.

.. bb:step:: MockBuildSRPM

MockBuildSRPM Step
++++++++++++++++++

The :bb:step:`MockBuildSRPM` step builds a SourceRPM based on a spec file and optionally a source directory::

    from buildbot.plugins import steps

    f.addStep(steps.MockBuildSRPM(root='default', spec='mypkg.spec'))

The step takes the following parameters

``root``
    Use chroot configuration defined in ``/etc/mock/<root>.cfg``.

``resultdir``
    The directory where the logfiles and the SourceRPM are written to.

``spec``
    Build the SourceRPM from this spec file.

``sources``
    Path to the directory containing the sources, defaulting to ``.``.

.. bb:step:: MockRebuild

MockRebuild Step
++++++++++++++++

The :bb:step:`MockRebuild` step rebuilds a SourceRPM package::

    from buildbot.plugins import steps

    f.addStep(steps.MockRebuild(root='default', spec='mypkg-1.0-1.src.rpm'))

The step takes the following parameters

``root``
    Uses chroot configuration defined in ``/etc/mock/<root>.cfg``.

``resultdir``
    The directory where the logfiles and the SourceRPM are written to.

``srpm``
    The path to the SourceRPM to rebuild.

Debian Build Steps
------------------

.. bb:step:: DebPbuilder

DebPbuilder
+++++++++++

The :bb:step:`DebPbuilder` step builds Debian packages within a chroot built by :command:`pbuilder`.
It populates the chroot with a basic system and the packages listed as build requirement.
The type of the chroot to build is specified with the ``distribution``, ``distribution`` and ``mirror`` parameter.
To use pbuilder your Buildbot user must have the right to run :command:`pbuilder` as root using :command:`sudo`.

::

    from buildbot.plugins import steps

    f.addStep(steps.DebPbuilder())

The step takes the following parameters

``architecture``
    Architecture to build chroot for.

``distribution``
    Name, or nickname, of the distribution.
    Defaults to 'stable'.

``basetgz``
    Path of the basetgz to use for building.

``mirror``
    URL of the mirror used to download the packages from.

``extrapackages``
    List if packages to install in addition to the base system.

``keyring``
    Path to a gpg keyring to verify the downloaded packages.
    This is necessary if you build for a foreign distribution.

``components``
    Repos to activate for chroot building.

.. bb:step:: DebCowbuilder

DebCowbuilder
+++++++++++++

The :bb:step:`DebCowbuilder` step is a subclass of :bb:step:`DebPbuilder`, which use cowbuilder instead of pbuilder.

.. bb:step:: DebLintian

DebLintian
++++++++++

The :bb:step:`DebLintian` step checks a build .deb for bugs and policy violations.
The packages or changes file to test is specified in ``fileloc``

::

    from buildbot.plugins import steps, util

    f.addStep(steps.DebLintian(fileloc=util.Interpolate("%(prop:deb-changes)s")))

Miscellaneous BuildSteps
------------------------

A number of steps do not fall into any particular category.

.. bb:step:: HLint

HLint
+++++

The :bb:step:`HLint` step runs Twisted Lore, a lint-like checker over a set of ``.xhtml`` files.
Any deviations from recommended style is flagged and put in the output log.

The step looks at the list of changes in the build to determine which files to check - it does not check all files.
It specifically excludes any ``.xhtml`` files in the top-level ``sandbox/`` directory.

The step takes a single, optional, parameter: ``python``.
This specifies the Python executable to use to run Lore.

::

    from buildbot.plugins import steps

    f.addStep(steps.HLint())

MaxQ
++++

.. bb:step:: MaxQ

MaxQ (http://maxq.tigris.org/) is a web testing tool that allows you to record HTTP sessions and play them back.
The :bb:step:`MaxQ` step runs this framework.

::

    from buildbot.plugins import steps

    f.addStep(steps.MaxQ(testdir='tests/'))

The single argument, ``testdir``, specifies where the tests should be run.
This directory will be passed to the ``run_maxq.py`` command, and the results analyzed.

.. index:: HTTP Requests
.. bb:step:: HTTPStep
.. bb:step:: POST
.. bb:step:: GET
.. bb:step:: PUT
.. bb:step:: DELETE
.. bb:step:: HEAD
.. bb:step:: OPTIONS

HTTP Requests
+++++++++++++

Using the :bb:step:`HTTPStep` step, it is possible to perform HTTP requests in order to trigger another REST service about the progress of the build.

.. note::

   This step requires the `txrequests <https://pypi.python.org/pypi/txrequests>`_ and `requests <http://python-requests.org>`_ Python libraries.

The parameters are the following:

``url``
    (mandatory) The URL where to send the request

``method``
    The HTTP method to use (out of ``POST``, ``GET``, ``PUT``, ``DELETE``, ``HEAD`` or ``OPTIONS``), default to ``POST``.

``params``
    Dictionary of URL parameters to append to the URL.

``data``
    The body to attach the request.
    If a dictionary is provided, form-encoding will take place.

``headers``
    Dictionary of headers to send.

``other params``
    Any other keywords supported by the ``requests`` api can be passed to this step

    .. note::

        The entire Buildbot master process shares a single Requests ``Session`` object.
        This has the advantage of supporting connection re-use and other HTTP/1.1 features.
        However, it also means that any cookies or other state changed by one step will be visible to other steps, causing unexpected results.
        This behavior may change in future versions.

When the method is known in advance, class with the name of the method can also be used.
In this case, it is not necessary to specify the method.

Example::

    from buildbot.plugins import steps, util

    f.addStep(steps.POST('http://myRESTService.example.com/builds',
                         data = {
                            'builder': util.Property('buildername'),
                            'buildnumber': util.Property('buildnumber'),
                            'workername': util.Property('workername'),
                            'revision': util.Property('got_revision')
                         }))
