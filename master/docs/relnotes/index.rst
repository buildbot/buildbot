Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

..
    NOTE: When releasing 0.9.0, combine these notes with those from 0.9.0b{1,2,3,4,5}
    into one single set of notes.  Also, link prominently to the migration guide.

The following are the release notes for Buildbot |version|

See :ref:`Upgrading to Nine` for a guide to upgrading from 0.8.x to 0.9.x

Master
------

Features
~~~~~~~~

Fixes
~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Note that Buildbot is not yet compatible with MySQL-5.7.
  See :bug:`3421` for status and to help out.

* The ``buildbot`` Python dist now (finally) requires SQLAlchemy-0.8.0 or later and SQLAlchemy-Migrate-0.9.0 or later.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Worker
------

Features
~~~~~~~~

Fixes
~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the git log itself:

.. code-block:: bash

   git log v0.9.0b5..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

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
