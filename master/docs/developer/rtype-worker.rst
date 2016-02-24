Workers
=======

.. bb:rtype:: worker

    :attr integer workerid: the ID of this worker
    :attr name: the name of the worker
    :type name: 50-character identifier
    :attr connected_to: list of masters this worker is attached to
    :type connected_to: list of objects with keys ``masterid`` and ``link``
    :attr configured_on: list of builders on masters this worker is configured on
    :type configured_on: list of objects with keys ``masterid``, ``builderid``, and ``link``
    :attr workerinfo: information about the worker
    :type workerinfo: dictionary

    The contents of the ``connected_to`` and ``configured_on`` attributes are sensitive to the context of the request.
    If a builder or master is specified in the path, then only the corresponding connections and configurations are included in the result.

    The worker information can be any JSON-able object.
    In practice, it contains the following keys, based on information provided by the worker:

    * ``admin`` (the admin information)
    * ``host`` (the name of the host)
    * ``access_uri`` (the access URI)
    * ``version`` (the version on the worker)

    A worker resource represents a worker to the source code monitored by Buildbot.

    .. bb:event:: worker.$workerid.connected

        The worker has connected to a master.

    .. bb:event:: worker.$workerid.disconnected

        The worker has disconnected from a master.

    .. bb:rpath:: /worker

        This path lists all workers.

    .. bb:rpath:: /worker/i:name

        :pathkey integer name: the name of the worker

        This path selects a specific worker, identified by name.

    .. bb:rpath:: /worker/n:workerid

        :pathkey integer workerid: the ID of the worker

        This path selects a specific worker, identified by ID.

    .. bb:rpath:: /builder/n:builderid/worker

        :pathkey integer builderid: the ID of the builder filtering the results

        This path lists all workers configured on the given builder on any master.

    .. bb:rpath:: /builder/n:builderid/worker/i:name

        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer name: the name of the worker

        This path returns the named worker, if it is configured on the given builder on any master.

    .. bb:rpath:: /builder/n:builderid/worker/n:workerid

        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer workerid: the ID of the worker

        This path returns the identified worker, if it is configured on the given builder on any master.

    .. bb:rpath:: /master/n:masterid/builder/n:builderid/worker

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer builderid: the ID of the builder filtering the results

        This path lists all workers configured on the given builder on the given master.

    .. bb:rpath:: /master/n:masterid/builder/n:builderid/worker/i:name

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer name: the name of the worker

        This path returns the named worker, if it is configured on the given builder on the given master.

    .. bb:rpath:: /master/n:masterid/builder/n:builderid/worker/n:workerid

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer builderid: the ID of the builder filtering the results
        :pathkey integer workerid: the ID of the worker

        This path returns the given worker, if it is configured on the given builder on the given master.

    .. bb:rpath:: /master/n:masterid/worker

        :pathkey integer masterid: the ID of the master filtering the results

        This path lists all workers configured on the any builder on the given master.

    .. bb:rpath:: /master/n:masterid/worker/i:name

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer name: the name of the worker

        This path returns the named worker, if it is configured on the any builder on the given master.

    .. bb:rpath:: /master/n:masterid/worker/n:workerid

        :pathkey integer masterid: the ID of the master filtering the results
        :pathkey integer workerid: the ID of the worker

        This path returns the given worker, if it is configured on the any builder on the given master.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.workers.Worker

    .. py:method:: findWorkerId(name)

        :param name: worker name
        :type name: 50-character identifier
        :returns: scheduler ID via Deferred

        Get the ID for the given worker name, inventing one if necessary.

    .. py:method:: workerConnected(workerid, masterid, workerinfo)

        :param integer workerid: ID of the newly-connected worker
        :param integer masterid: the ID of the master to which it connected
        :param workerinfo: the new worker information dictionary
        :type workerinfo: dict
        :returns: Deferred

        Record the given worker as attached to the given master, and update its cached worker information.
        The supplied information completely replaces any existing information.
        This method also sends a message indicating the connection.

    .. py:method:: workerDisconnected(workerid, masterid)

        :param integer workerid: ID of the newly-connected worker
        :param integer masterid: the ID of the master to which it connected
        :returns: Deferred

        Record the given worker as no longer attached to the given master.
        This method also sends a message indicating the disconnection.

    .. py:method:: workerConfigured(workerid, masterid, builderids)

        :param integer workerid: the ID of the worker or None
        :param integer masterid: the ID of the master to which it configured
        :param list of integer builderids: the ID of the builders to which it is configured
        :returns: Deferred

        Record the given worker as being configured on the given master and for given builders.


    .. py:method:: deconfigureAllWorkersForMaster(masterid)

        :param integer masterid: the ID of the master to which it configured
        :returns: Deferred

        Unregister all the workers configured to a master for given builders.
        This shall happen when master disabled or before reconfiguration
