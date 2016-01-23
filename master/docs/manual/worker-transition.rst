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


   * - :py:mod:`buildbot.db.buildslave`
     - :py:mod:`~buildbot.db.worker`


   * - :py:class:`buildbot.db.buildslave.BuildslavesConnectorComponent`
     - :py:class:`buildbot.db.worker.WorkersConnectorComponent`

   * - :py:meth:`buildbot.db.buildslave.BuildslavesConnectorComponent.findBuildslaveId`
     - :py:meth:`buildbot.db.worker.WorkersConnectorComponent.findWorkerId`

   * - :py:meth:`buildbot.db.buildslave.BuildslavesConnectorComponent.deconfigureAllBuidslavesForMaster`
       (note typo ``Buidslaves``)
     - :py:meth:`buildbot.db.worker.WorkersConnectorComponent.deconfigureAllWorkersForMaster`

   * - :py:meth:`buildbot.db.buildslave.BuildslavesConnectorComponent.buildslaveConfigured`
       (introduced in nine)
     - :py:meth:`buildbot.db.worker.WorkersConnectorComponent.workerConfigured`

   * - :py:meth:`buildbot.db.buildslave.BuildslavesConnectorComponent.getBuildslave`
     - :py:meth:`buildbot.db.worker.WorkersConnectorComponent.getWorker`

   * - :py:meth:`buildbot.db.buildslave.BuildslavesConnectorComponent.getBuildslaves`
     - :py:meth:`buildbot.db.worker.WorkersConnectorComponent.getWorkers`

   * - :py:meth:`buildbot.db.buildslave.BuildslavesConnectorComponent.buildslaveConnected`
     - :py:meth:`buildbot.db.worker.WorkersConnectorComponent.workerConnected`

   * - :py:meth:`buildbot.db.buildslave.BuildslavesConnectorComponent.buildslaveDisconnected`
     - :py:meth:`buildbot.db.worker.WorkersConnectorComponent.workerDisconnected`

API changes between 0.9.0b6 and 0.9.0b7 (done without providing fallback).

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

   * - :py:meth:`buildbot.buildslave.AbstractBuildSlave.updateSlaveStatus`
     - :py:meth:`buildbot.worker.AbstractWorker.updateWorkerStatus`


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


   * - :py:meth:`buildbot.process.slavebuilder.AbstractSlaveBuilder.getSlaveCommandVersion`
     - :py:meth:`buildbot.process.workerforbuilder.AbstractWorkerForBuilder.getWorkerCommandVersion`

   * - :py:meth:`buildbot.process.slavebuilder.AbstractSlaveBuilder.attached`
       method argument ``slave`` was renamed
     - ``worker``


   * - :py:attr:`buildbot.buildslave.AbstractBuildSlave.slave_commands`
     - :py:attr:`buildbot.worker.AbstractWorker.worker_commands`

   * - :py:attr:`buildbot.buildslave.AbstractBuildSlave.slave_environ`
     - :py:attr:`buildbot.worker.AbstractWorker.worker_environ`

   * - :py:attr:`buildbot.buildslave.AbstractBuildSlave.slave_basedir`
     - :py:attr:`buildbot.worker.AbstractWorker.worker_basedir`

   * - :py:attr:`buildbot.buildslave.AbstractBuildSlave.slave_system`
     - :py:attr:`buildbot.worker.AbstractWorker.worker_system`

   * - :py:attr:`buildbot.buildslave.AbstractBuildSlave.buildslaveid`
     - :py:attr:`buildbot.worker.AbstractWorker.workerid`

   * - :py:meth:`buildbot.buildslave.AbstractBuildSlave.addSlaveBuilder`
     - :py:meth:`buildbot.worker.AbstractWorker.addWorkerForBuilder`

   * - :py:meth:`buildbot.buildslave.AbstractBuildSlave.removeSlaveBuilder`
     - :py:meth:`buildbot.worker.AbstractWorker.removeWorkerForBuilder`

   * - :py:meth:`buildbot.buildslave.AbstractBuildSlave.messageReceivedFromSlave`
     - :py:meth:`buildbot.worker.AbstractWorker.messageReceivedFromWorker`


   * - :py:meth:`buildbot.process.slavebuilder.LatentSlaveBuilder`
       constructor positional argument ``slave`` was renamed
     - ``worker``


   * - :py:attr:`buildbot.process.buildrequestdistributor.BasicBuildChooser.nextSlave`
     - :py:attr:`~buildbot.process.buildrequestdistributor.BasicBuildChooser.nextWorker`

   * - :py:attr:`buildbot.process.buildrequestdistributor.BasicBuildChooser.slavepool`
     - :py:attr:`~buildbot.process.buildrequestdistributor.BasicBuildChooser.workerpool`

   * - :py:attr:`buildbot.process.buildrequestdistributor.BasicBuildChooser.preferredSlaves`
     - :py:attr:`~buildbot.process.buildrequestdistributor.BasicBuildChooser.preferredWorkers`

   * - :py:attr:`buildbot.process.buildrequestdistributor.BasicBuildChooser.rejectedSlaves`
     - :py:attr:`~buildbot.process.buildrequestdistributor.BasicBuildChooser.rejectedSlaves`


   * - :py:attr:`buildbot.steps.shell.ShellCommand.slaveEnvironment`
       (Note: this variable is renderable)
     - :py:attr:`buildbot.steps.shell.ShellCommand.workerEnvironment`


   * - :py:mod:`buildbot.status.slave`
     - :py:mod:`buildbot.status.worker`

   * - :py:class:`buildbot.status.slave.SlaveStatus`
     - :py:class:`buildbot.status.worker.WorkerStatus`

   * - :py:meth:`buildbot.interfaces.IStatusReceiver.slaveConnected`
       with all implementations
     - :py:meth:`buildbot.interfaces.IStatusReceiver.workerConnected`

   * - :py:meth:`buildbot.interfaces.IStatusReceiver.slaveDisconnected`
       with all implementations
     - :py:meth:`buildbot.interfaces.IStatusReceiver.workerDisconnected`

   * - :py:meth:`buildbot.status.master.Status.slaveConnected`
     - :py:meth:`buildbot.status.master.Status.workerConnected`

   * - :py:meth:`buildbot.status.master.Status.slaveDisconnected`
     - :py:meth:`buildbot.status.master.Status.workerDisconnected`

   * - :py:meth:`buildbot.status.master.Status.slavePaused`
     - :py:meth:`buildbot.status.master.Status.workerPaused`

   * - :py:meth:`buildbot.status.master.Status.slaveUnpaused`
     - :py:meth:`buildbot.status.master.Status.workerUnpaused`

   * - :py:attr:`buildbot.status.master.Status.buildslaves`
     - :py:attr:`buildbot.status.master.Status.workers`

   * - :py:meth:`buildbot.status.base.StatusReceiverBase.slavePaused`
     - :py:meth:`buildbot.status.base.StatusReceiverBase.workerPaused`

   * - :py:meth:`buildbot.status.base.StatusReceiverBase.slaveUnpaused`
     - :py:meth:`buildbot.status.base.StatusReceiverBase.workerUnpaused`

   * - :py:meth:`buildbot.interfaces.IStatus.getSlaveNames`
       with all implementations
     - :py:meth:`buildbot.interfaces.IStatus.getWorkerNames`

   * - :py:meth:`buildbot.interfaces.IStatus.getSlave`
       with all implementations
     - :py:meth:`buildbot.interfaces.IStatus.getWorker`


   * - :py:meth:`buildbot.interfaces.IBuildStatus.getSlavename`
       with all implementations
     - :py:meth:`buildbot.interfaces.IBuildStatus.getWorkername`

   * - :py:meth:`buildbot.status.build.BuildStatus.setSlavename`
     - :py:meth:`buildbot.status.build.BuildStatus.setWorkername`

   * - :py:attr:`buildbot.status.build.BuildStatus.slavename`
     - :py:attr:`buildbot.status.build.BuildStatus.workername`
       (also it was moved from class static attribute to instance attribute)


   * - :py:meth:`buildbot.interfaces.IBuilderStatus.getSlaves`
       with all implementations
     - :py:meth:`buildbot.interfaces.IBuilderStatus.getWorkers`

   * - :py:attr:`buildbot.status.builder.BuilderStatus.slavenames`
     - :py:attr:`buildbot.status.builder.BuilderStatus.workernames`

   * - :py:meth:`buildbot.status.builder.BuilderStatus.setSlavenames`
     - :py:meth:`buildbot.status.builder.BuilderStatus.setWorkernames`


   * - :py:meth:`buildbot.process.botmaster.BotMaster.slaveLost`
     - :py:meth:`buildbot.process.botmaster.BotMaster.workerLost`

   * - :py:meth:`buildbot.process.botmaster.BotMaster.getBuildersForSlave`
     - :py:meth:`buildbot.process.botmaster.BotMaster.getBuildersForWorker`

   * - :py:meth:`buildbot.process.botmaster.BotMaster.maybeStartBuildsForSlave`
     - :py:meth:`buildbot.process.botmaster.BotMaster.maybeStartBuildsForWorker`


   * - :py:class:`buildbot.locks.RealSlaveLock`
     - :py:class:`buildbot.locks.RealWorkerLock`

   * - :py:attr:`buildbot.locks.RealSlaveLock.maxCountForSlave`
     - :py:attr:`buildbot.locks.RealWorkerLock.maxCountForWorker`


   * - :py:class:`buildbot.protocols.base.Connection`
       constructor positional argument ``buildslave`` was renamed
     - ``worker``

   * - :py:attr:`buildbot.protocols.base.Connection.buidslave`
     - :py:attr:`buildbot.protocols.base.Connection.worker`

   * - :py:meth:`buildbot.protocols.base.Connection.remoteGetSlaveInfo`
     - :py:meth:`buildbot.protocols.base.Connection.remoteGetWorkerInfo`


   * - :py:class:`buildbot.protocols.pb.Connection`
       constructor positional argument ``buildslave`` was renamed
     - ``worker``


   * - :py:meth:`buildbot.db.buildslave.BuildslavesConnectorComponent.buildslaveConfigured`
       method positional argument ``buildslaveid`` was renamed
     - ``workerid``

Other changes:

* Functions argument ``buildslaveName`` renamed to ``workerName``.

* ``s`` and ``sl`` loops variables were renamed to ``worker`` or ``w``;
  ``sb`` to ``wfb``.

* In :py:meth:`buildbot.config.BuilderConfig.getConfigDict` result
  ``'slavenames'`` key changed to ``'workernames'``;
  ``'slavebuilddir'`` key changed to ``'workerbuilddir'``;
  ``'nextSlave'`` key changed to ``'nextWorker'``.

* :py:meth:`buildbot.process.builder.BuilderControl.ping` now generates
  ``["ping", "no worker"]`` event, instead of ``["ping", "no slave"]``.

* ``buildbot.plugins.util.WorkerChoiceParameter``
  (previously ``BuildslaveChoiceParameter``) label was changed from
  ``Build slave`` to ``Worker``.

* ``buildbot.plugins.util.WorkerChoiceParameter``
  (previously ``BuildslaveChoiceParameter``) default name was changed from
  ``slavename`` to ``workername``.

* ``buildbot.status.builder.SlaveStatus`` fallback was removed.
  ``SlaveStatus`` was moved to ``buildbot.status.builder.slave`` previously,
  and now it's :py:class:`buildbot.status.worker.WorkerStatus`.

* :py:mod:`buildbot.status.status_push.StatusPush` events generation changed:

  - instead of ``slaveConnected`` with data ``slave=...`` now generated
    ``workerConnected`` event with data ``worker=...``;

  - instead of ``slaveDisconnected`` with data ``slavename=...`` now generated
    ``workerDisconnected`` with data ``workername=...``;

  - instead of ``slavePaused`` with data ``slavename=...`` now generated
    ``workerPaused`` event with data ``workername=...``;

  - instead of ``slaveUnpaused`` with data ``slavename=...`` now generated
    ``workerUnpaused`` event with data ``workername=...``;

* :py:meth:`buildbot.status.build.BuildStatus.asDict` returns worker name under
  ``'worker'`` key, instead of ``'slave'`` key.

* :py:meth:`buildbot.status.builder.BuilderStatus.asDict` returns worker
  names under ``'workers'`` key, instead of ``'slaves'`` key.

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

* ``builddir`` property source changed from ``"slave"`` to ``"worker"``;
  ``workdir`` property source from ``"slave (deprecated)"`` to
  ``"worker (deprecated)"``.

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
