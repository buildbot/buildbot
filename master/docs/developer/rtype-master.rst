Masters
=======

.. bb:rtype:: master

    :attr integer masterid: the ID of this master
    :attr unicode name: master name (in the form "hostname:basedir")
    :attr unicode state: master state, either 'started' or 'stopped'

    This resource type describes buildmasters in the buildmaster cluster.

    .. warning:
        At this time, only the local master is represented, and it is assumed
        to have id '1'.

    .. bb:event:: master.$masterid.started

        The master has just started.

    .. bb:event:: master.$masterid.stopped

        The master has just stopped.
        Note that this message will not be sent if a master terminates abnormally.

    .. bb:rpath:: /master

        :opt count: number of masters to return (maximum 50)

        This path lists masters, sorted by ID.
        The ``count`` option can be used to limit the number of masters.

        Consuming from this path selects :bb:event:`master.$masterid.started` and :bb:event:`master.$masterid.stopped` events.

    .. bb:rpath:: /master/:masterid

        :pathkey integer masterid: the ID of the master

        This path selects a specific master, identified by ID.
