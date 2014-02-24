Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Features
~~~~~~~~

* The following optional parameters have been added to :py:class:`EC2LatentBuildSlave`
   * Boolean parameter ``spot_instance``, default False, creates a spot instance.
   * Float parameter ``max_spot_price`` defines the maximum bid for a spot instance.
   * List parameter ``volumes``, takes a list of (volume_id, mount_point) tuples.
   * String parameter ``placement`` is appended to the ``region`` parameter, e.g. ``region='us-west-2', placement='b'``
     will result in the spot request being placed in us-west-2b.
   * Float parameter ``price_multiplier`` specifies the percentage bid above the 24-hour average spot price.
   * Dict parameter ``tags`` specifies AWS tags as key/value pairs to be applied to new instances.
  
  With spot_instance=True, an EC2LatentBuildSlave will attempt to create a spot instance with the provided spot
  price, placement, and so on.

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

* The WebStatus :ref:`Authorization` support now includes a ``view`` action which can be used to restrict read-only access to the Buildbot instance.

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

* A new :bb:step:`MultipleFileUpload` step was added to allow uploading several files (or directories) in a single step.

* The HGPoller and GitPoller now split filenames on newlines, rather than whitespace, so files containing whitespace are handled correctly.

* Add 'pollAtLaunch' flag for polling change sources. This allows a poller to poll immediately on launch and get changes that occurred while it was down.

* Systemd unit files for Buildbot are available in the :bb:src:`contrib/` directory.

Fixes
~~~~~

* Fixed an issue where the Git and CVS source steps silently changed the ``workdir`` to ``'build'`` when the 'copy' method is used.

* The Git step now uses the `git submodule update` option `--init` when updating the submodules of an existing repository,
  so that it will receive any newly added submodules.

* The web status no longer relies on the current working directory, which is not set correctly by some initscripts, to find the ``templates/`` directory (:bb:bug:`2586`).

* The source steps now correctly interpolate properties in ``env``.

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``slavePortnum`` option deprecated, please use ``c['protocols']['pb']['port']`` to set up PB port

* The buildbot.process.mtrlogobserver module have been renamed to buildbot.steps.mtrlogobserver.

* The buildmaster now requires at least Twisted-11.0.0.

* The ``hgbuildbot`` Mercurial hook has been moved to ``contrib/``, and does not work with recent versions of Mercurial and Twisted.
  The runtimes for these two tools are incompatible, yet ``hgbuildbot`` attempts to run both in the same Python interpreter.
  Mayhem ensues.

* The try scheduler's ``--connect=ssh`` method no longer supports waiting for results (``--wait``).

* The former ``buildbot.process.buildstep.RemoteCommand`` class and its subclasses are now in :py:mod`buildbot.process.remotecommand`, although imports from the previous path will continue to work.
  Similarly, the former ``buildbot.process.buildstep.LogObserver`` class and its subclasses are now in :py:mod`buildbot.process.logobserver`, although imports from the previous path will continue to work.

* The undocumented BuildStep method ``checkDisconnect`` is deprecated and now does nothing as the handling of disconnects is now handled in the ``failed`` method.
  Any custom steps adding this method as a callback or errback should no longer do so.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Slave
-----

Features
~~~~~~~~

* Added zsh and bash tab-completions support for 'buildslave' command.
* RemoteShellCommands accept the new sigtermTime parameter from master. This allows processes to be killed by SIGTERM
  before resorting to SIGKILL (:bb:bug: `751`)
* Added spot instance support to EC2LatentBuildSlave.

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
