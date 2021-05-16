Buildrequests connector
~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.buildrequests

.. index:: double: BuildRequests; DB Connector Component

.. py:exception:: AlreadyClaimedError

    Raised when a build request is already claimed, usually by another master.

.. py:exception:: NotClaimedError

    Raised when a build request is not claimed by this master.

.. py:class:: BuildRequestsConnectorComponent

    This class handles the complex process of claiming and unclaiming build
    requests, based on a polling model: callers poll for unclaimed requests with
    :py:meth:`getBuildRequests`, and then they attempt to claim the requests with
    :py:meth:`claimBuildRequests`.  The claim can fail if another master has claimed
    the request in the interim.

    An instance of this class is available at ``master.db.buildrequests``.

    .. index:: brdict, brid

    Build requests are indexed by an ID referred to as a *brid*.  The contents
    of a request are represented as build request dictionaries (brdicts) with
    keys

    * ``buildrequestid``
    * ``buildsetid``
    * ``builderid``
    * ``buildername``
    * ``priority``
    * ``claimed`` (boolean, true if the request is claimed)
    * ``claimed_at`` (datetime object, time this request was last claimed)
    * ``claimed_by_masterid`` (integer, the id of the master that claimed this buildrequest)
    * ``complete`` (boolean, true if the request is complete)
    * ``complete_at`` (datetime object, time this request was completed)
    * ``submitted_at`` (datetime object, time this request was completed)
    * ``results`` (integer result code)
    * ``waited_for`` (boolean)

    .. py:method:: getBuildRequest(brid)

        :param brid: build request id to look up
        :returns: brdict or ``None``, via Deferred

        Get a single BuildRequest, in the format described above.  This method
        returns ``None`` if there is no such buildrequest.  Note that build
        requests are not cached, as the values in the database are not fixed.

    .. py:method:: getBuildRequests(buildername=None, complete=None, claimed=None, bsid=None, branch=None, repository=None, resultSpec=None)

        :param buildername: limit results to buildrequests for this builder
        :type buildername: string
        :param complete: if true, limit to completed buildrequests; if false,
            limit to incomplete buildrequests; if ``None``, do not limit based on
            completion.
        :param claimed: see below
        :param bsid: see below
        :param repository: the repository associated with the sourcestamps originating the requests
        :param branch: the branch associated with the sourcestamps originating the requests
        :param resultSpec: resultSpec containing filters sorting and paging request from data/REST API.
            If possible, the db layer can optimize the SQL query using this information.
        :returns: list of brdicts, via Deferred

        Get a list of build requests matching the given characteristics.

        Pass all parameters as keyword parameters to allow future expansion.

        The ``claimed`` parameter can be ``None`` (the default) to ignore the
        claimed status of requests; ``True`` to return only claimed builds,
        ``False`` to return only unclaimed builds, or a ``master ID`` to return only
        builds claimed by a particular master instance.  A request is considered
        unclaimed if its ``claimed_at`` column is either NULL or 0, and it is
        not complete.  If ``bsid`` is specified, then only build requests for
        that buildset will be returned.

        A build is considered completed if its ``complete`` column is 1; the
        ``complete_at`` column is not consulted.

    .. py:method:: claimBuildRequests(brids[, claimed_at=XX])

        :param brids: ids of buildrequests to claim
        :type brids: list
        :param datetime claimed_at: time at which the builds are claimed
        :returns: Deferred
        :raises: :py:exc:`AlreadyClaimedError`

        Try to "claim" the indicated build requests for this buildmaster
        instance.  The resulting deferred will fire normally on success, or
        fail with :py:exc:`AlreadyClaimedError` if *any* of the build
        requests are already claimed by another master instance.  In this case,
        none of the claims will take effect.

        If ``claimed_at`` is not given, then the current time will be used.

        .. index:: single: MySQL; limitations
        .. index:: single: SQLite; limitations

        .. note::
            On database backends that do not enforce referential integrity
            (e.g., SQLite), this method will not prevent claims for nonexistent
            build requests.  On database backends that do not support
            transactions (MySQL), this method will not properly roll back any
            partial claims made before an :py:exc:`AlreadyClaimedError` is
            generated.

    .. py:method:: unclaimBuildRequests(brids)

        :param brids: ids of buildrequests to unclaim
        :type brids: list
        :returns: Deferred

        Release this master's claim on all of the given build requests.  This
        will not unclaim requests that are claimed by another master, but will
        not fail in this case.  The method does not check whether a request is
        completed.

    .. py:method:: completeBuildRequests(brids, results[, complete_at=XX])

        :param brids: build request ids to complete
        :type brids: integer
        :param results: integer result code
        :type results: integer
        :param datetime complete_at: time at which the buildset was completed
        :returns: Deferred
        :raises: :py:exc:`NotClaimedError`

        Complete a set of build requests, all of which are owned by this master
        instance.  This will fail with :py:exc:`NotClaimedError` if the build
        request is already completed or does not exist.  If ``complete_at`` is
        not given, the current time will be used.
