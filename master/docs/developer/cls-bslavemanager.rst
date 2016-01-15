BuildslaveManager
=================

.. py:module:: buildbot.buildslave.manager

BuildslaveRegistration
----------------------

.. py:class:: BuildslaveRegistration(master, buildslave)

    Represents single BuildSlave registration

    .. py:method:: unregister()

        Remove registartion for `buildslave`

    .. py:method:: update(worker_config, global_config)

        :param worker_config: new BuildSlave instance
        :type worker_config: :class:`~buildbot.worker.Worker`
        :param global_config: Buildbot config
        :type global_config: :class:`~buildbot.config.MasterConfig`

        Update the registration in case the port or password has changed.

        NOTE: You should invoke this method after calling
        `BuildslaveManager.register(buildslave)`

BuildslaveManager
-----------------

.. py:class:: BuildslaveManager(master)

    Handle BuildSlave registrations for mulitple protocols

    .. py:method:: register(buildslave)

        :param slave_config: new BuildSlave instance
        :type slave_config: :class:`~buildbot.worker.Worker`
        :returns: :class:`~buildbot.buildslave.manager.BuildslaveRegistration`

        Creates :class:`~buildbot.buildslave.manager.BuildslaveRegistration`
        instance.

        NOTE: You should invoke `.update()` on returned BuildslaveRegistration
        instance
