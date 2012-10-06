Builders
========

.. bb:rtype:: builder

    :attr integer builderid: the ID of this builder
    :attr unicode name: builder name
    :attr Link link: link for this builder

    This resource type describes a builder.

    .. bb:event:: builder.$builderid.new

        A new builder has been added to the configuration.

    .. bb:rpath:: /builder

        This path lists builders, sorted by ID.
        The resulting builder objects omit the ``masters`` key.

        Subscribing to this path will select all :bb:event:`builder.$builderid.new` messages.

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
        The ``:masterid`` field is ignored, since ``:builderid`` uniquely identifies the builder.
