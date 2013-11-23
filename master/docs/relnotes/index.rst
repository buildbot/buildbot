Release Notes for Buildbot |version|
====================================

Nine
----

..
    For the moment, release notes for the nine branch go here, for ease of merging.

* The sourcestamp DB connector now returns a ``patchid`` field.

* Buildbot's tests now require at least Mock-0.8.0.

* Buildbot no longer polls the database for jobs.  The
  ``db_poll_interval`` configuration parameter and the :bb:cfg:`db` key
  of the same name are deprecated and will be ignored.

* The interface for adding changes has changed.
  The new method is ``master.data.updates.addChanges`` (implemented by :py:meth:`~buildbot.data.changes.ChangeResourceType.addChange`), although the old interface (``master.addChange``) will remain in place for a few versions.
  The new method:

  * returns a change ID, not a Change instance;

  * takes its ``when_timestamp`` argument as epoch time (UNIX time), not a datetime instance; and

  * does not accept the deprecated parameters ``who``, ``isdir``, ``is_dir``, and ``when``.

  * requires that all strings be unicode, not bytestrings.

  Please adjust any custom change sources accordingly.

* A new build status, CANCELLED, has been added.
  It is used when a step or build is deliberately cancelled by a user.

* This upgrade will delete all rows from the ``buildrequest_claims`` table.
  If you are using this table for analytical purposes outside of Buildbot, please back up its contents before the upgrade, and restore it afterward, translating object IDs to scheduler IDs if necessary.
  This translation would be very slow and is not required for most users, so it is not done automatically.

* All of the schedulers DB API methods now accept a schedulerid, rather than an objectid.
  If you have custom code using these methods, check your code and make the necessary adjustments.

* The ``addBuildsetForSourceStamp`` method has become ``addBuildsetForSourceStamps``, and its signature has changed.
  The ``addBuildsetForSourceStampSetDetails`` method has become ``addBuildsetForSourceStampsWithDefaults``, and its signature has changed.
  The ``addBuildsetForSourceStampDetails`` method has been removed.
  The ``addBuildsetForLatest`` method has been removed.
  It is equivalent to ``addBuildsetForSourceStampDetails`` with ``sourcestamps=None``.
  These methods are not yet documented, and their interface is not stable.
  Consult the source code for details on the changes.

* The triggerable schedulers` ``trigger`` method now requires a list of sourcestamps, rather than a dictionary.

* The :py:class:`~buildbot.sourcestamp.SourceStamp` class is no longer used.
  It remains in the codebase to support loading data from pickles on upgrade, but should not be used in running code.

* The :py:class:`~buildbot.process.buildrequest.BuildRequest` class no longer has full ``source`` or ``sources`` attributes.
  Use the data API to get this information (which is associated with the buildset, not the build request) instead.

* The undocumented ``BuilderControl`` method ``submitBuildRequest`` has been removed.

* The debug client no longer supports requesting builds (the ``requestBuild`` method has been removed).
  If you have been using this method in production, consider instead creating a new change source, using the :bb:sched:`ForceScheduler`, or using one of the try schedulers.

* SQLAlchemy-Migrate-0.6.1 is no longer supported.

* Bulider names are now restricted to unicode strings or ASCII bytestrings.
  Encoded bytestrings are not accepted.

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Features
~~~~~~~~

* The attributes ``description``, ``descriptionDone`` and ``descriptionSuffix`` have been moved from :py:class:`ShellCommand` to its superclass :py:class:`BuildStep` so that any class that inherits from :py:class:`BuildStep` can provide a suitable description of itself.

* A new :py:class:`FlattenList` Renderable has been added which can flatten nested lists.

* Builder configurations can now include a ``description``, which will appear in the web UI to help humans figure out what the builder does.

* The web UI now supports a PNG Status Resource that can be accessed publicly from for example README.md files or wikis or whatever other resource.
  This view produces an image in PNG format with information about the last build for the given builder name or whatever other build number if is passed as an argument to the view.

* The web hooks now include support for Bitbucket.

* The web hooks now include support for GitLab.

* The 'Rebuild' button on the web pages for builds features a dropdown to choose whether to
  rebuild from exact revisions or from the same sourcestamps (ie, update branch references)

* The ``start``, ``restart``, and ``reconfig`` commands will now wait for longer than 10 seconds as long as the master continues producing log lines indicating that the configuration is progressing.

* Git source checkout step now supports reference repositories.

* P4 source step now supports more advanced options.

* The ``comments`` field of changes is no longer limited to 1024 characters on MySQL and Postgres.  See :bb:bug:`2367` and :bb:pull:`736`.

* The WebStatus builder page can now filter pending/current/finished builds by property parameters of the form ``?property.<name>=<value>``.

* The Console view now supports codebases.

* Build status can be sent to GitHub.
  Depends on txgithub package.
  See :bb:status:`GitHubStatus` and `GitHub Commit Status <https://github.com/blog/1227-commit-status-api>`_.

* The web UI for Builders has been updated:
   * shows the build 'reason' and 'interested users'
   * shows sourcestamp information for builders that use multiple codebases (instead of the generic
     "multiple rev" placeholder that was shown before).

* Each Scheduler type can now take a 'reason' argument to customize the reason it uses for triggered builds.

* Added zsh and bash tab-completions support for 'buildbot' command.

* An example of a declarative configuration is included in :bb:src:`master/contrib/SimpleConfig.py`, with copious comments.

* A new argument ``createAbsoluteSourceStamps`` has been added to ``SingleBranchScheduler`` for use with multiple codebases.

* The WebStatus Authorization support now includes a ``view`` action which can be used to restrict read-only access to the Buildbot instance.

* Information about the buildslaves (admin, host, etc) is now persisted in the database and available even if
  the slave is not connected.

* Master side source checkout steps now support patches

* The master-side SVN step now supports authentication, fixing :bb:bug:`2463`.

* Master side source checkout steps now support retry option

* The SVN step now obfuscates the password in status logs, fixing :bb:bug:`2468`.

* Gerrit integration with Git Source step on master side.

* A new :bb:step:`Robocopy` step is available for Windows builders.

* The :bb:chsrc:`P4Source` changesource now supports Perforce servers in a different timezone than the buildbot master.

* Revision links for commits on SouceForge (Allura) are now automatically generated.

* The WebStatus now interprets ANSI color codes in stdio output.

* Master-side source steps now respond to the "stop build" button (:bb:bug:`2356`).

* The web hooks now include support for Gitorious.

* It is now possible to select categories to show in the waterfall help

* The web status now has options to cancel some or all pending builds.

* The web status correctly interprets ANSI color escape codes.

* Added new config option ``protocols`` which allows to configure multiple protocols on single master.

* New source step :bb:step:`Darcs` added on master side.

* RemoteShellCommands can be killed by SIGTERM with the sigtermTime parameter before resorting to SIGKILL (:bb:bug: `751`).
  If the slave's version is less than 0.8.9, the slave will kill the process with SIGKILL regardless of whether sigtermTime
  is supplied.

* The Git step now uses the `git clean` option `-f` twice, to also remove untracked directories managed by another git repository.
  See :bb:bug:`2560`.

* The slave-side source steps are deprecated in this version of Buildbot, and master-side support will be removed in a future version.
  Please convert any use of slave-side steps (imported directly from ``buildbot.steps.source``, rather than from a specific module like ``buildbot.steps.source.svn``) to use master-side steps.
  TODO: update version in deprecation warning.

* New source step :bb:step:`Monotone` added on master side.

* Introduce an alternative way to deploy Buildbot and try the pyflakes tutorial
  using :ref:`Docker <first-run-docker-label>`.

* The :bb:step:`HTTPStep` step can make arbitrary HTTP requests from the master, allowing communication with external APIs.
  This new feature requires the optional ``txrequests`` and ``requests`` Python packages.
  
* :bb:step:`CVS` source step now checks for "sticky dates" from a previous checkout before updating an existing source directory.

* The IRC bot of :bb:status:`IRC` will, unless useRevisions is set, shorten
  long lists of revisions printed when a build starts; it will only show two,
  and the number of additional revisions included in the build.

* A new argument ``createAbsoluteSourceStamps`` has been added to :bb:sched:`Nightly` for use with multiple codebases.

* The ``branch`` and ``codebase`` arguments to the :bb:step:`Git` step are now renderable.

* reconf option for GNUAutotools to run autoreconf before ./configure

Fixes
~~~~~

* Fixed an issue where the Git and CVS source steps silently changed the ``workdir`` to ``'build'`` when the 'copy' method is used.

* The Git step now uses the `git submodule update` option `--init` when updating the submodules of an existing repository,
  so that it will receive any newly added submodules.

* The web status no longer relies on the current working directory, which is not set correctly by some initscripts, to find the ``templates/`` directory (:bb:bug:`2586`).

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``slavePortnum`` option deprecated, please use ``c['protocols']['pb']['port']`` to set up PB port

* The buildbot.process.mtrlogobserver module have been renamed to buildbot.steps.mtrlogobserver.

* The buildmaster now requires at least Twisted-11.0.0.

* The former ``buildbot.process.buildstep.RemoteCommand`` class and its subclasses are now in :py:mod`buildbot.process.remotecommand`, although imports from the previous path will continue to work.
  Similarly, the former ``buildbot.process.buildstep.LogObserver`` class and its subclasses are now in :py:mod`buildbot.process.logobserver`, although imports from the previous path will continue to work.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Slave
-----

Features
~~~~~~~~

* Added zsh and bash tab-completions support for 'buildslave' command.
* RemoteShellCommands accept the new sigtermTime parameter from master. This allows processes to be killed by SIGTERM
  before resorting to SIGKILL (:bb:bug: `751`)

Fixes
~~~~~

* Fixed an issue when buildstep stop() was raising an exception incorrectly if timeout for
  buildstep wasn't set or was None (see :bb:pull:`753`) thus keeping watched logfiles open
  (this prevented their removal on Windows in subsequent builds).

* Fixed a bug in P4 source step where the ``timeout`` parameter was ignored.

* Fixed a bug in P4 source step where using a custom view-spec could result in failed syncs
  due to incorrectly generated command-lines.

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the
git log itself:

.. code-block:: bash

   git log v0.8.8..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.8.8
    0.8.7
    0.8.6
