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

* new :bb:reporter:`GitLabStatusPush` to report builds results to GitLab.

* ``buildbot stop`` now waits for complete buildmaster stop by default.

* New ``--no-wait`` argument for ``buildbot stop`` which allows not to wait for complete master shutdown.

Fixes
~~~~~

* OpenStackLatentWorker uses the novaclient API correctly now.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

Features
~~~~~~~~

Fixes
~~~~~

* The :bb:step:`MsBuild4` and :bb:step:`MsBuild12` steps work again (:bug:`2878`).

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* The buildmaster now requires at least Twisted-14.0.1.

* Web server does not provide /png and /redirect anymore (:bug:`3357`).
  This functionality is used to implement build status images.
  This should be easy to implement if you need it.
  One could port the old image generation code, or implement a redirection to http://shields.io/.

* html is not permitted anymore in 'label' attributes of forcescheduler parameters.

* ``LocalWorker`` now requires ``buildbot-worker`` package, instead of ``buildbot-slave``.

Worker
------

Fixes
~~~~~

* ``buildbot-worker`` script now outputs message to terminal.

* Windows helper script now called ``buildbot-worker.bat`` (was ``buildbot_worker.bat``, notice underscore), so that ``buildbot-worker`` command can be used in virtualenv both on Windows and POSIX systems.

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~

* ``SLAVEPASS`` environment variable is not removed in default-generated ``buildbot.tac``.
  Environment variables are cleared in places where they are used (e.g. in Docker Latent Worker contrib scripts).

* Master-part handling has been removed from ``buildbot-worker`` log watcher (:bug:`3482`).

* ``WorkerDetectedError`` exception type has been removed.

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
