Configuration
=============

.. py:module:: buildbot.config

Wherever possible, Buildbot components should access configuration information
as needed from the canonical source, ``master.config``, which is an instance of
:py:class:`MasterConfig`.  For example, components should not keep a copy of
the ``buildbotURL`` locally, as this value may change throughout the lifetime
of the master.

Components which need to be notified of changes in the configuration should be
implemented as services, subclassing :py:class:`ReconfigurableServiceMixin`, as
described in :ref:`developer-Reconfiguration`.

.. py:class:: MasterConfig

    The master object makes much of the configuration available from an object
    named ``master.config``.  Configuration is stored as attributes of this
    object.  Where possible, other Buildbot components should access this
    configuration directly and not cache the configuration values anywhere
    else.  This avoids the need to ensure that update-from-configuration
    methods are called on a reconfig.

    Aside from validating the configuration, this class handles any
    backward-compatibility issues - renamed parameters, type changes, and so on
    - removing those concerns from other parts of Buildbot.

    This class may be instantiated directly, creating an entirely default
    configuration, or via :py:meth:`loadConfig`, which will load the
    configuration from a config file.

    The following attributes are available from this class, representing the
    current configuration.  This includes a number of global parameters:

    .. py:attribute:: title

        The title of this buildmaster, from :bb:cfg:`title`.

    .. py:attribute:: titleURL

        The URL corresponding to the title, from :bb:cfg:`titleURL`.

    .. py:attribute:: buildbotURL

        The URL of this buildmaster, for use in constructing WebStatus URLs;
        from :bb:cfg:`buildbotURL`.

    .. py:attribute:: changeHorizon

        The current change horizon, from :bb:cfg:`changeHorizon`.

    .. py:attribute:: eventHorizon

        The current event horizon, from :bb:cfg:`eventHorizon`.

    .. py:attribute:: logHorizon

        The current log horizon, from :bb:cfg:`logHorizon`.

    .. py:attribute:: buildHorizon

        The current build horizon, from :bb:cfg:`buildHorizon`.

    .. py:attribute:: logCompressionLimit

        The current log compression limit, from :bb:cfg:`logCompressionLimit`.

    .. py:attribute:: logCompressionMethod

        The current log compression method, from
        :bb:cfg:`logCompressionMethod`.

    .. py:attribute:: logMaxSize

        The current log maximum size, from :bb:cfg:`logMaxSize`.

    .. py:attribute:: logMaxTailSize

        The current log maximum size, from :bb:cfg:`logMaxTailSize`.

    .. py:attribute:: properties

        A :py:class:`~buildbot.process.properties.Properties` instance
        containing global properties, from :bb:cfg:`properties`.

    .. py:attribute:: mergeRequests

        A callable, or True or False, describing how to merge requests; from
        :bb:cfg:`mergeRequests`.

    .. py:attribute:: prioritizeBuilders

        A callable, or None, used to prioritize builders; from
        :bb:cfg:`prioritizeBuilders`.

    .. py:attribute:: codebaseGenerator
    
        A callable, or None, used to determine the codebase from an incoming 
        :py:class:`~buildbot.changes.changes.Change`,
        from :bb:cfg:`codebaseGenerator`
        
    .. py:attribute:: protocols

        The per-protocol port specification for slave connections.
        Based on :bb:cfg:`protocols`.

    .. py:attribute:: multiMaster

        If true, then this master is part of a cluster; based on
        :bb:cfg:`multiMaster`.

    .. py:attribute:: debugPassword

        The password for the debug client, or None; from
        :bb:cfg:`debugPassword`.

    .. py:attribute:: manhole

        The manhole instance to use, or None; from :bb:cfg:`manhole`.

    The remaining attributes contain compound configuration structures, usually
    dictionaries:

    .. py:attribute:: validation

        Validation regular expressions, a dictionary from :bb:cfg:`validation`.
        It is safe to assume that all expected keys are present.

    .. py:attribute:: db

        Database specification, a dictionary with keys :bb:cfg:`db_url` and
        :bb:cfg:`db_poll_interval`.  It is safe to assume that both keys are
        present.

    .. py:attribute:: metrics

        The metrics configuration from :bb:cfg:`metrics`, or an empty
        dictionary by default.

    .. py:attribute:: caches

        The cache configuration, from :bb:cfg:`caches` as well as the
        deprecated :bb:cfg:`buildCacheSize` and :bb:cfg:`changeCacheSize`
        parameters.

        The keys ``Builds`` and ``Caches`` are always available; other keys
        should use ``config.caches.get(cachename, 1)``.

    .. py:attribute:: schedulers

        The dictionary of scheduler instances, by name, from :bb:cfg:`schedulers`.

    .. py:attribute:: builders

        The list of :py:class:`BuilderConfig` instances from
        :bb:cfg:`builders`.  Builders specified as dictionaries in the
        configuration file are converted to instances.

    .. py:attribute:: slaves

        The list of :py:class:`BuildSlave` instances from
        :bb:cfg:`slaves`.

    .. py:attribute:: change_sources

        The list of :py:class:`IChangeSource` providers from
        :bb:cfg:`change_source`.

    .. py:attribute:: status

        The list of :py:class:`IStatusReceiver` providers from
        :bb:cfg:`status`.

    .. py:attribute:: user_managers

        The list of user managers providers from :bb:cfg:`user_managers`.

    Loading of the configuration file is generally triggered by the master,
    using the following methods:

    .. py:classmethod:: loadConfig(basedir, filename)

        :param string basedir: directory to which config is relative
        :param string filename: the configuration file to load
        :raises: :py:exc:`ConfigErrors` if any errors occur
        :returns: new :py:class:`MasterConfig` instance

        Load the configuration in the given file.  Aside from syntax errors,
        this will also detect a number of semantic errors such as multiple
        schedulers with the same name.

        The filename is treated as relative to the basedir, if it is not
        absolute.

Builder Configuration
---------------------

.. py:class:: BuilderConfig([keyword args])

    This class parameterizes configuration of builders; see
    :ref:`Builder-Configuration` for its arguments.  The constructor checks for
    errors and applies defaults, and sets the properties described here.  Most
    are simply copied from the constructor argument of the same name.

    Users may subclass this class to add defaults, for example.

    .. py:attribute:: name

        The builder's name.

    .. py:attribute:: factory

        The builder's factory.

    .. py:attribute:: slavenames

        The builder's slave names (a list, regardless of whether the names were
        specified with ``slavename`` or ``slavenames``).

    .. py:attribute:: builddir

        The builder's builddir.

    .. py:attribute:: slavebuilddir

        The builder's slave-side builddir.

    .. py:attribute:: category

        The builder's category.

    .. py:attribute:: nextSlave

        The builder's nextSlave callable.

    .. py:attribute:: nextBuild

        The builder's nextBuild callable.

    .. py:attribute:: canStartBuild

        The builder's canStartBuild callable.

    .. py:attribute:: locks

        The builder's locks.

    .. py:attribute:: env

        The builder's environmnet variables.

    .. py:attribute:: properties

        The builder's properties, as a dictionary.

    .. py:attribute:: mergeRequests

        The builder's mergeRequests callable.

    .. py:attribute:: description

        The builder's description, displayed in the web status.

Error Handling
--------------

If any errors are encountered while loading the configuration :py:func:`buildbot.config.error`
should be called. This can occur both in the configuration-loading code,
and in the constructors of any objects that are instantiated in the
configuration - change sources, slaves, schedulers, build steps, and so on.

.. py:function:: error(error)

    :param error: error to report
    :raises: :py:exc:`ConfigErrors` if called at build-time

    This function reports a configuration error. If a config file is being loaded,
    then the function merely records the error, and allows the rest of the configuration
    to be loaded. At any other time, it raises :py:exc:`ConfigErrors`.  This is done
    so all config errors can be reported, rather than just the first.

.. py:exception:: ConfigErrors([errors])

    :param list errors: errors to report

    This exception represents errors in the configuration.  It supports
    reporting multiple errors to the user simultaneously, e.g., when several
    consistency checks fail.

    .. py:attribute:: errors

        A list of detected errors, each given as a string.

    .. py:method:: addError(msg)

        :param string msg: the message to add

        Add another error message to the (presumably not-yet-raised) exception.


.. _developer-Reconfiguration:

Reconfiguration
---------------

When the buildmaster receives a signal to begin a reconfig, it re-reads the
configuration file, generating a new :py:class:`MasterConfig` instance, and
then notifies all of its child services via the reconfig mechanism described
below.  The master ensures that at most one reconfiguration is taking place at
any time.

See :ref:`master-service-hierarchy` for the structure of the Buildbot service
tree.

To simplify initialization, a reconfiguration is performed immediately on
master startup.  As a result, services only need to implement their
configuration handling once, and can use ``startService`` for initialization.

See below for instructions on implementing configuration of common types of
components in Buildbot.

.. note::

    Because Buildbot uses a pure-Python configuration file, it is not possible
    to support all forms of reconfiguration.  In particular, when the
    configuration includes custom subclasses or modules, reconfiguration can
    turn up some surprising behaviors due to the dynamic nature of Python.  The
    reconfig support in Buildbot is intended for "intermediate" uses of the
    software, where there are fewer surprises.

Reconfigurable Services
.......................

Instances which need to be notified of a change in configuration should be
implemented as Twisted services, and mix in the
:py:class:`ReconfigurableServiceMixin` class, overriding the
:py:meth:`~ReconfigurableServiceMixin.reconfigService` method.

.. py:class:: ReconfigurableServiceMixin

    .. py:method:: reconfigService(new_config)

        :param new_config: new master configuration
        :type new_config: :py:class:`MasterConfig`
        :returns: Deferred

        This method notifies the service that it should make any changes
        necessary to adapt to the new configuration values given.

        This method will be called automatically after a service is started.

        It is generally too late at this point to roll back the
        reconfiguration, so if possible any errors should be detected in the
        :py:class:`MasterConfig` implementation.  Errors are handled as best as
        possible and communicated back to the top level invocation, but such
        errors may leave the master in an inconsistent state.
        :py:exc:`ConfigErrors` exceptions will be displayed appropriately to
        the user on startup.

        Subclasses should always call the parent class's implementation. For
        :py:class:`MultiService` instances, this will call any child services'
        :py:meth:`reconfigService` methods, as appropriate.  This will be done
        sequentially, such that the Deferred from one service must fire before
        the next service is reconfigured.

    .. py:attribute:: priority

        Child services are reconfigured in order of decreasing priority.  The
        default priority is 128, so a service that must be reconfigured before
        others should be given a higher priority.


Change Sources
..............

When reconfiguring, there is no method by which Buildbot can determine that a
new :py:class:`~buildbot.changes.base.ChangeSource` represents the same source
as an existing :py:class:`~buildbot.changes.base.ChangeSource`, but with
different configuration parameters.  As a result, the change source manager
compares the lists of existing and new change sources using equality, stops any
existing sources that are not in the new list, and starts any new change
sources that do not already exist.

:py:class:`~buildbot.changes.base.ChangeSource` inherits
:py:class:`~buildbot.util.ComparableMixin`, so change sources are compared
based on the attributes described in their ``compare_attrs``.

If a change source does not make reference to any global configuration
parameters, then there is no need to inherit
:py:class:`ReconfigurableServiceMixin`, as a simple comparison and
``startService`` and ``stopService`` will be sufficient.

If the change source does make reference to global values, e.g., as default
values for its parameters, then it must inherit
:py:class:`ReconfigurableServiceMixin` to support the case where the global
values change.


Schedulers
..........

Schedulers have names, so Buildbot can determine whether a scheduler has been
added, removed, or changed during a reconfig.  Old schedulers will be stopped,
new schedulers will be started, and both new and existing schedulers will see a
call to :py:meth:`~ReconfigurableServiceMixin.reconfigService`, if such a
method exists.  For backward compatibility, schedulers which do not support
reconfiguration will be stopped, and the new scheduler started, when their
configuration changes.

If, during a reconfiguration, a new and old scheduler's fully qualified class
names differ, then the old class will be stopped and the new class started.
This supports the case when a user changes, for example, a Nightly scheduler to
a Periodic scheduler without changing the name.

Because Buildbot uses :py:class:`~buildbot.schedulers.base.BaseScheduler`
instances directly in the configuration file, a reconfigured scheduler must
extract its new configuration information from another instance of itself.
:py:class:`~buildbot.schedulers.base.BaseScheduler` implements a helper method,
:py:meth:`~buildbot.schedulers.base.BaseScheduler.findNewSchedulerInstance`,
which will return the new instance of the scheduler in the given
:py:class:`MasterConfig` object.


Custom Subclasses
~~~~~~~~~~~~~~~~~

Custom subclasses are most often defined directly in the configuration file, or
in a Python module that is reloaded with ``reload`` every time the
configuration is loaded.  Because of the dynamic nature of Python, this creates
a new object representing the subclass every time the configuration is loaded
-- even if the class definition has not changed.

Note that if a scheduler's class changes in a reconfig, but the scheduler's
name does not, it will still be treated as a reconfiguration of the existing
scheduler.  This means that implementation changes in custom scheduler
subclasses will not be activated with a reconfig.  This behavior avoids
stopping and starting such schedulers on every reconfig, but can make
development difficult.

One workaround for this is to change the name of the scheduler before each
reconfig - this will cause the old scheduler to be stopped, and the new
scheduler (with the new name and class) to be started.

Slaves
......

Similar to schedulers, slaves are specified by name, so new and old
configurations are first compared by name, and any slaves to be added or
removed are noted.  Slaves for which the fully-qualified class name has changed
are also added and removed.  All slaves have their
:py:meth:`~ReconfigurableServiceMixin.reconfigService` method called.

This method takes care of the basic slave attributes, including changing the PB
registration if necessary.  Any subclasses that add configuration parameters
should override :py:meth:`~ReconfigurableServiceMixin.reconfigService` and
update those parameters.  As with Schedulers, because the
:py:class:`~buildbot.buildslave.AbstractBuildSlave` instance is given directly
in the configuration, on reconfig instances must extract the configuration from
a new instance.  The
:py:meth:`~buildbot.buildslave.AbstractBuildSlave.findNewSlaveInstance` method
can be used to find the new instance.

User Managers
.............

Since user managers are rarely used, and their purpose is unclear, they are
always stopped and re-started on every reconfig.  This may change in figure
versions.

Status Receivers
................

At every reconfig, all status listeners are stopped and new versions started.


