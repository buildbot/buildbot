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

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the
git log itself::

   git log v0.8.7..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.8.7
    0.8.6
