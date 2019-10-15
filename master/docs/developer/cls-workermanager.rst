WorkerManager
=============

.. py:module:: buildbot.worker.manager

WorkerRegistration
------------------

.. py:class:: WorkerRegistration(master, worker)

    Represents single Worker registration

    .. py:method:: unregister()

        Remove registration for `worker`

    .. py:method:: update(worker_config, global_config)

        :param worker_config: new Worker instance
        :type worker_config: :class:`~buildbot.worker.Worker`
        :param global_config: Buildbot config
        :type global_config: :class:`~buildbot.config.MasterConfig`

        Update the registration in case the port or password has changed.

        NOTE: You should invoke this method after calling
        `WorkerManager.register(worker)`

WorkerManager
-------------

.. py:class:: WorkerManager(master)

    Handle Worker registrations for multiple protocols

    .. py:method:: register(worker)

        :param worker: new Worker instance
        :type worker: :class:`~buildbot.worker.Worker`
        :returns: :class:`~buildbot.worker.manager.WorkerRegistration`

        Creates :class:`~buildbot.worker.manager.WorkerRegistration`
        instance.

        NOTE: You should invoke `.update()` on returned WorkerRegistration
        instance
