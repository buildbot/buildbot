Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

    If you can:

       please point to the bug using syntax: (:bug:`NNN`)
       please point to classes using syntax: :py:class:`~buildbot.reporters.http.HttpStatusBase`

..
    NOTE: When releasing 0.9.0, combine these notes with those from 0.9.0b*
    into one single set of notes.  Also, link prominently to the migration guide.

The following are the release notes for Buildbot |version|

See :ref:`Upgrading to Nine` for a guide to upgrading from 0.8.x to 0.9.x

Master
------

Features
~~~~~~~~

Fixes
~~~~~


Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Features
~~~~~~~~

Fixes
~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* GitLabStatus was present in buildbot 0.8.12 release, but is no more in 0.9.0 (:bug:`3286`).
  Gitlab community should be able to easily port it using :py:class:`~buildbot.reporters.http.HttpStatusBase`


* Web server does not provide /png and /redirect anymore (:bug:`3357`).
  This functionality is used to implement build status images.
  This should be easy to implement if you need it.
  One could port the old image generation code, or implement a redirection to http://shields.io/.


Details
-------

For a more detailed description of the changes made in this version, see the git log itself:

.. code-block:: bash

   git log v0.9.0b8..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.9.0b8
    0.9.0b7
    0.9.0b6
    0.9.0b5
    0.9.0b4
    0.9.0b3
    0.9.0b2
    0.9.0b1
    0.8.12
    0.8.10
    0.8.9
    0.8.8
    0.8.7
    0.8.6

Note that Buildbot-0.8.11 was never released.
