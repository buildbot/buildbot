Buildbot Configuration
======================

Access to Configuration
-----------------------

The master object makes much of the configuration available from an object
named ``master.config``.  Configuration is stored as attributes of this
object.  Where possible, components should access this configuration directly
and not cache the configuration values anywhere else.  This avoids the need to
ensure that update-from-configuration methods are called on a reconfig.

The available attributes are listed in the docstring for the
:class:`buildbot.config.MasterConfig` class.
