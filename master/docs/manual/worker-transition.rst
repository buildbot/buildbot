.. _Transition-to-worker-terminology:

Transition to "worker" terminology
==================================

Since version 0.9.0 of Buildbot "slave"-based terminology is deprecated
in favor of "worker"-based terminology.

API change is done in backward compatible way, so old "slave"-containing
classes, functions and attributes are still available and can be used.
Old API support will be removed in the future versions of Buildbot.

Rename of API introduced in beta versions of Buildbot 0.9.0 done without
providing fallback.
See release notes for the list of breaking changes of private interfaces.

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

In general "Slave" and "Buildslave" parts in identifiers and messages were
replaced with "Worker"; "SlaveBuilder" with "WorkerForBuilder".

Below is the list of changed API (use of old names from this list will work).
Note that some of these symbols are not included in Buildbot's public API.
Compatibility is provided as a convenience to those using the private symbols
anyway.

.. list-table::
   :header-rows: 1

   * - Old name
     - New name

   * - :py:class:`buildbot.interfaces.IBuildSlave`
     - :py:class:`~buildbot.interfaces.IWorker`


   * - :py:class:`buildbot.interfaces.NoSlaveError` (private)
     - left as is, but deprecated (it shouldn't be used at all)


   * - :py:class:`buildbot.interfaces.BuildSlaveTooOldError`
     - :py:class:`~buildbot.interfaces.WorkerTooOldError`


   * - :py:class:`buildbot.interfaces.LatentBuildSlaveFailedToSubstantiate`
       (private)
     - :py:class:`~buildbot.interfaces.LatentWorkerFailedToSubstantiate`


   * - :py:class:`buildbot.interfaces.ILatentBuildSlave`
     - :py:class:`~buildbot.interfaces.ILatentWorker`


   * - :py:class:`buildbot.interfaces.ISlaveStatus` (will be removed in 0.9.x)
     - :py:class:`~buildbot.interfaces.IWorkerStatus`


   * - :py:mod:`buildbot.buildslave` module with all contents
     - :py:mod:`buildbot.worker`


   * - :py:class:`buildbot.buildslave.AbstractBuildSlave`
     - :py:class:`buildbot.worker.AbstractWorker`

   * - :py:attr:`buildbot.buildslave.AbstractBuildSlave.slavename` (private)
     - :py:attr:`buildbot.worker.AbstractWorker.workername`


   * - :py:class:`buildbot.buildslave.AbstractLatentBuildSlave`
     - :py:class:`buildbot.worker.AbstractLatentWorker`


   * - :py:class:`buildbot.buildslave.BuildSlave`
     - :py:class:`buildbot.worker.Worker`


   * - :py:mod:`buildbot.buildslave.ec2`
     - :py:mod:`buildbot.worker.ec2`

   * - :py:class:`buildbot.buildslave.ec2.EC2LatentBuildSlave`
     - :py:class:`buildbot.worker.ec2.EC2LatentWorker`


   * - :py:mod:`buildbot.buildslave.libvirt`
     - :py:mod:`buildbot.worker.libvirt`

   * - :py:class:`buildbot.buildslave.libvirt.LibVirtSlave`
     - :py:class:`buildbot.worker.libvirt.LibVirtWorker`


   * - :py:mod:`buildbot.buildslave.openstack`
     - :py:mod:`buildbot.worker.openstack`

   * - :py:class:`buildbot.buildslave.openstack.OpenStackLatentBuildSlave`
     - :py:class:`buildbot.worker.openstack.OpenStackLatentWorker`


   * - :py:attr:`buildbot.config.MasterConfig.slaves`
     - :py:attr:`~buildbot.config.MasterConfig.workers`


   * - :py:attr:`buildbot.config.BuilderConfig` constructor keyword argument
       ``slavename`` was renamed to

     - ``workername``

   * - :py:attr:`buildbot.config.BuilderConfig` constructor keyword argument
       ``slavenames`` was renamed to

     - ``workernames``

   * - :py:attr:`buildbot.config.BuilderConfig` constructor keyword argument
       ``slavebuilddir`` was renamed to

     - ``workerbuilddir``

   * - :py:attr:`buildbot.config.BuilderConfig` constructor keyword argument
       ``nextSlave`` was renamed to

     - ``nextWorker``

   * - :py:attr:`buildbot.config.BuilderConfig.slavenames`
     - :py:attr:`~buildbot.config.BuilderConfig.workernames`

   * - :py:attr:`buildbot.config.BuilderConfig.slavebuilddir`
     - :py:attr:`~buildbot.config.BuilderConfig.workerbuilddir`

   * - :py:attr:`buildbot.config.BuilderConfig.nextSlave`
     - :py:attr:`~buildbot.config.BuilderConfig.nextWorker`


   * - :py:mod:`buildbot.process.slavebuilder`
     - :py:mod:`buildbot.process.workerforbuilder`


   * - :py:class:`buildbot.process.slavebuilder.AbstractSlaveBuilder`
     - :py:class:`buildbot.process.workerforbuilder.AbstractWorkerForBuilder`

   * - :py:attr:`buildbot.process.slavebuilder.AbstractSlaveBuilder.slave`
     - :py:attr:`buildbot.process.workerforbuilder.AbstractWorkerForBuilder.worker`


   * - :py:class:`buildbot.process.slavebuilder.SlaveBuilder`
     - :py:class:`buildbot.process.workerforbuilder.WorkerForBuilder`

   * - :py:class:`buildbot.process.slavebuilder.LatentSlaveBuilder`
     - :py:class:`buildbot.process.workerforbuilder.LatentWorkerForBuilder`


   * - :py:meth:`buildbot.process.build.Build.getSlaveName`
     - :py:meth:`~buildbot.process.build.Build.getWorkerName`

   * - :py:meth:`buildbot.process.build.Build.slavename`
     - :py:meth:`~buildbot.process.build.Build.workername`


   * - :py:func:`buildbot.process.builder.enforceChosenSlave`
     - :py:func:`~buildbot.process.builder.enforceChosenWorker`


   * - :py:meth:`buildbot.process.builder.Builder.canStartWithSlavebuilder`
     - :py:meth:`~buildbot.process.builder.Builder.canStartWithWorkerForBuilder`

   * - :py:attr:`buildbot.process.builder.Builder.attaching_slaves`
     - :py:attr:`~buildbot.process.builder.Builder.attaching_workers`

   * - :py:attr:`buildbot.process.builder.Builder.slaves`
     - :py:attr:`~buildbot.process.builder.Builder.workers`

   * - :py:meth:`buildbot.process.builder.Builder.addLatentSlave`
     - :py:meth:`~buildbot.process.builder.Builder.addLatentWorker`

   * - :py:meth:`buildbot.process.builder.Builder.getAvailableSlaves`
     - :py:meth:`~buildbot.process.builder.Builder.getAvailableWorkers`


   * - :py:class:`buildbot.schedulers.forcesched.BuildslaveChoiceParameter`
     - :py:class:`~buildbot.schedulers.forcesched.WorkerChoiceParameter`


   * - :py:attr:`buildbot.process.buildstep.BuildStep.buildslave`
     - :py:attr:`buildbot.process.buildstep.BuildStep.worker`
       (also it was moved from class static attribute to instance attribute)

   * - :py:meth:`buildbot.process.buildstep.BuildStep.setBuildSlave`
     - :py:meth:`buildbot.process.buildstep.BuildStep.setWorker`

   * - :py:meth:`buildbot.process.buildstep.BuildStep.slaveVersion`
     - :py:meth:`buildbot.process.buildstep.BuildStep.workerVersion`

   * - :py:meth:`buildbot.process.buildstep.BuildStep.slaveVersionIsOlderThan`
     - :py:meth:`buildbot.process.buildstep.BuildStep.workerVersionIsOlderThan`

   * - :py:meth:`buildbot.process.buildstep.BuildStep.checkSlaveHasCommand`
     - :py:meth:`buildbot.process.buildstep.BuildStep.checkWorkerHasCommand`

   * - :py:meth:`buildbot.process.buildstep.BuildStep.getSlaveName`
     - :py:meth:`buildbot.process.buildstep.BuildStep.getWorkerName`


   * - :py:class:`buildbot.locks.SlaveLock`
     - :py:class:`buildbot.locks.WorkerLock`

   * - :py:attr:`buildbot.locks.SlaveLock.maxCountForSlave`
     - :py:attr:`buildbot.locks.WorkerLock.maxCountForWorker`

   * - :py:class:`buildbot.locks.SlaveLock` constructor argument
       ``maxCountForSlave`` was renamed
     - ``maxCountForWorker``


   * - :py:mod:`buildbot.steps.slave`
     - :py:mod:`buildbot.steps.worker`

   * - :py:class:`buildbot.steps.slave.SlaveBuildStep`
     - :py:class:`buildbot.steps.worker.WorkerBuildStep`

   * - :py:class:`buildbot.steps.slave.CompositeStepMixin.getFileContentFromSlave`
     - :py:class:`buildbot.steps.worker.CompositeStepMixin.getFileContentFromWorker`


   * - :py:attr:`buildbot.steps.transfer.FileUpload.slavesrc`
     - :py:attr:`~buildbot.steps.transfer.FileUpload.workersrc`

   * - :py:class:`buildbot.steps.transfer.FileUpload`
       constructor argument ``slavesrc`` was renamed to

     - ``workersrc``


   * - :py:attr:`buildbot.steps.transfer.DirectoryUpload.slavesrc`
     - :py:attr:`~buildbot.steps.transfer.DirectoryUpload.workersrc`

   * - :py:class:`buildbot.steps.transfer.DirectoryUpload`
       constructor argument ``slavesrc`` was renamed to

     - ``workersrc``


   * - :py:attr:`buildbot.steps.transfer.MultipleFileUpload.slavesrcs`
     - :py:attr:`~buildbot.steps.transfer.MultipleFileUpload.workersrcs`

   * - :py:class:`buildbot.steps.transfer.MultipleFileUpload`
       constructor argument ``slavesrcs`` was renamed to

     - ``workersrcs``


   * - :py:attr:`buildbot.steps.transfer.FileDownload.slavedest`
     - :py:attr:`~buildbot.steps.transfer.FileDownload.workerdest`

   * - :py:class:`buildbot.steps.transfer.FileDownload`
       constructor argument ``slavedest`` was renamed to

     - ``workerdest``


   * - :py:attr:`buildbot.steps.transfer.StringDownload.slavedest`
     - :py:attr:`~buildbot.steps.transfer.StringDownload.workerdest`

   * - :py:class:`buildbot.steps.transfer.StringDownload`
       constructor argument ``slavedest`` was renamed to

     - ``workerdest``


   * - :py:attr:`buildbot.steps.transfer.JSONStringDownload.slavedest`
     - :py:attr:`~buildbot.steps.transfer.JSONStringDownload.workerdest`

   * - :py:class:`buildbot.steps.transfer.JSONStringDownload`
       constructor argument ``slavedest`` was renamed to

     - ``workerdest``


   * - :py:attr:`buildbot.steps.transfer.JSONPropertiesDownload.slavedest`
     - :py:attr:`~buildbot.steps.transfer.JSONPropertiesDownload.workerdest`

   * - :py:class:`buildbot.steps.transfer.JSONPropertiesDownload`
       constructor argument ``slavedest`` was renamed to

     - ``workerdest``

   * - :py:attr:`buildbot.process.remotecommand.RemoteCommand.buildslave`
     - :py:attr:`~buildbot.process.remotecommand.RemoteCommand.worker`



Plugins
-------

``buildbot.buildslave`` entry point was renamed to ``buildbot.worker``, new
plugins should be updated accordingly.

Plugins that use old ``buildbot.buildslave`` entry point are still available
in the configuration file in the same way, as they were in versions prior
0.9.0:

.. code-block:: python

    from buildbot.plugins import buildslave  # deprecated, use "worker" instead
    w = buildslave.ThirdPartyWorker()

But also they available using new namespace inside configuration
file, so its recommended to use ``buildbot.plugins.worker``
name even if plugin uses old entry points:

.. code-block:: python

    from buildbot.plugins import worker
    # ThirdPartyWorker can be defined in using `buildbot.buildslave` entry
    # point, this still will work.
    w = worker.ThirdPartyWorker()

Other changes:

* ``buildbot.plugins.util.BuildslaveChoiceParameter`` is deprecated in favor of
  ``WorkerChoiceParameter``.

* ``buildbot.plugins.util.enforceChosenSlave`` is deprecated in favor of
  ``enforceChosenWorker``.

* ``buildbot.plugins.util.SlaveLock`` is deprecated in favor of
  ``WorkerLock``.

``BuildmasterConfig`` changes
-----------------------------

* ``c['slaves']`` was replaced with ``c['workers']``.
  Use of ``c['slaves']`` will work, but is considered deprecated, and will be
  removed in the future versions of Buildbot.

* Configuration key ``c['slavePortnum']`` is deprecated in favor of
  ``c['protocols']['pb']['port']``.


Docker latent worker changes
----------------------------

In addition to class being renamed, environment variables that are set inside
container ``SLAVENAME`` and ``SLAVEPASS`` were renamed to
``WORKERNAME`` and ``WORKERPASS`` accordingly.
Old environment variable are still available, but are deprecated and will be
removed in the future.

EC2 latent worker changes
-------------------------

Use of default values of ``keypair_name`` and ``security_name``
constructor arguments of :py:class:`buildbot.worker.ec2.EC2LatentWorker`
is deprecated. Please specify them explicitly.

``steps.slave.SetPropertiesFromEnv`` changes
--------------------------------------------

In addition to ``buildbot.steps.slave`` module being renamed to
:py:mod:`buildbot.steps.worker`, default ``source`` value for
:py:class:`~buildbot.steps.worker.SetPropertiesFromEnv` was changed from
``"SlaveEnvironment"`` to ``"WorkerEnvironment"``.

Local worker changes
--------------------

Working directory for local workers were changed from
``master-basedir/slaves/name`` to ``master-basedir/workers/name``.

Worker Manager changes
----------------------

``slave_config`` function argument was renamed to ``worker_config``.

Properties
----------

* ``slavename`` property is deprecated in favor of ``workername`` property.
  Render of deprecated property will produce warning.

  :py:class:`buildbot.worker.AbstractWorker`
  (previously ``buildbot.buildslave.AbstractBuildSlave``) ``slavename``
  property source were changed from ``BuildSlave`` to
  ``Worker (deprecated)``

  :py:class:`~buildbot.worker.AbstractWorker` now sets ``workername``
  property with source ``Worker`` which should be used.

Metrics
-------

* :py:class:`buildbot.process.metrics.AttachedSlavesWatcher` was renamed to
  :py:class:`buildbot.process.metrics.AttachedWorkersWatcher`.

* :py:attr:`buildbot.worker.manager.WorkerManager.name`
  (previously ``buildbot.buildslave.manager.BuildslaveManager.name``) metric
  measurement class name changed from ``BuildslaveManager`` to ``WorkerManager``

* :py:attr:`buildbot.worker.manager.WorkerManager.managed_services_name`
  (previously ``buildbot.buildslave.manager.BuildslaveManager.managed_services_name`)
  metric measurement managed service name changed from ``buildslaves`` to
  ``workers``

Renamed events:

.. list-table::
   :header-rows: 1

   * - Old name
     - New name

   * - ``AbstractBuildSlave.attached_slaves``
     - ``AbstractWorker.attached_workers``

   * - ``BotMaster.attached_slaves``
     - ``BotMaster.attached_workers``

   * - ``BotMaster.slaveLost()``
     - ``BotMaster.workerLost()``

   * - ``BotMaster.getBuildersForSlave()``
     - ``BotMaster.getBuildersForWorker()``

   * - ``AttachedSlavesWatcher``
     - ``AttachedWorkersWatcher``

   * - ``attached_slaves``
     - ``attached_workers``

Database
--------

Schema changes:

.. list-table::
   :header-rows: 1

   * - Old name
     - New name

   * - ``buildslaves`` table
     - ``workers``

   * - ``builds.buildslaveid`` (not ForeignKey) column
     - ``workerid`` (now ForeignKey)


   * - ``configured_buildslaves`` table
     - ``configured_workers``

   * - ``configured_buildslaves.buildslaveid`` (ForeignKey) column
     - ``workerid``


   * - ``connected_buildslaves`` table
     - ``connected_workers``

   * - ``connected_buildslaves.buildslaveid`` (ForeignKey) column
     - ``workerid``


   * - ``buildslaves_name`` index
     - ``workers_name``

   * - ``configured_slaves_buildmasterid`` index
     - ``configured_workers_buildmasterid``

   * - ``configured_slaves_slaves`` index
     - ``configured_workers_workers``

   * - ``configured_slaves_identity`` index
     - ``configured_workers_identity``

   * - ``connected_slaves_masterid`` index
     - ``connected_workers_masterid``

   * - ``connected_slaves_slaves`` index
     - ``connected_workers_workers``

   * - ``connected_slaves_identity`` index
     - ``connected_workers_identity``

   * - ``builds_buildslaveid`` index
     - ``builds_workerid``

List of database-related changes in API (fallback for old API is provided):

.. list-table::
   :header-rows: 1

   * - Old name
     - New name

   * - :py:mod:`buildbot.db.buildslaves`
     - :py:mod:`~buildbot.db.workers`


   * - :py:class:`buildbot.db.buildslaves.BuildslavesConnectorComponent`
     - :py:class:`buildbot.db.workers.WorkersConnectorComponent`

   * - :py:meth:`buildbot.db.buildslaves.BuildslavesConnectorComponent.getBuildslaves`
       (rewritten in nine)
     - :py:meth:`buildbot.db.workers.WorkersConnectorComponent.getWorkers`


   * - :py:attr:`buildbot.db.connector.DBConnector.buildslaves`
     - :py:attr:`buildbot.db.connector.DBConnector.workers`

``buildbot-worker``
-------------------

``buildbot-slave`` package has been deprecated in favor of ``buildbot-worker`` package.

``buildbot-worker`` has backward incompatible changes and requires buildmaster >= 0.9.0b8.
``buildbot-slave`` will work with both 0.8.x and 0.9.x versions of buildmaster, so there is no need to upgrade currently deployed buildbot-slaves during switch from 0.8.x to 0.9.x.

.. list-table:: Master/worker compatibility table
   :header-rows: 1
   :stub-columns: 1

   * -
     - master 0.8.x
     - master 0.9.x
   * - buildbot-slave
     - yes
     - yes
   * - buildbot-worker
     - no
     - yes

``buildbot-worker`` doesn't support worker-side specification of ``usePTY`` (with ``--usepty`` command line switch of ``buildbot-worker create-worker``), you need to specify this option on master side.
