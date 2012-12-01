.. _master-service-hierarchy:

Master Organization
===================

Buildbot makes heavy use of Twisted Python's support for services - software
modules that can be started and stopped dynamically.  Buildbot adds the ability
to reconfigure such services, too - see :ref:`developer-reconfiguration`.
Twisted arranges services into trees; the following section describes the
service tree on a running master.

Buildmaster Service Hierarchy
-----------------------------

The hierarchy begins with the master, a :py:class:`buildbot.master.BuildMaster`
instance.  Most other services contain a reference to this object in their
``master`` attribute, and in general the appropriate way to access other
objects or services is to begin with ``self.master`` and navigate from there.

The master has several child services:

``master.metrics``
    A :py:class:`buildbot.process.metrics.MetricLogObserver` instance that
    handles tracking and reporting on master metrics.

``msater.caches``
    A :py:class:`buildbot.process.caches.CacheManager` instance that provides
    access to object caches.

``master.pbmanager``
    A :py:class:`buildbot.pbmanager.PBManager` instance that handles incoming
    PB connections, potentially on multiple ports, and dispatching those
    connections to appropriate components based on the supplied username.

``master.change_svc``
    A :py:class:`buildbot.changes.manager.ChangeManager` instance that manages
    the active change sources, as well as the stream of changes received from
    those sources.  All active change sources are child services of this instance.

``master.botmaster``
    A :py:class:`buildbot.process.botmaster.BotMaster` instance that manages
    all of the slaves and builders as child services.

    The botmaster acts as the parent service for a
    :py:class:`buildbot.process.botmaster.BuildRequestDistributor` instance (at
    ``master.botmaster.brd``) as well as all active slaves
    (:py:class:`buildbot.buildslave.AbstractBuildSlave` instances) and builders
    (:py:class:`buildbot.process.builder.Builder` instances).

``master.scheduler_manager``
    A :py:class:`buildbot.schedulers.manager.SchedulerManager` instance that
    manages the active schedulers.  All active schedulers are child services of
    this instance.

``master.user_manager``
    A :py:class:`buildbot.process.users.manager.UserManagerManager` instance
    that manages access to users.  All active user managers are child services
    of this instance.

``master.db``
    A :py:class:`buildbot.db.connector.DBConnector` instance that manages
    access to the buildbot database.  See :ref:`developer-database` for more
    information.

``master.debug``
    A :py:class:`buildbot.process.debug.DebugServices` instance that manages
    debugging-related access -- the debug client and manhole.

``master.status``
    A :py:class:`buildbot.status.master.Status` instance that provides access
    to all status data.  This instance is also the service parent for all
    status listeners.
