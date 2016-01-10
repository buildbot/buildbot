Transition to "worker" terminology
==================================

.. todo::

    * ReStructured text formatting should be reviewed in scope of using
      Buildbot-specific directives.

    * This page may be splitted in parts or merged with other pages.

    * This page should be placed in a proper place in the TOC.

    * Links on this page should be added, e.g. from 0.9.0 changelog.

Since version 0.9.0 of Buildbot "slave"-based terminology is deprecated
in favor of "worker"-based terminology.

API change is done in backward compatible way, so old "slave"-containing
classes, functions and attributes are still available and can be used.
Complete removal of "slave"-containing terminology is planned in version
**TODO**.

Old names fallback settings
---------------------------

Use of obsolete names will raise Python warnings with category
:py:exc:`buildbot.worker_transition.DeprecatedWorkerAPIWarning`.
By default these warnings are printed in the application log.
This behaviour can be changed by setting appropriate Python warnings settings
via Python's :py:mod:`warnings` module:

.. code-block:: python

    import warnings
    from buildbot.worker_transition import DeprecatedWorkerAPIWarning
    # Treat old-name usage as errors:
    warnings.simplefilter("error", DeprecatedWorkerAPIWarning)

See Python's :py:mod:`warnings` module documentation for complete list of
available actions, in particular warnings can be disabled using
``"ignore"`` action.

It's recommended to configure warnings inside :file:`buildbot.tac`, before
using any other Buildbot classes.

Changed API
-----------

In general "Slave" and "Buildslave" parts in identifiers was replaced with
"Worker", "SlaveBuilder" with "WorkerBuilder".

Here is the complete list of changed API:

.. todo::

    * This list will be updated along with actual changing of the API.
    * Most of this list can be generated/verified by grepping use of
      ``worker_transition`` helpers.

.. list-table::
   :header-rows: 1

   * - Old name
     - New name

   * - :py:class:`buildbot.interfaces.IBuildSlave`
     - :py:class:`~buildbot.interfaces.IWorker`


   * - :py:class:`buildbot.interfaces.NoSlaveError`
     - :py:class:`~buildbot.interfaces.NoWorkerError`


   * - :py:class:`buildbot.interfaces.BuildSlaveTooOldError`
     - :py:class:`~buildbot.interfaces.WorkerTooOldError`


   * - :py:class:`buildbot.interfaces.LatentBuildSlaveFailedToSubstantiate`
     - :py:class:`~buildbot.interfaces.LatentWorkerFailedToSubstantiate`


   * - :py:class:`buildbot.interfaces.ILatentBuildSlave`
     - :py:class:`~buildbot.interfaces.ILatentWorker`


   * - :py:mod:`buildbot.buildslave` module with all contents
     - :py:mod:`buildbot.worker`

   * - :py:class:`buildbot.buildslave.AbstractBuildSlave`
       (this is an alias of
       :py:class:`buildbot.buildslave.base.AbstractBuildSlave`)
     - :py:class:`buildbot.worker.AbstractWorker`

   * - :py:class:`buildbot.buildslave.base.AbstractBuildSlave`
     - :py:class:`buildbot.worker.base.AbstractWorker`

   * - :py:attr:`buildbot.buildslave.base.AbstractBuildSlave.slavename`
     - :py:attr:`buildbot.worker.base.AbstractWorker.workername`

   * - :py:meth:`buildbot.buildslave.base.AbstractBuildSlave.updateSlave`
     - :py:meth:`buildbot.worker.base.AbstractWorker.updateWorker`


   * - :py:class:`buildbot.buildslave.base.AbstractLatentBuildSlave`
     - :py:class:`buildbot.worker.base.AbstractLatentWorker`

   * - :py:meth:`buildbot.buildslave.base.AbstractLatentBuildSlave.updateSlave`
     - :py:meth:`buildbot.worker.base.AbstractLatentWorker.updateWorker`


   * - :py:class:`buildbot.buildslave.BuildSlave`
       (this is an alias of
       :py:class:`buildbot.buildslave.base.BuildSlave`)
     - :py:class:`buildbot.worker.Worker`

   * - :py:class:`buildbot.buildslave.base.BuildSlave`
     - :py:class:`buildbot.worker.base.Worker`


   * - :py:class:`buildbot.buildslave.AbstractLatentBuildSlave`
       (this is an alias of
       :py:class:`buildbot.buildslave.base.AbstractLatentBuildSlave`)
     - :py:class:`buildbot.worker.AbstractLatentWorker`

   * - :py:class:`buildbot.buildslave.base.AbstractLatentBuildSlave`
     - :py:class:`buildbot.worker.base.AbstractLatentWorker`

   * - :py:attr:`buildbot.master.BuildMaster.buildslaves`
     - :py:attr:`buildbot.worker.base.AbstractWorker.workers`


   * - :py:meth:`buildbot.config.MasterConfig.load_slaves`
     - :py:meth:`~buildbot.config.MasterConfig.load_workers`

Plugins
-------

``buildbot.buildslave`` entry point was renamed to ``buildbot.worker``, new
plugins should be updated accordingly.

Plugins that use old ``buildbot.buildslave`` entry point are still available
in the configuration file in the same way, as they were in versions prior
0.9.0:

.. code-block:: python

    from buildbot.plugins import buildslave
    w = buildslave.ThirdPartyWorker()

But also they available using new namespace inside configuration
file, so its recommended to use ``buildbot.plugins.worker``
name even if plugin uses old entry points:

.. code-block:: python

    from buildbot.plugins import worker
    # ThirdPartyWorker can be defined in using `buildbot.buildslave` entry
    # point, this still will work.
    w = worker.ThirdPartyWorker()

``BuildmasterConfig`` changes
-----------------------------

``c['slaves']`` was replaced with ``c['workers']``.
Use of ``c['slaves']`` will work, but is considered deprecated, and will be
removed in the future versions of Buildbot.
