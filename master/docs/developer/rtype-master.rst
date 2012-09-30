Masters
=======

.. bb:rtype:: master

    :attr integer masterid: the ID of this master
    :attr unicode name: master name (in the form "hostname:basedir")
    :attr unicode state: master state, either 'started' or 'stopped'

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
