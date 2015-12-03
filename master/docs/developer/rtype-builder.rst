Builders
========

.. bb:rtype:: builder

    :attr integer builderid: the ID of this builder
    :attr name: builder name
    :type name: 20-character :ref:`identifier <type-identifier>`
    :attr integer masterid: the ID of the master this builder is running on (only for messages; see below)

    This resource type describes a builder.

    .. bb:event:: builder.$builderid.started

        The builder has started on the master specified by the message's ``masterid``.

    .. bb:event:: builder.$builderid.stopped

        The builder has stopped on the master specified by the message's ``masterid``.

    .. bb:rpath:: /builder

        This path lists builders, sorted by ID.

        Subscribing to this path will select all :bb:event:`builder.$builderid.started` and :bb:event:`builder.$builderid.stopped` messages.

    .. bb:rpath:: /builder/:builderid

        :pathkey integer builderid: the ID of the builder

        This path selects a specific builder, identified by ID.

    .. bb:rpath:: /master/:masterid/builder/

        :pathkey integer masterid: the ID of the master

        This path enumerates the builders running on the given master.

    .. bb:rpath:: /master/:masterid/builder/:builderid

        :pathkey integer masterid: the ID of the master
        :pathkey integer builderid: the ID of the builder

        This path selects a specific builder, identified by ID.
        If the given builder is not running on the given master, this path returns nothing.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.changes.BuilderResourceType

    .. py:method:: updateBuilderList(masterid, builderNames)

        :param integer masterid: this master's master ID
        :param list builderNames: list of names of currently-configured builders (unicode strings)
        :returns: Deferred

        Record the given builders as the currently-configured set of builders on this master.
        Masters should call this every time the list of configured builders changes.

