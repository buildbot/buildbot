BuildworkerManager
==================

.. py:module:: buildbot.buildworker.manager

BuildworkerRegistration
-----------------------

.. py:class:: BuildworkerRegistration(master, buildworker)

    Represents single BuildWorker registration

    .. py:method:: unregister()

        Remove registartion for `buildworker`

    .. py:method:: update(worker_config, global_config)

        :param worker_config: new BuildWorker instance
        :type worker_config: :class:`~buildbot.buildworker.base.BuildWorker`
        :param global_config: Buildbot config
        :type global_config: :class:`~buildbot.config.MasterConfig`

        Update the registration in case the port or password has changed.

        NOTE: You should invoke this method after calling
        `BuildworkerManager.register(buildworker)`

BuildworkerManager
------------------

.. py:class:: BuildworkerManager(master)

    Handle BuildWorker registrations for mulitple protocols

    .. py:method:: register(buildworker)

        :param worker_config: new BuildWorker instance
        :type worker_config: :class:`~buildbot.buildworker.base.BuildWorker`
        :returns: :class:`~buildbot.buildworker.manager.BuildworkerRegistration`

        Creates :class:`~buildbot.buildworker.manager.BuildworkerRegistration`
        instance.

        NOTE: You should invoke `.update()` on returned BuildworkerRegistration
        instance
