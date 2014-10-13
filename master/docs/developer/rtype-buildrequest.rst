BuildRequests
=============

.. bb:rtype:: buildrequest

    :attr integer buildrequestid: the unique ID of this buildrequest
    :attr integer buildsetid: the id of the buildset that contains this buildrequest
    :attr integer builderid: the id of the builder linked to this buildrequest
    :attr integer priority: the priority of this buildrequest
    :attr boolean claimed: true if this buildrequest has been claimed
    :attr timestamp claimed_at: time at which this build has last been claimed,
          or None if this buildrequest has never been claimed or has been unclaimed
    :attr integer claimed_by_masterid: the id of the master that claimed this buildrequest.
          None if this buildrequest has not been claimed
    :attr boolean complete: true if this buildrequest is complete
    :attr integer results: the results of this buildrequest (see :ref:`Build-Result-Codes`),
          or None if not complete
    :attr timestamp submitted_at: time at which this buildrequest were submitted
    :attr timestamp complete_at: time at which this buildrequest was completed,
          or None if it's still running
    :attr boolean waited_for: true if the entity that triggered this buildrequest is waiting for it to complete (should be used by clean shutdown to only start br that are waited_for)

    This resource type describes completed and in-progress buildrequests.
    Much of the contextual data for a buildrequest is associated with the buildset that contains this buildrequest.

Events
------

.. todo::
    The initial version of buildrequest events is described in :ref:`Messaging_and_Queues`
    This list is under discussion

Endpoints
---------

.. bb:rpath:: /buildrequest

    This path lists buildrequests, sorted by ID.

        :opt complete: if true, only returns completed buildsets;
                       if false, only returns incomplete buildsets
        :opt claimed: if true, only returns the claimed buildrequests;
                      if false, only returns unclaimed builds
        :opt claimed_by_masterid: only returns buildrequests claimed by this master instance
        :opt buildsetid: only returns buildrequests contained by this buildset ID
        :opt branch: only returns buildrequests on this branch
        :opt repository: only returns buildrequests on this repository

.. bb:rpath:: /buildrequest/:buildrequestid

    :pathkey integer buildrequestid: the ID of the buildrequest

    This path selects a specific buildrequest, identified by its ID.

    This endpoint has a control method with the following action:

    * cancel (TODO - not implemented yet):

        cancel the buildrequest identified by its ID.

.. bb:rpath:: /builders/:buildername/buildrequest

    :pathkey string buildername: the name of the builder

    This path lists buildrequests performed for the identified builder, sorted by ID.

        :opt this endpoint supports same options as /buildrequest

.. bb:rpath:: /builder/:builderid/buildrequest


.. bb:rpath:: /builders/:builderid/buildrequest

    :pathkey integer builderid: the id of the builder

    This path lists buildrequests performed for the identified builder, sorted by ID.

        :opt this endpoint supports same options as /buildrequest

.. todo::
    May need to define additional useful collection endpoints like e.g:
        * /buildset/:buildsetid/buildrequest

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.buildrequests.BuildRequest

    .. py:method:: claimBuildRequests(brids, claimed_at=None, _reactor=twisted.internet.reactor)

        :param list(integer) brids: list of buildrequest id to claim
        :param datetime claimed_at: date and time when the buildrequest is claimed
        :param twisted.internet.interfaces.IReactorTime _reactor: reactor used to get current time if ``claimed_at`` is None
        :returns: (boolean) whether claim succeeded or not

        Claim a list of buildrequests

    .. py:method:: reclaimBuildRequests(brids, _reactor=twisted.internet.reactor)

        :param list(integer) brids: list of buildrequest id to reclaim
        :param twisted.internet.interfaces.IReactorTime _reactor: reactor used to get current time
        :returns: (boolean) whether reclaim succeeded or not

        Reclaim a list of buildrequests

    .. py:method:: unclaimBuildRequests(brids)

        :param list(integer) brids: list of buildrequest id to unclaim

        Unclaim a list of buildrequests

    .. py:method:: completeBuildRequests(brids, results, complete_at=None, _reactor=twisted.internet.reactor)

        :param list(integer) brids: list of buildrequest id to complete
        :param integer results: the results of the buildrequest (see :ref:`Build-Result-Codes`)
        :param datetime complete_at: date and time when the buildrequest is completed
        :param twisted.internet.interfaces.IReactorTime _reactor: reactor used to get current time, if ``complete_at`` is None

        Complete a list of buildrequest with the ``results`` status

    .. py:method:: unclaimExpiredRequests(old, _reactor=twisted.internet.reactor)

        :param integer old: time in seconds considered for getting unclaimed buildrequests
        :param twisted.internet.interfaces.IReactorTime _reactor: reactor used to get current time

        Unclaim the previously claimed buildrequests that are older than ``old`` seconds
        and that were never completed
