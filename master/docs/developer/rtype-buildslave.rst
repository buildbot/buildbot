Buildslaves
===========

.. bb:rtype:: buildslave

    :attr integer buildslaveid: the ID of this buildslave
    :attr name: the name of the buildslave
    :type name: 50-character identifier
    :attr connected_to: list of masters this buildslave is attached to
    :type connected_to: list of objects with keys ``masterid`` and ``link``
    :attr configured_on: list of builders on masters this buildslave is configured on
    :type configured_on: list of objects with keys ``masterid``, ``builderid``, and ``link``
    :attr slaveinfo: information about the slave
    :type slaveinfo: dictionary

    The contents of the ``connected_to`` and ``configured_on`` attributes are sensitive to the context of the request.
    If a builder or master is specified in the path, then only the corresponding connections and configurations are included in the result.

    The buildslave information can be any JSON-able object.
    In practice, it contains the following keys, based on information provided by the slave:

    * ``admin`` (the admin information)
    * ``host`` (the name of the host)
    * ``access_uri`` (the access URI)
    * ``version`` (the version on the buildslave)

    A buildslave resource represents a buildslave to the source code monitored by Buildbot.

    .. bb:event:: buildslave.$buildslaveid.connected

        The buildslave has connected to a master.

    .. bb:event:: buildslave.$buildslaveid.disconnected

        The buildslave has disconnected from a master.

    .. bb:rpath:: /buildslave

        This path lists all buildslaves.

    .. bb:rpath:: /buildslave/i:name

        :pathkey integer name: the name of the buildslave

        This path selects a specific buildslave, identified by name.

    .. bb:rpath:: /buildslave/n:buildslaveid

        :pathkey integer buildslaveid: the ID of the buildslave

        This path selects a specific buildslave, identified by ID.

    .. bb:rpath:: /builder/n:builderid/buildslave

        :pathkey integer builderid: the ID of the builder filtering the results

        This path lists all buildslaves configured on the given builder on any master.

    .. bb:rpath:: /builder/n:builderid/buildslave/i:name

        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer name: the name of the buildslave

        This path returns the named buildslave, if it is configured on the given builder on any master.

    .. bb:rpath:: /builder/n:builderid/buildslave/n:buildslaveid

        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer buildslaveid: the ID of the buildslave

        This path returns the identified buildslave, if it is configured on the given builder on any master.

    .. bb:rpath:: /master/n:masterid/builder/n:builderid/buildslave

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer builderid: the ID of the builder filtering the results

        This path lists all buildslaves configured on the given builder on the given master.

    .. bb:rpath:: /master/n:masterid/builder/n:builderid/buildslave/i:name

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer name: the name of the buildslave

        This path returns the named buildslave, if it is configured on the given builder on the given master.

    .. bb:rpath:: /master/n:masterid/builder/n:builderid/buildslave/n:buildslaveid

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer buildslaveid: the ID of the buildslave

        This path returns the given buildslave, if it is configured on the given builder on the given master.

    .. bb:rpath:: /master/n:masterid/buildslave

        :pathkey integer masterid: the ID of the master filtering the results

        This path lists all buildslaves configured on the any builder on the given master.

    .. bb:rpath:: /master/n:masterid/buildslave/i:name

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer name: the name of the buildslave

        This path returns the named buildslave, if it is configured on the any builder on the given master.

    .. bb:rpath:: /master/n:masterid/buildslave/n:buildslaveid

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer buildslaveid: the ID of the buildslave

        This path returns the given buildslave, if it is configured on the any builder on the given master.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.buildslaves.BuildslaveResourceType

    .. py:method:: findSchedulerId(name)

        :param name: buildslave name
        :type name: 50-character identifier
        :returns: scheduler ID via Deferred

        Get the ID for the given buildslave name, inventing one if necessary.

    .. py:method:: buildslaveConnected(buildslaveid, masterid, slaveinfo)

        :param integer buildslaveid: ID of the newly-connected buildslave
        :param integer masterid: the ID of the master to which it connected
        :param slaveinfo: the new buildslave information dictionary
        :type slaveinfo: dict
        :returns: Deferred

        Record the given buildslave as attached to the given master, and update its cached slave information.
        The supplied information completely replaces any existing information.
        This method also sends a message indicating the connection.

    .. py:method:: buildslaveDisconnected(buildslaveid, masterid)

        :param integer buildslaveid: ID of the newly-connected buildslave
        :param integer masterid: the ID of the master to which it connected
        :returns: Deferred

        Record the given buildslave as no longer attached to the given master.
        This method also sends a message indicating the disconnection.

    .. py:method:: buildslaveConfigured(buildslaveid, masterid, builderids)

        :param integer buildslaveid: the ID of the buildslave or None
        :param integer masterid: the ID of the master to which it configured
        :param list of integer builderids: the ID of the builders to which it is configured
        :returns: Deferred

        Record the given buildslave as being configured on the given master and for given builders.


    .. py:method:: deconfigureAllBuidslavesForMaster(masterid)

        :param integer masterid: the ID of the master to which it configured
        :returns: Deferred

        Unregister all the slaves configured to a master for given builders.
        This shall happen when master disabled or before reconfiguration
