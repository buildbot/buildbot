.. index:: single: Configurator; IConfigurator

IConfigurator
=============

.. class:: buildbot.interfaces.IConfigurator

    A configurator is an object which configures several components of Buildbot in a coherent manner.
    This can be used to implement higher level configuration tools.

    .. method:: configure(config_dict)

        Alter the Buildbot ``config_dict``, as defined in master.cfg.

        Like master.cfg, this is run out of the main reactor thread, so this can block, but it can't
        call most Buildbot facilities.
