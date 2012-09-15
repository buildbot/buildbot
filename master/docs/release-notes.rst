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

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Features
~~~~~~~~

* The :bb:status:`IRC` bot now supports clean shutdown and immediate shutdown by using the command 'shutdown'.
  To allow the command to function, you must provide `allowShutdown=True`.

* :bb:step:`CopyDirectory` has been added.

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* The ``split_file`` function for :bb:chsrc:`SVNPoller` may now return a dictionary instead of a tuple.
  This allows it to add extra information about a change (such as ``project`` or ``repository``).
* The ``workdir`` property has been renamed to ``builddir``.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

* Added an optional build start callback to ``buildbot.status.status_gerrit.GerritStatusPush``

* An optional ``startCB`` callback to :bb:status:`GerritStatusPush` can be used
  to send a message back to the committer.
  See the linked documentation for details.

Slave
-----

Features
~~~~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the
git log itself:

   git log v0.8.7..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/release-notes/` directory of the source tree.
Starting with version 0.8.6, they are also available under the appropriate version at http://buildbot.net/buildbot/docs.
