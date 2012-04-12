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

* Buildbot master now requires at least Python-2.5 and Twisted-9.0.0.

* Buildbot master requires ``python-dateutil`` version 1.5 to support the
  Nightly scheduler.

* The configurable callable build.workdir has changed his parameterlist. Instead
  of a single sourcestamp a list of sourcestamps is passed. Each sourcestamp in 
  the list has a different :ref:`codebase<Attr-Codebase>`

* BK support has been removed in this release - see :bb:bug:`2198`.

* The undocumented renderable ``_ComputeRepositoryURL`` is no longer imported to
  :py:mod:`buildbot.steps.source`. It is still available at
  :py:mod:`buildbot.steps.source.oldsource`.

* ``IProperties.render`` now returns a deferred, so any code rendering properties
  by hand will need to take this into account.

* ``baseURL`` has been removed in :bb:step:`SVN` to use just ``repourl`` - see
  :bb:bug:`2066`. Branch info should be provided with ``Interpolate``.

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

* ``IRenderable.getRenderingFor`` can now return a deferred.

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
