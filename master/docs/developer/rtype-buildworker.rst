Buildworkers
============

.. bb:rtype:: buildworker

    :attr integer buildworkerid: the ID of this buildworker
    :attr name: the name of the buildworker
    :type name: 50-character identifier
    :attr connected_to: list of masters this buildworker is attached to
    :type connected_to: list of objects with keys ``masterid`` and ``link``
    :attr configured_on: list of builders on masters this buildworker is configured on
    :type configured_on: list of objects with keys ``masterid``, ``builderid``, and ``link``
    :attr workerinfo: information about the worker
    :type workerinfo: dictionary

    The contents of the ``connected_to`` and ``configured_on`` attributes are sensitive to the context of the request.
    If a builder or master is specified in the path, then only the corresponding connections and configurations are included in the result.

    The buildworker information can be any JSON-able object.
    In practice, it contains the following keys, based on information provided by the worker:

    * ``admin`` (the admin information)
    * ``host`` (the name of the host)
    * ``access_uri`` (the access URI)
    * ``version`` (the version on the buildworker)

    A buildworker resource represents a buildworker to the source code monitored by Buildbot.

    .. bb:event:: buildworker.$buildworkerid.connected

        The buildworker has connected to a master.

    .. bb:event:: buildworker.$buildworkerid.disconnected

        The buildworker has disconnected from a master.

    .. bb:rpath:: /buildworker

        This path lists all buildworkers.

    .. bb:rpath:: /buildworker/i:name

        :pathkey integer name: the name of the buildworker

        This path selects a specific buildworker, identified by name.

    .. bb:rpath:: /buildworker/n:buildworkerid

        :pathkey integer buildworkerid: the ID of the buildworker

        This path selects a specific buildworker, identified by ID.

    .. bb:rpath:: /builder/n:builderid/buildworker

        :pathkey integer builderid: the ID of the builder filtering the results

        This path lists all buildworkers configured on the given builder on any master.

    .. bb:rpath:: /builder/n:builderid/buildworker/i:name

        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer name: the name of the buildworker

        This path returns the named buildworker, if it is configured on the given builder on any master.

    .. bb:rpath:: /builder/n:builderid/buildworker/n:buildworkerid

        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer buildworkerid: the ID of the buildworker

        This path returns the identified buildworker, if it is configured on the given builder on any master.

    .. bb:rpath:: /master/n:masterid/builder/n:builderid/buildworker

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer builderid: the ID of the builder filtering the results

        This path lists all buildworkers configured on the given builder on the given master.

    .. bb:rpath:: /master/n:masterid/builder/n:builderid/buildworker/i:name

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer name: the name of the buildworker

        This path returns the named buildworker, if it is configured on the given builder on the given master.

    .. bb:rpath:: /master/n:masterid/builder/n:builderid/buildworker/n:buildworkerid

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer buildworkerid: the ID of the buildworker

        This path returns the given buildworker, if it is configured on the given builder on the given master.

    .. bb:rpath:: /master/n:masterid/buildworker

        :pathkey integer masterid: the ID of the master filtering the results

        This path lists all buildworkers configured on the any builder on the given master.

    .. bb:rpath:: /master/n:masterid/buildworker/i:name

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer name: the name of the buildworker

        This path returns the named buildworker, if it is configured on the any builder on the given master.

    .. bb:rpath:: /master/n:masterid/buildworker/n:buildworkerid

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer buildworkerid: the ID of the buildworker

        This path returns the given buildworker, if it is configured on the any builder on the given master.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.buildworkers.BuildworkerResourceType

    .. py:method:: findSchedulerId(name)

        :param name: buildworker name
        :type name: 50-character identifier
        :returns: scheduler ID via Deferred

        Get the ID for the given buildworker name, inventing one if necessary.

    .. py:method:: buildworkerConnected(buildworkerid, masterid, workerinfo)

        :param integer buildworkerid: ID of the newly-connected buildworker
        :param integer masterid: the ID of the master to which it connected
        :param workerinfo: the new buildworker information dictionary
        :type workerinfo: dict
        :returns: Deferred

        Record the given buildworker as attached to the given master, and update its cached worker information.
        The supplied information completely replaces any existing information.
        This method also sends a message indicating the connection.

    .. py:method:: buildworkerDisconnected(buildworkerid, masterid)

        :param integer buildworkerid: ID of the newly-connected buildworker
        :param integer masterid: the ID of the master to which it connected
        :returns: Deferred

        Record the given buildworker as no longer attached to the given master.
        This method also sends a message indicating the disconnection.

    .. py:method:: buildworkerConfigured(buildworkerid, masterid, builderids)

        :param integer buildworkerid: the ID of the buildworker or None
        :param integer masterid: the ID of the master to which it configured
        :param list of integer builderids: the ID of the builders to which it is configured
        :returns: Deferred

        Record the given buildworker as being configured on the given master and for given builders.


    .. py:method:: deconfigureAllBuidworkersForMaster(masterid)

        :param integer masterid: the ID of the master to which it configured
        :returns: Deferred

        Unregister all the workers configured to a master for given builders.
        This shall happen when master disabled or before reconfiguration
