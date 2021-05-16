Buildsets connector
~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.buildsets

.. index:: double: Buildsets; DB Connector Component

.. py:class:: BuildsetsConnectorComponent

    This class handles getting buildsets into and out of the database.
    Buildsets combine multiple build requests that were triggered together.

    An instance of this class is available at ``master.db.buildsets``.

    .. index:: bsdict, bsid

    Buildsets are indexed by *bsid* and their contents are represented as *bsdicts* (buildset dictionaries), with keys

    * ``bsid``
    * ``external_idstring`` (arbitrary string for mapping builds externally)
    * ``reason`` (string; reason these builds were triggered)
    * ``sourcestamps`` (list of sourcestamps for this buildset, by ID)
    * ``submitted_at`` (datetime object; time this buildset was created)
    * ``complete`` (boolean; true if all of the builds for this buildset are complete)
    * ``complete_at`` (datetime object; time this buildset was completed)
    * ``results`` (aggregate result of this buildset; see :ref:`Build-Result-Codes`)

    .. py:method:: addBuildset(sourcestamps, reason, properties, builderids, external_idstring=None, parent_buildid=None, parent_relationship=None)

        :param sourcestamps: sourcestamps for the new buildset; see below
        :type sourcestamps: list
        :param reason: reason for this buildset
        :type reason: short unicode string
        :param properties: properties for this buildset
        :type properties: dictionary, where values are tuples of (value, source)
        :param builderids: builderids specified by this buildset
        :type builderids: list of int
        :param external_idstring: external key to identify this buildset; defaults to None
        :type external_idstring: unicode string
        :param datetime submitted_at: time this buildset was created; defaults to the current time
        :param int parent_buildid: optional build id that is the parent for this buildset
        :param unicode parent_relationship: relationship identifier for the parent. This is the configured relationship between the parent build and the child buildsets
        :returns: buildset ID and buildrequest IDs, via a Deferred

        Add a new buildset to the database, along with build requests for each builder, returning the resulting bsid via a Deferred.
        Arguments should be specified by keyword.

        Each sourcestamp in the list of sourcestamps can be given either as an integer, assumed to be a sourcestamp ID, or a dictionary of keyword arguments to be passed to :py:meth:`~buildbot.db.sourcestamps.SourceStampsConnectorComponent.findSourceStampId`.

        The return value is a tuple ``(bsid, brids)`` where ``bsid`` is the inserted buildset ID and ``brids`` is a dictionary mapping builderids to build request IDs.

    .. py:method:: completeBuildset(bsid, results[, complete_at=XX])

        :param bsid: buildset ID to complete
        :type bsid: integer
        :param results: integer result code
        :type results: integer
        :param datetime complete_at: time the buildset was completed
        :returns: Deferred
        :raises: :py:exc:`KeyError` if the buildset does not exist or is
            already complete

        Complete a buildset, marking it with the given ``results`` and setting
        its ``completed_at`` to the current time, if the ``complete_at``
        argument is omitted.

    .. py:method:: getBuildset(bsid)

        :param bsid: buildset ID
        :returns: bsdict, or ``None``, via Deferred

        Get a bsdict representing the given buildset, or ``None`` if no such
        buildset exists.

        Note that buildsets are not cached, as the values in the database are
        not fixed.

    .. py:method:: getBuildsets(complete=None, resultSpec=None)

        :param complete: if true, return only complete buildsets; if false,
            return only incomplete buildsets; if ``None`` or omitted, return all
            buildsets
        :param resultSpec: result spec containing filters sorting and paging requests from data/REST API.
            If possible, the db layer can optimize the SQL query using this information.

        :returns: list of bsdicts, via Deferred

        Get a list of bsdicts matching the given criteria.

    .. py:method:: getRecentBuildsets(count=None, branch=None, repository=None,
                           complete=None):

        :param count: maximum number of buildsets to retrieve (required)
        :type count: integer
        :param branch: optional branch name. If specified, only buildsets
            affecting such branch will be returned
        :type branch: string
        :param repository: optional repository name. If specified, only
            buildsets affecting such repository will be returned
        :type repository: string
        :param complete: if true, return only complete buildsets; if false,
            return only incomplete buildsets; if ``None`` or omitted, return all
            buildsets
        :type complete: Boolean
        :returns: list of bsdicts, via Deferred

        Get "recent" buildsets, as defined by their ``submitted_at`` times.

    .. py:method:: getBuildsetProperties(buildsetid)

        :param bsid: buildset ID
        :returns: dictionary mapping property name to ``value, source``, via
            Deferred

        Return the properties for a buildset, in the same format they were
        given to :py:meth:`addBuildset`.

        Note that this method does not distinguish a nonexistent buildset from
        a buildset with no properties, and returns ``{}`` in either case.
