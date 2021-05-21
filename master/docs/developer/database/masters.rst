Masters connector
~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.masters

.. index:: double: Masters; DB Connector Component

.. py:class:: MastersConnectorComponent

    This class handles tracking the buildmasters in a multi-master configuration.
    Masters "check in" periodically.
    Other masters monitor the last activity times, and mark masters that have not recently checked in as inactive.

    Masters are represented by master dictionaries with the following keys:

    * ``id`` -- the ID of this master
    * ``name`` -- the name of the master (generally of the form ``hostname:basedir``)
    * ``active`` -- true if this master is running
    * ``last_active`` -- time that this master last checked in (a datetime object)

    .. py:method:: findMasterId(name)

        :param unicode name: name of this master
        :returns: master id via Deferred

        Return the master ID for the master with this master name (generally ``hostname:basedir``).
        If such a master is already in the database, this returns the ID.
        If not, the master is added to the database, with ``active=False``, and its ID returned.

    .. py:method:: setMasterState(masterid, active)

        :param integer masterid: the master to check in
        :param boolean active: whether to mark this master as active or inactive
        :returns: boolean via Deferred

        Mark the given master as active or inactive, returning true if the state actually changed.
        If ``active`` is true, the ``last_active`` time is updated to the current time.
        If ``active`` is false, then any links to this master, such as schedulers, will be deleted.

    .. py:method:: getMaster(masterid)

        :param integer masterid: the master to check in
        :returns: Master dict or None via Deferred

        Get the indicated master.

    .. py:method:: getMasters()

        :returns: list of Master dicts via Deferred

        Get a list of the masters, represented as dictionaries; masters are sorted
        and paged using generic data query options

    .. py:method:: setAllMastersActiveLongTimeAgo()

        :returns: None via Deferred

        This method is intended to be called by upgrade-master, and will effectively force housekeeping on all masters at next startup.
        This method is not intended to be called outside of housekeeping scripts.
