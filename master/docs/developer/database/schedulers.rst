Schedulers connector
~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.schedulers

.. index:: double: Schedulers; DB Connector Component

.. py:exception:: SchedulerAlreadyClaimedError

    Raised when a scheduler request is already claimed by another master.

.. py:class:: SchedulersConnectorComponent

    This class manages the state of the Buildbot schedulers.  This state includes
    classifications of as-yet un-built changes.

    An instance of this class is available at ``master.db.schedulers``.

    Schedulers are identified by their schedulerid, which can be obtained from :py:meth:`findSchedulerId`.

    Schedulers are represented by dictionaries with the following keys:

        * ``id`` - scheduler's ID
        * ``name`` - scheduler's name
        * ``masterid`` - ID of the master currently running this scheduler, or None if it is inactive

    Note that this class is conservative in determining what schedulers are inactive: a scheduler linked to an inactive master is still considered active.
    This situation should never occur, however; links to a master should be deleted when it is marked inactive.

    .. py:method:: classifyChanges(objectid, classifications)

        :param schedulerid: ID of the scheduler classifying the changes
        :param classifications: mapping of changeid to boolean, where the boolean
            is true if the change is important, and false if it is unimportant
        :type classifications: dictionary
        :returns: Deferred

        Record the given classifications.  This method allows a scheduler to
        record which changes were important and which were not immediately,
        even if the build based on those changes will not occur for some time
        (e.g., a tree stable timer).  Schedulers should be careful to flush
        classifications once they are no longer needed, using
        :py:meth:`flushChangeClassifications`.

    .. py:method:: flushChangeClassifications(objectid, less_than=None)

        :param schedulerid: ID of the scheduler owning the flushed changes
        :param less_than: (optional) lowest changeid that should *not* be flushed
        :returns: Deferred

        Flush all scheduler_changes for the given scheduler, limiting to those
        with changeid less than ``less_than`` if the parameter is supplied.

    .. py:method:: getChangeClassifications(objectid[, branch])

        :param schedulerid: ID of scheduler to look up changes for
        :type schedulerid: integer
        :param branch: (optional) limit to changes with this branch
        :type branch: string or None (for default branch)
        :returns: dictionary via Deferred

        Return the classifications made by this scheduler, in the form of a
        dictionary mapping changeid to a boolean, just as supplied to
        :py:meth:`classifyChanges`.

        If ``branch`` is specified, then only changes on that branch will be
        given.  Note that specifying ``branch=None`` requests changes for the
        default branch, and is not the same as omitting the ``branch`` argument
        altogether.

    .. py:method:: findSchedulerId(name)

        :param name: scheduler name
        :returns: scheduler ID via Deferred

        Return the scheduler ID for the scheduler with this name.
        If such a scheduler is already in the database, this returns the ID.
        If not, the scheduler is added to the database and its ID is returned.

    .. py:method:: setSchedulerMaster(schedulerid, masterid)

        :param schedulerid: scheduler to set the master for
        :param masterid: new master for this scheduler, or None
        :returns: Deferred

        Set, or unset if ``masterid`` is None, the active master for this scheduler.
        If no master is currently set, or the current master is not active, this method will complete without error.
        If the current master is active, this method will raise :py:exc:`~buildbot.db.exceptions.SchedulerAlreadyClaimedError`.

    .. py:method:: getScheduler(schedulerid)

        :param schedulerid: scheduler ID
        :returns: scheduler dictionary or None via Deferred

        Get the scheduler dictionary for the given scheduler.

    .. py:method:: getSchedulers(active=None, masterid=None)

        :param boolean active: if specified, filter for active or inactive schedulers
        :param integer masterid: if specified, only return schedulers attached associated with this master
        :returns: list of scheduler dictionaries in unspecified order

        Get a list of schedulers.

        If ``active`` is given, schedulers are filtered according to whether they are active (true) or inactive (false).
        An active scheduler is one that is claimed by an active master.

        If ``masterid`` is given, the list is restricted to schedulers associated with that master.

