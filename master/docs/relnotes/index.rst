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

* Both the P4 source step and P4 change source support ticket-based authentication.

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

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Slave
-----

Features
~~~~~~~~

* Added zsh and bash tab-completions support for 'buildslave' command.

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
