Release Notes for Buildbot |version|
====================================

Nine
----

..
    For the moment, release notes for the nine branch go here, for ease of merging.

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

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Features
~~~~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

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
