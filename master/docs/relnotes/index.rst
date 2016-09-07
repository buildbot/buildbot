Release Notes for Buildbot ``|version|``
========================================

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

The following are the release notes for Buildbot ``|version|``.

See :ref:`Upgrading to Nine` for a guide to upgrading from 0.8.x to 0.9.x

Master
------

* Add support for hyper.sh via :class:`HyperLatentWorker`
  Hyper_ is a CaaS solution for hosting docker container in the cloud, billed to the second.
  It forms a very cost efficient solution to run your CI in the cloud.

.. _Hyper: https://hyper.sh

* add tool to send usage data to buildbot.net :bb:cfg:`buildbotNetUsageData`

Features
~~~~~~~~

* The :bb:step:`Trigger` step now supports ``unimportantSchedulerNames``

* add a UI button to allow to cancel the whole queue for a builder

* Buildbot log viewer now support 256 colors ANSI codes

Fixes
~~~~~

* fix the UI to allow to cancel a buildrequest (:bug:`3582`)

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Features
~~~~~~~~

Fixes
~~~~~


Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Buildslave
----------

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Worker
------

Fixes
~~~~~

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Details
-------

For a more detailed description of the changes made in this version, see the git log itself:

.. code-block:: bash

   git log v0.9.0rc1..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.9.0
    0.9.0rc2
    0.9.0rc1
    0.9.0b9
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
