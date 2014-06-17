BuildslaveManager
=================

.. py:module:: buildbot.buildslave.manager

BuildslaveRegistration
----------------------

.. py:class:: BuildslaveRegistration(master, buildslave)

    Represents single BuildSlave registration

    .. py:method:: unregister()

        Remove registartion for `buildslave`

    .. py:method:: update(slave_config, global_config)

        :param slave_config: new BuildSlave instance
        :type slave_config: :class:`~buildbot.buildslave.base.BuildSlave`
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
        :type slave_config: :class:`~buildbot.buildslave.base.BuildSlave`
        :returns: :class:`~buildbot.buildslave.manager.BuildslaveRegistration`

        Creates :class:`~buildbot.buildslave.manager.BuildslaveRegistration`
        instance.

        NOTE: You should invoke `.update()` on returned BuildslaveRegistration
        instance
