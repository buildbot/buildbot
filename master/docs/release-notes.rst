Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* The configurable callable build.workdir has changed his parameterlist. Instead
  of a single sourcestamp a list of sourcestamps is passed. Each sourcestamp in 
  the list has a different :ref:`codebase<Attr-Codebase>`

* BK support has been removed in this release - see :bb:bug:`2198`.

* The undocumented renderable _ComputeRepositoryURL is no longer imported to
  py:module::`buildbot.steps.source`. It is still available at
  py:module::`buildbot.steps.source.oldsource`.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Features
~~~~~~~~

Slave
-----

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* BK support has been removed in this release - see :bb:bug:`2198`.

Features
~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the
git log itself:

   git log v0.8.6..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the
:bb:src:`master/docs/release-notes/` directory of the source tree, or in the archived
documentation for those versions at http://buildbot.net/buildbot/docs.
