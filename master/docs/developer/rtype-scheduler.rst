Scheduler
=========

.. bb:rtype:: scheduler

    :attr integer schedulerid: the ID of this scheduler
    :attr string name: name of this scheduler
    :attr master master: the master on which this scheduler is running, or None if it is inactive

    A scheduler initiates builds, often in response to changes from change sources.
    A particular scheduler (by name) runs on at most one master at a time.

    .. bb:rpath:: /scheduler

        This path selects all schedulers.

    .. bb:rpath:: /master/:masterid/scheduler

        :pathkey integer masterid: the ID of the master

        This path selects all schedulers running on the given master.

    .. bb:rpath:: /scheduler/:schedulerid

        :pathkey integer schedulerid: the ID of the scheduler

        This path selects a specific scheduler, identified by ID.

    .. bb:rpath:: /master/:masterid/scheduler/:schedulerid

        :pathkey integer masterid: the ID of the master
        :pathkey integer schedulerid: the ID of the scheduler

        This path selects a scheduler, identified by ID.
        If the scheduler is not running on the given master, this path returns nothing.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.schedulers.SchedulerResourceType

    .. py:method:: findSchedulerId(name)

        :param string name: scheduler name
        :returns: scheduler ID via Deferred

        Get the ID for the given scheduler name, inventing one if necessary.

    .. py:method:: trySetSchedulerMaster(schedulerid, masterid)

        :param integer schedulerid: scheduler ID to try to claim
        :param integer masterid: this master's master ID
        :returns: ``True`` or ``False``, via Deferred

        Try to claim the given scheduler for the given master and return ``True`` if
        the scheduler is to be activated on that master.
