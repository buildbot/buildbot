Master Organization
===================

Buildmaster Service Hierarchy
-----------------------------

Buildbot uses Twisted's service hierarchy heavily.  The hierarchy looks like
this:

.. py:class:: buildbot.master.BuildMaster

    This is the top-level service.

    .. py:class:: buildbot.master.BotMaster

        The :class:`BotMaster` manages all of the slaves.  :class:`BuildSlave` instances are added as
        child services of the :class:`BotMaster`.

    .. py:class:: buildbot.changes.manager.ChangeManager

        The :class:`ChangeManager` manages the active change sources, as well as the stream of
        changes received from those sources.

    .. py:class:: buildbot.schedulers.manager.SchedulerManager

        The :class:`SchedulerManager` manages the active schedulers and handles inter-scheduler
        notifications.

    :class:`IStatusReceiver` implementations
        Objects from the ``status`` configuration key are attached directly to the
        buildmaster. These classes should inherit from :class:`StatusReceiver` or
        :class:`StatusReceiverMultiService` and include an
        ``implements(IStatusReceiver)`` stanza.



