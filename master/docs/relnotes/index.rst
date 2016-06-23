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

Features
~~~~~~~~

* new :bb:reporter:`HipchatStatusPush` to report build results to Hipchat.
* new steps for Visual Studio 2015 (VS2015, VC14, and MsBuild14).

* The :bb:step:`P4` step now obfuscates the password in status logs.

* Added support for specifying the depth of a shallow clone in :bb:step:`Git`.

* :bb:worker:`OpenStackLatentWorker` now uses a single novaclient instance to not require re-authentication when starting or stopping instances.

Fixes
~~~~~

* :bb:reporter:`GerritStatusPush` now includes build properties in the ``startCB`` and ``reviewCB`` functions. ``startCB`` now must return a dictionary.
* Fix TypeError exception with :py:class:`~buildbot.changes.HgPoller` if ``usetimestamps=False`` is used (:bug:`3562`)

* sqlite access is serialized in order to improve stability (:bug:`3565`)

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Features
~~~~~~~~

Fixes
~~~~~


Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Support for python 2.6 was dropped from the master.

* ``public_html`` directory is not created anymore in ``buildbot create-master`` (it's not used for some time already).
  Documentation was updated with suggestions to use third party web server for serving static file.

* ``usePTY`` default value has been changed from ``slave-config`` to ``None`` (use of ``slave-config`` will still work).

* ``GithubStatusPush`` reporter was renamed to :bb:reporter:`GitHubStatusPush`.

Buildslave
----------

Fixes
~~~~~

* ``buildslave`` script now outputs messages to the terminal.


Worker
------

Fixes
~~~~~

* ``runGlob()`` uses the correct remote protocol for both :py:class:`~buildbot.process.buildstep.CommandMixin` and :py:class:`~buildbot.steps.worker.ComposititeStepMixin`.

* Rename ``glob()`` to ``runGlob()`` in :py:class:`~buildbot.process.buildstep.CommandMixin`

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

* EC2 Latent Worker upgraded from ``boto2`` to ``boto3``.

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Worker commands version bumped to 3.0.

* Master/worker protocol has been changed:

  * ``slave_commands`` key in worker information was renamed to ``worker_commands``.

  * ``getSlaveInfo`` remote method was renamed to ``getWorkerInfo``.

  * ``slave-config`` value of ``usePTY`` is not supported anymore.


Details
-------

For a more detailed description of the changes made in this version, see the git log itself:

.. code-block:: bash

   git log v0.9.0b9..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

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
