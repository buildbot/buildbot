.. _Upgrading:

Upgrading
=========

This section describes the process of upgrading the master and workers from old versions of Buildbot.

The users of the Buildbot project will be warned about backwards-incompatible changes by warnings produced by the code.
Additionally, all backwards-incompatible changes will be done at a major version change (e.g. 1.x to 2.0).
Minor version change (e.g. 2.3 to 2.4) will only introduce backwards-incompatible changes only if they affect small part of the users and are absolutely necessary.
Direct upgrades between more than two major releases (e.g. 1.x to 3.x) are not supported.

The versions of the master and the workers do not need to match, so it's possible to upgrade them separately.

Usually there are no actions needed to upgrade a worker except to install a new version of the code and restart it.

Usually the process of upgrading the master is as simple as running the following command:

.. code-block:: bash

    buildbot upgrade-master basedir

This command will also scan the :file:`master.cfg` file for incompatibilities (by loading it and printing any errors or deprecation warnings that occur).
It is safe to run this command multiple times.

.. warning::

   The ``upgrade-master`` command may perform database schema modifications.
   To avoid any data loss or corruption, it should **not** be interrupted.
   As a safeguard, it ignores all signals except ``SIGKILL``.

To upgrade between major releases the best approach is first to upgrade to the latest minor release on the same major release.
Then, fix all deprecation warnings by upgrading the configuration code to the replacement APIs.
Finally, upgrade to the next major release.


.. toctree::
   :maxdepth: 1

   4.0-upgrade
   3.0-upgrade
   2.0-upgrade
   1.0-upgrade
   0.9-upgrade
   0.9-new-style-steps
   0.9-worker-transition
