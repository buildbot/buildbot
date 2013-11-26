BuildRequests
=============

.. todo::
    This data API is not yet implemented

.. bb:rtype:: buildrequest

    :attr integer buildrequestid: the unique ID of this buildrequest
    :attr integer buildsetid: the id of the buildset that contains this buildrequest
    :attr Link buildset_link: the link to the buildset that contains this buildrequest
    :attr string buildername: the name of the builder linked to this buildrequest
    :attr integer priority: the priority of this buildrequest
    :attr boolean claimed: true if this buildrequest has been claimed
    :attr timestamp claimed_at: time at which this build has last been claimed,
          or None if this buildrequest has never been claimed or has been unclaimed
    :attr boolean mine: true if this request is claimed by this master;
          false if this buildrequest has not been claimed or has been claimed by another master
    :attr boolean complete: true if this buildrequest is complete
    :attr integer results: the results of this buildrequest (see :ref:`Build-Result-Codes`),
          or None if not complete
    :attr timestamp submitted_at: time at which this buildrequest were submitted
    :attr timestamp complete_at: time at which this buildrequest was completed,
          or None if it's still running
    :attr boolean waited_for: true if the entity that triggered this buildrequest is waiting for it to complete
    :attr Link link: link for this buildrequest

    This resource type describes completed and in-progress buildrequests.
    Much of the contextual data for a buildrequest is associated with the buildset that contains this buildrequest.

Events
------

.. todo:: 
    The initial version of buildrequest events is described in :ref:`Messaging_and_Queues`
    This list is under discussion

Endpoints
---------

.. bb:rpath:: GET /buildrequest

    This path lists buildrequests, sorted by ID.

.. bb:rpath:: GET /buildrequest/:buildrequestid

    :pathkey integer buildrequestid: the ID of the buildrequest

    This path selects a specific buildrequest, identified by its ID.

.. bb:rpath:: POST /buildrequest/:buildrequestid

    :pathkey integer buildrequestid: the ID of the buildrequest
    :jsonparam: action (string) the action to perform on this buildrequest

    This path performs an action (e.g. cancelling) on the buildrequests, identified by its ID.
    The action is encoded in the POST data 'action' key

.. bb:rpath:: GET /builder/:builderid/buildrequest

    :pathkey integer builderid: the ID of the builder

    This path lists buildrequests performed for the identified builder, sorted by ID.

.. todo::
    May need to define additional useful collection endpoints like e.g:
        * /builder/:buildername/buildrequest
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