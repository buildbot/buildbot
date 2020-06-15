Change sources connector
~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.changesources

.. index:: double: ChangeSources; DB Connector Component

.. py:exception:: ChangeSourceAlreadyClaimedError

    Raised when a changesource request is already claimed by another master.

.. py:class:: ChangeSourcesConnectorComponent

    This class manages the state of the Buildbot changesources.

    An instance of this class is available at ``master.db.changesources``.

    Changesources are identified by their changesourceid, which can be obtained from :py:meth:`findChangeSourceId`.

    Changesources are represented by dictionaries with the following keys:

        * ``id`` - changesource's ID
        * ``name`` - changesource's name
        * ``masterid`` - ID of the master currently running this changesource, or None if it is inactive

    Note that this class is conservative in determining what changesources are inactive: a changesource linked to an inactive master is still considered active.
    This situation should never occur, however; links to a master should be deleted when it is marked inactive.

    .. py:method:: findChangeSourceId(name)

        :param name: changesource name
        :returns: changesource ID via Deferred

        Return the changesource ID for the changesource with this name.
        If such a changesource is already in the database, this returns the ID.
        If not, the changesource is added to the database and its ID returned.

    .. py:method:: setChangeSourceMaster(changesourceid, masterid)

        :param changesourceid: changesource to set the master for
        :param masterid: new master for this changesource, or None
        :returns: Deferred

        Set, or unset if ``masterid`` is None, the active master for this changesource.
        If no master is currently set, or the current master is not active, this method will complete without error.
        If the current master is active, this method will raise :py:exc:`~buildbot.db.exceptions.ChangeSourceAlreadyClaimedError`.

    .. py:method:: getChangeSource(changesourceid)

        :param changesourceid: changesource ID
        :returns: changesource dictionary or None, via Deferred

        Get the changesource dictionary for the given changesource.

    .. py:method:: getChangeSources(active=None, masterid=None)

        :param boolean active: if specified, filter for active or inactive changesources
        :param integer masterid: if specified, only return changesources attached associated with this master
        :returns: list of changesource dictionaries in unspecified order

        Get a list of changesources.

        If ``active`` is given, changesources are filtered according to whether they are active (true) or inactive (false).
        An active changesource is one that is claimed by an active master.

        If ``masterid`` is given, the list is restricted to schedulers associated with that master.
