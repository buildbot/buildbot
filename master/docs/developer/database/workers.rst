Workers connector
~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.workers

.. index:: double: Workers; DB Connector Component

.. py:class:: WorkersConnectorComponent

    This class handles Buildbot's notion of workers.
    The worker information is returned as a dictionary with the following keys:

    * ``id``
    * ``name`` - the name of the worker
    * ``workerinfo`` - worker information as dictionary
    * ``paused`` - boolean indicating worker is paused and shall not take new builds
    * ``graceful`` - boolean indicating worker will be shutdown as soon as build finished
    * ``connected_to`` - a list of masters, by ID, to which this worker is currently connected.
      This list will typically contain only one master, but in unusual circumstances the same worker may appear to be connected to multiple masters simultaneously
    * ``configured_on`` - a list of master-builder pairs, on which this worker is configured.
      Each pair is represented by a dictionary with keys ``buliderid`` and ``masterid``

    The worker information can be any JSON-able object.
    See :bb:rtype:`worker` for more detail.

    .. py:method:: findWorkerId(name=name)

        :param name: worker name
        :type name: 50-character identifier
        :returns: worker ID via Deferred

        Get the ID for a worker, adding a new worker to the database if necessary.
        The worker information for a new worker is initialized to an empty dictionary.

    .. py:method:: getWorkers(masterid=None, builderid=None)

        :param integer masterid: limit to workers configured on this master
        :param integer builderid: limit to workers configured on this builder
        :returns: list of worker dictionaries, via Deferred

        Get a list of workers.
        If either or both of the filtering parameters either specified, then the result is limited to workers configured to run on that master or builder.
        The ``configured_on`` results are limited by the filtering parameters as well.
        The ``connected_to`` results are limited by the ``masterid`` parameter.

    .. py:method:: getWorker(workerid=None, name=None, masterid=None, builderid=None)

        :param string name: the name of the worker to retrieve
        :param integer workerid: the ID of the worker to retrieve
        :param integer masterid: limit to workers configured on this master
        :param integer builderid: limit to workers configured on this builder
        :returns: info dictionary or None, via Deferred

        Looks up the worker with the given name or ID, returning ``None`` if no matching worker is found.
        The ``masterid`` and ``builderid`` arguments function as they do for :py:meth:`getWorkers`.

    .. py:method:: workerConnected(workerid, masterid, workerinfo)

        :param integer workerid: the ID of the worker
        :param integer masterid: the ID of the master to which it connected
        :param workerinfo: the new worker information dictionary
        :type workerinfo: dict
        :returns: Deferred

        Record the given worker as attached to the given master, and update its cached worker information.
        The supplied information completely replaces any existing information.

    .. py:method:: workerDisconnected(workerid, masterid)

        :param integer workerid: the ID of the worker
        :param integer masterid: the ID of the master to which it connected
        :returns: Deferred

        Record the given worker as no longer attached to the given master.

    .. py:method:: workerConfigured(workerid, masterid, builderids)

        :param integer workerid: the ID of the worker
        :param integer masterid: the ID of the master to which it configured
        :param list of integer builderids: the ID of the builders to which it is configured
        :returns: Deferred

        Record the given worker as being configured on the given master and for given builders.
        This method will also remove any other builder that were configured previously for same (worker, master) combination.


    .. py:method:: deconfigureAllWorkersForMaster(masterid)

        :param integer masterid: the ID of the master to which it configured
        :returns: Deferred

        Unregister all the workers configured to a master for given builders.
        This shall happen when master is disabled or before reconfiguration.

    .. py:method:: setWorkerState(workerid, paused, graceful)

        :param integer workerid: the ID of the worker whose state is being changed
        :param integer paused: the paused state
        :param integer graceful: the graceful state
        :returns: Deferred

        Change the state of a worker (see definition of states above in worker dict description).
