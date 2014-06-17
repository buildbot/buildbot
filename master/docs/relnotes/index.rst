Release Notes for Buildbot |version|
====================================

Nine
----

..
    For the moment, release notes for the nine branch go here, for ease of merging.

..
    0.9.0 release notes should include a warning similar to that in 0.8.9 about new-style steps

* The sourcestamp DB connector now returns a ``patchid`` field.

* Buildbot's tests now require at least Mock-0.8.0.

* Buildbot no longer polls the database for jobs.  The
  ``db_poll_interval`` configuration parameter and the :bb:cfg:`db` key
  of the same name are deprecated and will be ignored.

* The interface for adding changes has changed.
  The new method is ``master.data.updates.addChange`` (implemented by :py:meth:`~buildbot.data.changes.ChangeResourceType.addChange`), although the old interface (``master.addChange``) will remain in place for a few versions.
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

* :py:mod:`buildbot.schedulers.forcesched` has the following changes:

  - The default configuration does not contain 4 AnyPropertyParameter anymore
  - configuring codebase is now mandatory, and the deprecated ``branch``,  ``repository``, ``project``, ``revision`` are not supported anymore in ForceScheduler
  - :py:meth:`buildbot.schedulers.forcesched.BaseParameter.updateFromKwargs` now takes a ``collector`` parameter used to collect all validation errors

* Logs are now stored as Unicode strings, and thus must be decoded properly from the bytestrings provided by shell commands.
  By default this encoding is assumed to be UTF-8, but the :bb:cfg:`logEncoding` parameter can be used to select an alternative.
  Steps and individual logfiles can also override the global default.

* The PB status service uses classes which have now been removed, and anyway is redundant to the REST API, so it has been removed.
  It has taken the following with it:
  * ``buildbot statuslog``
  * ``buildbot statusgui`` (the GTK client)
  * ``buildbot debugclient``

The ``PBListener`` status listener is now deprecated and does nothing.
Accordingly, there is no external access to status objects via Perspective Broker, aside from some compatibility code for the try scheduler.

The ``debugPassword`` configuration option is no longer needed and is thus deprecated.

* The undocumented and un-tested ``TinderboxMailNotifier``, designed to send emails suitable for the abandoned and insecure Tinderbox tool, has been removed.

* Buildslave is no longer available via :ref:`Interpolate` and the ``SetSlaveInfo`` buildstep has been removed.

* The ``buildbot.misc.SerializedInvocation`` class has been removed; use :py:func:`buildbot.util.debounce.method` instead.

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Features
~~~~~~~~

* Both the P4 source step and P4 change source support ticket-based authentication.

Fixes
~~~~~

* Buildbot is now compatible with SQLAlchemy 0.8 and higher, using the newly-released SQLAlchemy-Migrate.

* The :bb:step:`HTTPStep` step's requeset parameters are now renderable.

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~


Slave
-----

Features
~~~~~~~~

Fixes
~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the
git log itself:

.. code-block:: bash

   git log v0.8.9..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.8.9
    0.8.8
    0.8.7
    0.8.6
