Buildsets
=========

.. bb:rtype:: buildset

    :attr integer bsid: the ID of this buildset
    :attr string external_idstring: an identifier that external applications can use to identify a submitted buildset; can be None
    :attr string reason: the reason this buildset was scheduled
    :attr timestamp submitted_at: the time this buildset was submitted
    :attr boolean complete: true if all of the build requests in this buildset are complete
    :attr timestamp complete_at: the time this buildset was completed, or None if not complete
    :attr integer results: the results of the buildset (see :ref:`Build-Result-Codes`), or None if not complete
    :attr list sourcestamps: the sourcestamps for this buildset; each element is a valid :bb:rtype:`sourcestamp` entity
    :attr Link link: link for this buildset

    A buildset gathers build requests that were scheduled at the same time, and which share a source stamp, properties, and so on.

    .. todo:
        Currently buildset properties aren't available in this resource type

    .. bb:event:: buildset.$bsid.new

        This message indicates the addition of a new buildset.

    .. bb:event:: buildset.$bsid.complete

        This message indicates the completion of a buildset.

    .. bb:rpath:: /buildset

        :opt complete: if true, only return completed buildsets; if false, only return incomplete buildsets

        This path lists buildsets, sorted by ID.

        .. todo:
            Consuming from this path selects :bb:event:`buildset.$bsid.new` and :bb:event:`buildset.$bsid.complete` events.

    .. bb:rpath:: /buildset/:bsid

        :pathkey integer bsid: the ID of the buildset

        This path selects a specific buildset, identified by ID.

        .. todo:
            Consuming from this path selects and :bb:event:`buildset.$bsid.complete` events for this buildset.
