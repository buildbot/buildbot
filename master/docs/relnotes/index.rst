Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

This version represents a refactoring of Buildbot into a consistent, well-defined application composed of loosely coupled components.
The components are linked by a common database backend and a messaging system.
This allows components to be distributed across multiple build masters.
It also allows the rendering of complex web status views to be performed in the browser, rather than on the buildmasters.

The branch looks forward to committing to long-term API compatibility, but does not reach that goal.
The Buildbot-0.9.x series of releases will give the new APIs time to "settle in" before we commit to them.
Commitment will wait for Buildbot-1.0.0 (as per http://semver.org).
Once Buildbot reaches version 1.0.0, upgrades will become much easier for users.

To encourage contributions from a wider field of developers, the web application is designed to look like a normal AngularJS application.
Developers familiar with AngularJS, but not with Python, should be able to start hacking on the web application quickly.
The web application is "pluggable", so users who develop their own status displays can package those separately from Buildbot itself.

Other goals:

 * An approachable HTTP REST API, used by the web application but available for any other purpose.
 * A high degree of coverage by reliable, easily-modified tests.
 * "Interlocking" tests to guarantee compatibility.
   For example, the real and fake DB implementations must both pass the same suite of tests.
   Then no unseen difference between the fake and real implementations can mask errors that will occur in production.

Requirements
~~~~~~~~~~~~

The buildbot-master package requires Python 2.6 -- Python 2.5 is no longer supported.
The buildbot-slave package continues to support Python 2.4 through Python 2.7.

No additional software or systems, aside from some minor Python packages, are required.

But the devil is in the details:

 * If you want to do web *development*, or *build* the buildbot-www package, you'll need Node.
   It's an Angular app, and that's how such apps are developed.
   We've taken pains to not make either a requirement for users - you can simply 'pip install' buildbot-www and be on your way.
   This is the case even if you're hacking on the Python side of Buildbot.
 * For a single master, nothing else is required.
 * If you want multiple masters, you'll need an external message broker of some sort.
   Messaging is based on `Kombu <http://kombu.readthedocs.org/>`_, and supports the backends that Kombu supports.

Minor Python Packages
.....................

* Buildbot requires at least Twisted-11.0.0.

Features
~~~~~~~~

..
    TODO: talk about big new Nine features

* Both the P4 source step and P4 change source support ticket-based authentication.

Fixes
~~~~~

* Buildbot is now compatible with SQLAlchemy 0.8 and higher, using the newly-released SQLAlchemy-Migrate.

* The :bb:step:`HTTPStep` step's requeset parameters are now renderable.

* With Git(), force the updating submodules to ensure local changes by the
  build are overwitten. This both ensures more consistent builds and avoids
  errors when updating submodules.

* Buildbot is now compatible with Gerrit v2.6 and higher.

  To make this happen, the return result of ``reviewCB`` and ``summaryCB``
  callback has changed from

  .. code-block:: python

     (message, verified, review)

  to

  .. code-block:: python

     {'message': message,
      'labels': {'label-name': value,
                ...
                }
     }

  The implications are:

  * there are some differences in behaviour: only those labels that were
    provided will be updated
  * Gerrit server must be able to provide a version, if it can't the
    :bb:status:`GerritStatusPush` will not work

  .. note::

     If you have an old style ``reviewCB`` and/or ``summaryCB`` implemented,
     these will still work, however there could be more labels updated than
     anticipated.

  More detailed information is available in :bb:status:`GerritStatusPush`
  section.

* :bb:chsrc:`P4Poller`'s ``server_tz`` parameter now works correctly.

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

..
    TODO: "executive summary" of changes: new-style steps, status classes missing, etc.

..
    TODO: 0.9.0 release notes should include a warning similar to that in 0.8.9 about new-style steps

WebStatus
.........

The old, clunky WebStatus has been removed.
You will like the new interface!
RIP WebStatus, you were a good friend.

If you have code like this in your configuration (and you probably do!)

.. code-block:: python

    from buildbot.status import html
    c['status'].append(html.WebStatus(http_port=8010, allowForce=True)

remove it and replace it with :bb:cfg:`www configuration <www>`.

Requirements
............

* Buildbot's tests now require at least Mock-0.8.0.

* SQLAlchemy-Migrate-0.6.1 is no longer supported.

* Bulider names are now restricted to unicode strings or ASCII bytestrings.
  Encoded bytestrings are not accepted.

Changes and Removals
....................

* Buildslave names must now be 50-character :ref:`identifier <type-identifier>`.
  Note that this disallows some common characters in bulidslave names, including spaces, ``/``, and ``.``.

* Builders now have "tags" instead of a category.
  Builders can have multiple tags, allowing more flexible builder displays.

* :bb:sched:`ForceScheduler` has the following changes:

  - The default configuration no longer contains four ``AnyPropertyParameter`` instances.
  - Configuring ``codebases`` is now mandatory, and the deprecated ``branch``,  ``repository``, ``project``, ``revision`` are not supported anymore in ForceScheduler
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

* Buildslave info is no longer available via :ref:`Interpolate` and the ``SetSlaveInfo`` buildstep has been removed.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

* The sourcestamp DB connector now returns a ``patchid`` field.

* Buildbot no longer polls the database for jobs.
  The ``db_poll_interval`` configuration parameter and the :bb:cfg:`db` key of the same name are deprecated and will be ignored.

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

* The ``buildbot.misc.SerializedInvocation`` class has been removed; use :py:func:`buildbot.util.debounce.method` instead.

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
