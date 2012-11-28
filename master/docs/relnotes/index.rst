Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

* The ``MasterShellCommand`` step now correctly handles environment variables passed as list.

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
