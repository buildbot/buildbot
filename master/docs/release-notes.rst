Release Notes
=============

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``buildbot start`` no longer invokes make if a ``Makefile.buildbot`` exists.
  If you are using this functionality, consider invoking make directly.

Features
~~~~~~~~

* Buildbot can now take advantage of authentication done by a front-end web
  server: https://github.com/buildbot/buildbot/pull/266

Slave
-----

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Features
~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the
git log itself::

   https://github.com/buildbot/buildbot/compare/buildbot-0.8.4...buildbot-0.8.5

Older Versions
--------------

Release notes for older versions of Buildbot are available in the
``master/docs/release-notes/`` directory of the source tree, or in the archived
documentation for those versions at http://buildbot.net/buildbot/docs.
