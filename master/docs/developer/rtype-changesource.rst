ChangeSource
============

.. bb:rtype:: changesource

    :attr integer changesourceid: the ID of this changesource
    :attr string name: name of this changesource
    :attr master master: the master on which this slave is running, or None if it is inactive

    A changesource generates change objects, for example in response to an update in some
    repository. A particular changesource (by name) runs on at most one master at a time.

    .. bb:rpath:: /changesource

        This path selects all changesources.

    .. bb:rpath:: /master/:masterid/changesource

        :pathkey integer masterid: the ID of the master

        This path selects all changesources running on the given master.

    .. bb:rpath:: /changesource/:changesourceid

        :pathkey integer changesourceid: the ID of the changesource

        This path selects a specific changesource, identified by ID.

    .. bb:rpath:: /master/:masterid/changesource/:changesourceid

        :pathkey integer masterid: the ID of the master
        :pathkey integer changesourceid: the ID of the changesource

        This path selects a changesource, identified by ID.
        If the changesource is not running on the given master, this path returns nothing.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.changes.ChangeSourceResourceType

    .. py:method:: findChangeSourceId(name)

        :param string name: changesource name
        :returns: changesource ID via Deferred

        Get the ID for the given changesource name, inventing one if necessary.

    .. py:method:: trySetChangeSourceMaster(changesourceid, masterid)

        :param integer changesourceid: changesource ID to try to claim
        :param integer masterid: this master's master ID
        :returns: ``True`` or ``False``, via Deferred

        Try to claim the given scheduler for the given master and return ``True`` if
        the scheduler is to be activated on that master.
