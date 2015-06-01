Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot |version|.

Master
------

Features
~~~~~~~~

* :bb:step:`Git` supports an "origin" option to give a name to the remote repo.

* two new general steps are added to handle related builds -- :bb:step:`CancelRelatedBuilds` and :bb:step:`StopRelatedBuilds` -- as well as Gerrit specific ones -- :bb:step:`CancelGerritRelatedBuilds` and :bb:step:`StopGerritRelatedBuilds`.
  More information in :ref:`the manual <handle-related-builds>`.

Fixes
~~~~~

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

For a more detailed description of the changes made in this version, see the git log itself:

.. code-block:: bash

   git log v0.8.11..eight

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :bb:src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.8.12
    0.8.10
    0.8.9
    0.8.8
    0.8.7
    0.8.6
