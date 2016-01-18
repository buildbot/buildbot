Transition to "worker" terminology
==================================

.. todo::

    * ReStructured text formatting should be reviewed in scope of using
      Buildbot-specific directives.

    * This page may be split in parts or merged with other pages.

    * This page should be placed in a proper place in the TOC.

    * Links on this page should be added, e.g. from 0.9.0 changelog.

    * Is all changes are done only for functionality that was in eight branch?
      If something is introduced in nine branch, it can be safely changed
      without providing fallback (for example, Docker stuff).

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

    * Some of attribute/methods that were renamed may be actually private.
      If they are private, then no fallback should be provided and they
      change shouldn't be documented.

    * Thorought tests for old modules imports are not yet written.

    * Test that module reloading works and doesn't produce more warnings than
      it should.

    * Some classes are marked as ``(private?)`` because they are not mentined
      in the documentation, but in my opinion they most probably used by
      end users (so they either should be documented, or fallback for them
      should be removed).

.. list-table::
   :header-rows: 1

   * - Old name
     - New name

   * - :py:class:`buildbot.interfaces.IBuildSlave` (private?)
     - :py:class:`~buildbot.interfaces.IWorker`


   * - :py:class:`buildbot.interfaces.NoSlaveError` (private?)
     - left as is, but deprecated (it shouldn't be used at all)


   * - :py:class:`buildbot.interfaces.BuildSlaveTooOldError`
     - :py:class:`~buildbot.interfaces.WorkerTooOldError`


   * - :py:class:`buildbot.interfaces.LatentBuildSlaveFailedToSubstantiate`
       (private?)
     - :py:class:`~buildbot.interfaces.LatentWorkerFailedToSubstantiate`


   * - :py:class:`buildbot.interfaces.ILatentBuildSlave` (private?)
     - :py:class:`~buildbot.interfaces.ILatentWorker`


   * - :py:class:`buildbot.interfaces.ISlaveStatus` (private?)
     - :py:class:`~buildbot.interfaces.IWorkerStatus`


   * - :py:mod:`buildbot.buildslave` module with all contents
     - :py:mod:`buildbot.worker`


   * - :py:class:`buildbot.buildslave.AbstractBuildSlave` (private?)
     - :py:class:`buildbot.worker.AbstractWorker`

   * - :py:attr:`buildbot.buildslave.AbstractBuildSlave.slavename` (private?)
     - :py:attr:`buildbot.worker.AbstractWorker.workername`


   * - :py:class:`buildbot.buildslave.AbstractLatentBuildSlave`
     - :py:class:`buildbot.worker.AbstractLatentWorker`


   * - :py:class:`buildbot.buildslave.BuildSlave`
     - :py:class:`buildbot.worker.Worker`


   * - :py:class:`buildbot.buildslave.ec2.EC2LatentBuildSlave`
     - :py:class:`buildbot.worker.ec2.EC2LatentWorker`


   * - :py:class:`buildbot.buildslave.libvirt.LibVirtSlave`
     - :py:class:`buildbot.worker.libvirt.LibVirtWorker`


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


   * - :py:mod:`buildbot.steps.slave`
     - :py:mod:`buildbot.steps.worker`


   * - :py:mod:`buildbot.status.slave`
     - :py:mod:`buildbot.status.worker`

   * - :py:mod:`buildbot.status.slave.SlaveStatus`
     - :py:mod:`buildbot.status.worker.WorkerStatus`
       (this class is now new-style Python class)

   * - :py:class:`buildbot.schedulers.forcesched.BuildslaveChoiceParameter`
     - :py:class:`~buildbot.schedulers.forcesched.WorkerChoiceParameter`

API changes between 0.9.0b4 and 0.9.0b5 (done without providing fallback).

.. todo::

   This whole section may be removed since it's not important for users
   upgrading to 0.9.0.

.. list-table::
   :header-rows: 1

   * - Old name
     - New name

   * - :py:mod:`buildbot.buildslave.manager`
     - :py:mod:`buildbot.worker.manager`

   * - :py:class:`buildbot.buildslave.manager.BuildslaveRegistration`
     - :py:class:`buildbot.worker.manager.WorkerRegistration`

   * - :py:class:`buildbot.buildslave.manager.BuildslaveRegistration.buildslave`
     - :py:class:`buildbot.worker.manager.WorkerRegistration.worker`

   * - :py:class:`buildbot.buildslave.manager.BuildslaveManager`
     - :py:class:`buildbot.worker.manager.WorkerManager`

   * - :py:attr:`buildbot.buildslave.manager.BuildslaveManager.name` metric
       mesurement class name changed from ``BuildslaveManager``
     - to ``WorkerManager``

   * - :py:attr:`buildbot.buildslave.manager.BuildslaveManager.managed_services_name`
       metric mesurement managed service name changed from ``buildslaves``
     - to ``workers``

   * - :py:attr:`buildbot.buildslave.manager.BuildslaveManager.slaves`
     - :py:attr:`buildbot.worker.manager.WorkerManager.workers`

   * - :py:meth:`buildbot.buildslave.manager.BuildslaveManager.getBuildslaveByName`
     - :py:meth:`buildbot.worker.manager.WorkerManager.getWorkerByName`


   * - :py:class:`buildbot.buildslave.docker.DockerLatentBuildSlave`
     - :py:class:`buildbot.worker.docker.DockerLatentWorker`


   * - :py:class:`buildbot.buildslave.local.LocalBuildSlave`
     - :py:class:`buildbot.worker.local.LocalWorker`

   * - :py:attr:`buildbot.buildslave.local.LocalBuildSlave.LocalBuildSlaveFactory`
     - :py:attr:`buildbot.worker.local.LocalWorker.LocalWorkerFactory`

   * - :py:attr:`buildbot.buildslave.local.LocalBuildSlave.remote_slave`
     - :py:attr:`buildbot.worker.local.LocalWorker.remote_worker`


   * - :py:mod:`buildbot.buildslave.base` module with all contents
     - :py:mod:`buildbot.worker.base`


   * - :py:meth:`buildbot.buildslave.AbstractBuildSlave.updateSlave`
     - :py:meth:`buildbot.worker.AbstractWorker.updateWorker`

   * - :py:attr:`buildbot.buildslave.AbstractBuildSlave.slavebuilders`
     - :py:attr:`buildbot.worker.AbstractWorker.workerforbuilders`


   * - :py:meth:`buildbot.buildslave.AbstractLatentBuildSlave.updateSlave`
     - :py:meth:`buildbot.worker.AbstractLatentWorker.updateWorker`


   * - :py:class:`buildbot.buildslave.BuildSlave.slave_status`
     - :py:class:`buildbot.worker.Worker.worker_status`


   * - :py:meth:`buildbot.config.MasterConfig.load_slaves`
     - :py:meth:`~buildbot.config.MasterConfig.load_workers`


   * - :py:attr:`buildbot.master.BuildMaster.buildslaves`
     - :py:attr:`buildbot.master.BuildMaster.workers`


   * - :py:attr:`buildbot.process.build.Build.slavebuilder`
     - :py:attr:`~buildbot.process.build.Build.workerforbuilder`

   * - :py:meth:`buildbot.process.build.Build.setSlaveEnvironment`
     - :py:meth:`~buildbot.process.build.Build.setWorkerEnvironment`

   * - :py:attr:`buildbot.process.build.Build.slaveEnvironment`
     - :py:attr:`~buildbot.process.build.Build.workerEnvironment`

   * - :py:meth:`buildbot.process.build.Build.getSlaveCommandVersion`
     - :py:meth:`~buildbot.process.build.Build.getWorkerCommandVersion`

   * - :py:meth:`buildbot.process.build.Build.setupSlaveBuilder`
     - :py:meth:`~buildbot.process.build.Build.setupWorkerForBuilder`

   * - :py:meth:`buildbot.process.builder.Build.canStartWithSlavebuilder`
     - :py:meth:`~buildbot.process.builder.Build.canStartWithWorkerForBuilder`


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


   * - :py:attr:`buildbot.steps.shell.ShellCommand.slaveEnvironment`
       (Note: this variable is renderable)
     - :py:attr:`buildbot.steps.shell.ShellCommand.workerEnvironment`


   * - :py:class:`buildbot.steps.slave.SlaveBuildStep`
     - :py:class:`buildbot.steps.worker.SlaveBuildStep`


   * - :py:meth:`buildbot.process.slavebuilder.AbstractSlaveBuilder.getSlaveCommandVersion`
     - :py:meth:`buildbot.process.workerforbuilder.AbstractWorkerForBuilder.getWorkerCommandVersion`


Other changes:

* ``buildslaveName`` functions argument name renamed to ``workerName``.

* ``s`` and ``sl`` loops variables were renamed to ``worker`` or ``w``.

* In :py:meth:`buildbot.config.BuilderConfig.getConfigDict` result
  ``'slavenames'`` key changed to ``workernames``;
  ``'slavebuilddir'`` key changed to ``workerbuilddir``;
  ``'nextSlave'`` key changed to ``nextWorker``.

* Configuration key ``c['slavePortnum']`` is deprecated in favor of
  ``c['protocols']['pb']['port']``.

* :py:meth:`buildbot.process.builder.BuilderControl.ping` now generates
  ``["ping", "no worker"]`` event, instead of ``["ping", "no slave"]``.

* Definitely privately used "slave"-named variables and attributes were
  renamed, including tests modules, classes and methods.

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

``buildbot.plugins.util.BuildslaveChoiceParameter`` is deprecated in favor of
``WorkerChoiceParameter``.

``buildbot.plugins.util.enforceChosenSlave`` is deprecated in favor of
``enforceChosenWorker``.

``BuildmasterConfig`` changes
-----------------------------

``c['slaves']`` was replaced with ``c['workers']``.
Use of ``c['slaves']`` will work, but is considered deprecated, and will be
removed in the future versions of Buildbot.

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
