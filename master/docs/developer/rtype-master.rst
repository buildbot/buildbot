Masters
=======

.. bb:rtype:: master

    :attr integer masterid: the ID of this master
    :attr unicode name: master name (in the form "hostname:basedir")
    :attr boolean active: true if the master is active
    :attr timestamp last_active: time this master was last marked active

    This resource type describes buildmasters in the buildmaster cluster.

    .. bb:event:: master.$masterid.started

        The master has just started.

    .. bb:event:: master.$masterid.stopped

        The master has just stopped.
        If the master terminated abnormally, this may be sent sometime later, by another master.

    .. bb:rpath:: /master

        This path lists masters, sorted by ID.

        Consuming from this path selects :bb:event:`master.$masterid.started` and :bb:event:`master.$masterid.stopped` events.

    .. bb:rpath:: /master/:masterid

        :pathkey integer masterid: the ID of the master

        This path selects a specific master, identified by ID.

    .. bb:rpath:: /builder/:builderid/master

        :pathkey integer builderid: the ID of the builder

        This path enumerates the active masters where this builder is configured.

    .. bb:rpath:: /builder/:builderid/master/:masterid

        :pathkey integer builderid: the ID of the builder
        :pathkey integer masterid: the ID of the master

        This path selects a specific master, identified by ID.
        The ``:builderid`` field is ignored, since ``:masterid`` uniquely identifies the master.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.masters.MasterResourceType

    .. py:method:: masterActive(name, masterid)

        :param unicode name: the name of this master (generally ``hostname:basedir``)
        :param integer masterid: this master's master ID
        :returns: Deferred

        Mark this master as still active.
        This method should be called at startup and at least once per minute.
        The master ID is acquired directly from the database early in the master startup process.

    .. py:method:: expireMasters()

        :returns: Deferred

        Scan the database for masters that have not checked in for ten minutes.
        This method should be called about once per minute.

    .. py:method:: masterStopped(name, masterid)

        :param unicode name: the name of this master
        :param integer masterid: this master's master ID
        :returns: Deferred

        Mark this master as inactive.
        Masters should call this method before completing an expected shutdown, and on startup.
        This method will take care of deactivating or removing configuration resources like builders and schedulers as well as marking lost builds and build requests for retry.
