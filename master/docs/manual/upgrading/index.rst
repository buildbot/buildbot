Upgrading
=========

This section describes the process of upgrading from old versions of Buildbot.

Upgrades between multiple major versions at a time are not supported.
To do so, first upgrade to the last version before the major version bump.
Then fix any deprecation warnings, migrate off APIs removed in the next major version.
And finally, perform the upgrade to the next major version.

.. toctree::
   :maxdepth: 1

   2.0-upgrade
   1.0-upgrade
   0.9-upgrade
   0.9-new-style-steps
   0.9-worker-transition
