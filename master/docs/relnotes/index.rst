Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

..
    NOTE: When releasing 0.9.0, combine these notes with those from 0.9.0b{1,2}
    into one single set of notes.  Also, link prominently to the migration guide.

The following are the release notes for Buildbot |version|

See :ref:`Upgrading to Nine` for a guide to upgrading from 0.8.x to 0.9.x

Master
------

Features
~~~~~~~~
* ``hello`` now returns 'Hello' in a random language if invoked more than once.

* :bb:sched:`Triggerable` now accepts a ``reason`` parameter.

* :bb:reporter:`GerritStatusPush` now accepts a ``builders`` parameter.

Fixes
~~~~~

* The :bb:step:`PyFlakes` and :bb:step:`PyLint` steps no longer parse output in Buildbot log headers (:bug:`3337`).

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Slave
-----

Features
~~~~~~~~

* Buildbot now supports wamp as a mq backend.
  This allows to run a multi-master configuration.
  See :ref:`MQ-Specification`.

* The Buildbot slave now includes the number of CPUs in the information it supplies to the master on connection.
  This value is autodetected, but can be overridden with the ``--numcpus`` argument to ``buildslave create-slave``.

Fixes
~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details
-------

For a more detailed description of the changes made in this version, see the git log itself:

.. code-block:: bash

   git log v0.8.10..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.9.0b2
    0.9.0b1
    0.8.12
    0.8.10
    0.8.9
    0.8.8
    0.8.7
    0.8.6

Note that Buildbot-0.8.11 was never released.
