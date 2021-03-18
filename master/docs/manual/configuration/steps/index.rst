.. _Build-Steps:

Build Steps
===========

.. toctree::
    :hidden:
    :maxdepth: 2

    common
    source_common
    source_bzr
    source_cvs
    source_darcs
    source_gerrit
    source_github
    source_gitlab
    source_git
    source_mercurial
    source_monotone
    source_p4
    source_repo
    source_svn
    gitcommit
    gittag
    gitpush
    git_diffinfo
    shell_command
    shell_sequence
    compile
    configure
    cmake
    visual_cxx
    cppcheck
    robocopy
    test
    treesize
    perl_module_test
    subunit_shell_command
    hlint
    maxq
    trigger
    build_epydoc
    pyflakes
    sphinx
    pylint
    trial
    remove_pycs
    http_step
    worker_filesystem
    file_transfer
    master_shell_command
    log_renderable
    assert
    set_property
    set_properties
    set_property_from_command
    set_properties_from_env
    rpm_build
    rpm_lint
    mock_build_srpm
    mock_rebuild
    deb_pbuilder
    deb_lintian

:class:`BuildStep`\s are usually specified in the buildmaster's configuration file, in a list that given to a :class:`BuildFactory`.
The :class:`BuildStep` instances in this list are used as templates to construct new independent copies for each build (so that state can be kept on the :class:`BuildStep` in one build without affecting a later build).
Each :class:`BuildFactory` can be created with a list of steps, or the factory can be created empty and then steps added to it using the :meth:`addStep` method:

.. code-block:: python

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
* finish with a status described by one of four values defined in :mod:`buildbot.process.results`: ``SUCCESS``, ``WARNINGS``, ``FAILURE``, ``SKIPPED``
* provide a list of short strings to describe the step

The rest of this section describes all the standard :class:`BuildStep` objects available for use in a :class:`Build`, and the parameters that can be used to control each.
A full list of build steps is available in the :bb:index:`step`.

.. contents::
    :depth: 2
    :local:

Build steps
-----------

The following build steps are available:

* :ref:`Buildstep-Common-Parameters`

* **Source checkout steps** - used to checkout the source code

    * :ref:`Step-Source-Common`
    * :ref:`Step-Bzr`
    * :ref:`Step-CVS`
    * :ref:`Step-Darcs`
    * :ref:`Step-Git`
    * :ref:`Step-Gerrit`
    * :ref:`Step-GitHub`
    * :ref:`Step-GitLab`
    * :ref:`Step-Mercurial`
    * :ref:`Step-Monotone`
    * :ref:`Step-P4`
    * :ref:`Step-Repo`
    * :ref:`Step-SVN`

* **Other source-related steps** - used to perform non-checkout source operations

    * :ref:`Step-GitCommit`
    * :ref:`Step-GitTag`
    * :ref:`Step-GitPush`
    * :ref:`Step-GitDiffInfo`

* **ShellCommand steps** - used to perform various shell-based operations

    * :ref:`Step-ShellCommand`
    * :ref:`Step-ShellSequence`
    * :ref:`Step-Compile`
    * :ref:`Step-Configure`
    * :ref:`Step-CMake`
    * :ref:`Step-VisualCxx` (``VC<...>``, ``VS<...>``, ``VCExpress9``, ``MsBuild<...``)
    * :ref:`Step-Cppcheck`
    * :ref:`Step-Robocopy`
    * :ref:`Step-Test`
    * :ref:`Step-TreeSize`
    * :ref:`Step-PerlModuleTest`
    * :ref:`Step-SubunitShellCommand`
    * :ref:`Step-HLint`
    * :ref:`Step-MaxQ`

* :ref:`Step-Trigger` - triggering other builds

* **Python build steps** - used to perform Python-related build operations

    * :ref:`Step-BuildEPYDoc`
    * :ref:`Step-PyFlakes`
    * :ref:`Step-Sphinx`
    * :ref:`Step-PyLint`
    * :ref:`Step-Trial`

* **Debian build steps** - used to build ``deb`` packages

    * :ref:`Step-DebPbuilder`, DebCowBuilder
    * :ref:`Step-DebLintian`

* **RPM build steps** - used to build ``rpm`` packages

    * :ref:`Step-RpmBuild`
    * :ref:`Step-RpmLint`
    * :ref:`Step-MockBuildSRPM`
    * :ref:`Step-MockRebuild`

* :ref:`Step-FileTransfer` - used to perform file transfer operations

    * FileUpload
    * FileDownload
    * DirectoryUpload
    * MultipleFileUpload
    * StringDownload
    * JSONStringDownload
    * JSONPropertiesDownload

* :ref:`Step-HTTPStep` - used to perform HTTP requests

    * HTTPStep
    * POST
    * GET
    * PUT
    * DELETE
    * HEAD
    * OPTIONS

* :ref:`Worker-Filesystem-Steps` - used to perform filesystem operations on the worker

    * FileExists
    * CopyDirectory
    * RemoveDirectory
    * MakeDirectory

* **Master steps** - used to perform operations on the build master

    * :ref:`Step-MasterShellCommand`
    * :ref:`Step-SetProperty`
    * :ref:`Step-SetProperties`
    * :ref:`Step-SetPropertyFromCommand`
    * :ref:`Step-SetPropertiesFromEnv`
    * :ref:`Step-LogRenderable` - used to log a renderable property for debugging
    * :ref:`Step-Assert` - used to terminate build depending on condition
