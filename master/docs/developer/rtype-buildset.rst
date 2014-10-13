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

    A buildset gathers build requests that were scheduled at the same time, and which share a source stamp, properties, and so on.

    .. todo::
        Currently buildset properties aren't available in this resource type

    .. bb:event:: buildset.$bsid.new

        This message indicates the addition of a new buildset.

    .. bb:event:: buildset.$bsid.complete

        This message indicates the completion of a buildset.

    .. bb:rpath:: /buildset

        :opt complete: if true, only return completed buildsets; if false, only return incomplete buildsets

        This path lists buildsets, sorted by ID.

        .. todo::
            Consuming from this path selects :bb:event:`buildset.$bsid.new` and :bb:event:`buildset.$bsid.complete` events.

    .. bb:rpath:: /buildset/:bsid

        :pathkey integer bsid: the ID of the buildset

        This path selects a specific buildset, identified by ID.

        .. todo::
            Consuming from this path selects and :bb:event:`buildset.$bsid.complete` events for this buildset.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.buildsets.BuildsetResourceType

    .. py:method:: addBuildset(scheduler=None, sourcestamps=[], reason='', properties={}, builderids=[], external_idstring=None, parent_buildid=None, parent_relationship=None)

        :param string scheduler: the name of the scheduler creating this buildset
        :param list sourcestamps: sourcestamps for the new buildset; see below
        :param unicode reason: the reason for this build
        :param properties: properties to set on this buildset
        :type properties: dictionary with unicode keys and (source, property value) values
        :param list builderids: names of the builderids for which build requests should be created
        :param unicode external_idstring: arbitrary identifier to recognize this buildset later
        :param int parent_buildid: optional build id that is the parent for this buildset
        :param unicode parent_relationship: relationship identifier for the parent, this is is configured relationship between the parent build, and the childs buildsets
        :returns: (buildset id, dictionary mapping builder ids to build request ids) via Deferred

        .. warning:

            The ``scheduler`` parameter will be replaced with a ``schedulerid`` parameter in future releases.

        Create a new buildset and corresponding buildrequests based on the given parameters.
        This is the low-level interface for scheduling builds.

        Each sourcestamp in the list of sourcestamps can be given either as an integer, assumed to be a sourcestamp ID, or a dictionary of keyword arguments to be passed to :py:meth:`~buildbot.db.sourcestamps.SourceStampsConnectorComponent.findSourceStampId`.

    .. py:method:: maybeBuildsetComplete(bsid)

        :param integer bsid: buildset that may be complete
        :returns: Deferred

        This method should be called when a build request is finished.
        It checks the given buildset to see if all of its buildrequests are finished.
        If so, it updates the status of the buildset and send the appropriate messages.

