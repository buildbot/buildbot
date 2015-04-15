Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

* The ``MasterShellCommand`` step now correctly handles environment variables passed as list.
* The master now poll the database for pending tasks when running buildbot in multi-master mode.

Master
------

Features
~~~~~~~~

* The algorithm to match build requests to slaves has been rewritten in :bb:pull:`615`.
  The new algorithm automatically takes locks into account, and will not schedule a build only to have it wait on a lock.
  The algorithm also introduces a ``canStartBuild`` builder configuration option which can be used to prevent a build request being assigned to a slave.

* ``buildbot stop`` and ``buildbot restart`` now accept ``--clean`` to stop or restart the master cleanly (allowing all running builds to complete first).

* The :bb:status:`IRC` bot now supports clean shutdown and immediate shutdown by using the command 'shutdown'.
  To allow the command to function, you must provide `allowShutdown=True`.

* :bb:step:`CopyDirectory` has been added.

* :bb:sched:`BuildslaveChoiceParameter` has been added to provide a way to explicitly choose a buildslave
  for a given build.

* default.css now wraps preformatted text by default.

* Slaves can now be paused through the web status.

* The latent buildslave support is less buggy, thanks to :bb:pull:`646`.

* The ``treeStableTimer`` for ``AnyBranchScheduler`` now maintains separate timers for separate branches, codebases, projects, and repositories.

* :bb:step:`SVN` has a new option `preferLastChangedRev=True` to use the last changed revision for ``got_revision``

* The build request DB connector method :py:meth:`~buildbot.db.buildrequests.BuildRequestsConnectorComponent.getBuildRequests` can now filter by branch and repository.

* A new :bb:step:`SetProperty` step has been added in ``buildbot.steps.master`` which can set a property directly without accessing the slave.

* The new :bb:step:`LogRenderable` step logs Python objects, which can contain renderables, to the logfile.
  This is helpful for debugging property values during a build.

* 'buildbot try' now has an additional :option:`--property` option to set properties.
  Unlike the existing :option:`--properties` option, this new option supports setting
  only a single property and therefore allows commas to be included in the property
  name and value.

* The ``Git`` step has a new ``config`` option, which accepts a dict of git configuration options to pass to the low-level git commands.
  See :bb:step:`Git` for details.

* The ``TryScheduler`` now accepts an additional ``properties`` argument to its
  ``getAvailableBuilderNames`` method, which 'buildbot try' uses to send the properties
  it was passed (and are normally sent when starting a build).

* In :bb:step:`ShellCommand` ShellCommand now validates its arguments during config and will identify any invalid arguments before a build is started.

* The list of force schedulers in the web UI is now sorted by name.

* The :bb:step:`ShellCommand` step has a new parameter ``user``.
  When this is set, the slave will use 'sudo' to run the command as the given user.

* OpenStack-based Latent Buildslave support was added.
  See :bb:pull:`666`.

* Master-side support for P4 is available, and provides a great deal more flexibility than the old slave-side step.
  See :bb:pull:`596`.

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* The ``split_file`` function for :bb:chsrc:`SVNPoller` may now return a dictionary instead of a tuple.
  This allows it to add extra information about a change (such as ``project`` or ``repository``).

* The ``workdir`` build property has been renamed to ``builddir``.
  This change accurately reflects its content; the term "workdir" means something different.

* The ``Blocker`` step has been removed.

* Several polling ChangeSources are now documented to take a ``pollInterval`` argument, instead of ``pollinterval``.
  The old name is still supported.

* StatusReceivers' checkConfig method should no longer take an `errors` parameter.
  It should indicate errors by calling :py:func:`~buildbot.config.error`.

* Build steps now require that their name be a string.
  Previously, they would accept anything, but not behave appropriately.

* The web status no longer displays a potentially misleading message, indicating whether the build
  can be rebuilt exactly.

* The ``SetProperty`` step in ``buildbot.steps.shell`` has been renamed to :bb:step:`SetPropertyFromCommand`.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

* Added an optional build start callback to ``buildbot.status.status_gerrit.GerritStatusPush``

* An optional ``startCB`` callback to :bb:status:`GerritStatusPush` can be used
  to send a message back to the committer.
  See the linked documentation for details.

* bb:sched:`ChoiceStringParameter` has a new method ``getChoices`` that can be used to generate
  content dynamically for Force scheduler forms.

Slave
-----

Features
~~~~~~~~

* The fix for Twisted bug #5079 is now applied on the slave side, too.
  This fixes a perspective broker memory leak in older versions of Twisted.
  This fix was added on the master in Buildbot-0.8.4 (see :bb:bug:`1958`).

* The ``--nodaemon`` option to ``buildslave start`` now correctly prevents the slave from forking before running.

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the
git log itself::

   git log v0.8.7..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/release-notes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.8.7
    0.8.6
