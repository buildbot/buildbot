.. _developer-database:

Database
========

As of version 0.8.0, Buildbot has used a database as part of its storage
backend.  This section describes the database connector classes, which allow
other parts of Buildbot to access the database.  It also describes how to
modify the database schema and the connector classes themselves.


Database Overview
-----------------

All access to the Buildbot database is mediated by database connector classes.
These classes provide a functional, asynchronous interface to other parts of
Buildbot, and encapsulate the database-specific details in a single location in
the codebase.

The connector API, defined below, is a stable API in Buildbot, and can be
called from any other component.  Given a master ``master``, the root of the
database connectors is available at ``master.db``, so, for example, the state
connector's ``getState`` method is ``master.db.state.getState``.

The connectors all use `SQLAlchemy Core
<http://www.sqlalchemy.org/docs/index.html>`_ to achieve (almost)
database-independent operation.  Note that the SQLAlchemy ORM is not used in
Buildbot.  Database queries are carried out in threads, and report their
results back to the main thread via Twisted Deferreds.

Schema
------

The database schema is maintained with `SQLAlchemy-Migrate
<https://github.com/openstack/sqlalchemy-migrate>`_.  This package handles the
details of upgrading users between different schema versions.

The schema itself is considered an implementation detail, and may change
significantly from version to version.  Users should rely on the API (below),
rather than performing queries against the database itself.

API
---

types
~~~~~

Identifier
..........

.. _type-identifier:

An "identifier" is a nonempty unicode string of limited length, containing only UTF-8 alphanumeric characters along with ``-`` (dash) and ``_`` (underscore), and not beginning with a digit
Wherever an identifier is used, the documentation will give the maximum length in characters.
The function :py:func:`buildbot.util.identifiers.isIdentifier` is useful to verify a well-formed identifier.

buildrequests
~~~~~~~~~~~~~

.. py:module:: buildbot.db.buildrequests

.. index:: double: BuildRequests; DB Connector Component

.. py:exception:: AlreadyClaimedError

    Raised when a build request is already claimed, usually by another master.

.. py:exception:: NotClaimedError

    Raised when a build request is not claimed by this master.

.. py:class:: BuildRequestsConnectorComponent

    This class handles the complex process of claiming and unclaiming build
    requests, based on a polling model: callers poll for unclaimed requests with
    :py:meth:`getBuildRequests`, then attempt to claim the requests with
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

        :param brids: build request IDs to complete
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

builds
~~~~~~

.. py:module:: buildbot.db.builds

.. index:: double: Builds; DB Connector Component

.. py:class:: BuildsConnectorComponent

    This class handles builds.
    One build record is created for each build performed by a master.
    This record contains information on the status of the build, as well as links to the resources used in the build: builder, master, worker, etc.

    An instance of this class is available at ``master.db.builds``.

    .. index:: bdict, buildid

    Builds are indexed by *buildid* and their contents represented as *builddicts* (build dictionaries), with the following keys:

    * ``id`` (the build ID, globally unique)
    * ``number`` (the build number, unique only within the builder)
    * ``builderid`` (the ID of the builder that performed this build)
    * ``buildrequestid`` (the ID of the build request that caused this build)
    * ``workerid`` (the ID of the worker on which this build was performed)
    * ``masterid`` (the ID of the master on which this build was performed)
    * ``started_at`` (datetime at which this build began)
    * ``complete_at`` (datetime at which this build finished, or None if it is ongoing)
    * ``state_string`` (short string describing the build's state)
    * ``results`` (results of this build; see :ref:`Build-Result-Codes`)

    .. py:method:: getBuild(buildid)

        :param integer buildid: build id
        :returns: Build dictionary as above or ``None``, via Deferred

        Get a single build, in the format described above.
        Returns ``None`` if there is no such build.

    .. py:method:: getBuildByNumber(builderid, number)

        :param integer builder: builder id
        :param integer number: build number within that builder
        :returns: Build dictionary as above or ``None``, via Deferred

        Get a single build, in the format described above, specified by builder and number, rather than build id.
        Returns ``None`` if there is no such build.

    .. py:method:: getPrevSuccessfulBuild(builderid, number, ssBuild)

        :param integer builderid: builder to get builds for
        :param integer number: the current build number. Previous build will be taken from this number
        :param list ssBuild: the list of sourcestamps for the current build number
        :returns: None or a build dictionary

        Returns the last successful build from the current build number with the same repository/repository/codebase

    .. py:method:: getBuilds(builderid=None, buildrequestid=None, complete=None, resultSpec=None)

        :param integer builderid: builder to get builds for
        :param integer buildrequestid: buildrequest to get builds for
        :param boolean complete: if not None, filters results based on completeness
        :param resultSpec: resultSpec containing filters sorting and paging request from data/REST API.
            If possible, the db layer can optimize the SQL query using this information.
        :returns: list of build dictionaries as above, via Deferred

        Get a list of builds, in the format described above.
        Each of the parameters limit the resulting set of builds.

    .. py:method:: addBuild(builderid, buildrequestid, workerid, masterid, state_string)

        :param integer builderid: builder to get builds for
        :param integer buildrequestid: build request id
        :param integer workerid: worker performing the build
        :param integer masterid: master performing the build
        :param unicode state_string: initial state of the build
        :returns: tuple of build ID and build number, via Deferred

        Add a new build to the db, recorded as having started at the current time.
        This will invent a new number for the build, unique within the context of the builder.

    .. py:method:: setBuildStateString(buildid, state_string):

        :param integer buildid: build id
        :param unicode state_string: updated state of the build
        :returns: Deferred

        Update the state strings for the given build.

    .. py:method:: finishBuild(buildid, results)

        :param integer buildid: build id
        :param integer results: build result
        :returns: Deferred

        Mark the given build as finished, with ``complete_at`` set to the current time.

        .. note::

            This update is done unconditionally, even if the build is already finished.

    .. py:method:: getBuildProperties(buildid)

        :param buildid: build ID
        :returns: dictionary mapping property name to ``value, source``, via Deferred

        Return the properties for a build, in the same format they were given to :py:meth:`addBuild`.

        Note that this method does not distinguish a non-existent build from a build with no properties, and returns ``{}`` in either case.

    .. py:method:: setBuildProperty(buildid, name, value, source)

        :param integer buildid: build ID
        :param string name: Name of the property to set
        :param value: Value of the property
        :param string source: Source of the Property to set
        :returns: Deferred

        Set a build property.
        If no property with that name existed in that build, a new property will be created.

steps
~~~~~

.. py:module:: buildbot.db.steps

.. index:: double: Steps; DB Connector Component

.. py:class:: StepsConnectorComponent

    This class handles the steps performed within the context of a build.
    Within a build, each step has a unique name and a unique, 0-based number.

    An instance of this class is available at ``master.db.steps``.

    .. index:: stepdict, stepid

    Builds are indexed by *stepid* and their contents represented as *stepdicts* (step dictionaries), with the following keys:

    * ``id`` (the step ID, globally unique)
    * ``number`` (the step number, unique only within the build)
    * ``name`` (the step name, an 50-character :ref:`identifier <type-identifier>` unique only within the build)
    * ``buildid`` (the ID of the build containing this step)
    * ``started_at`` (datetime at which this step began)
    * ``complete_at`` (datetime at which this step finished, or None if it is ongoing)
    * ``state_string`` (short string describing the step's state)
    * ``results`` (results of this step; see :ref:`Build-Result-Codes`)
    * ``urls`` (list of URLs produced by this step. Each urls is stored as a dictionary with keys `name` and `url`)
    * ``hidden`` (true if the step should be hidden in status displays)

    .. py:method:: getStep(stepid=None, buildid=None, number=None, name=None)

        :param integer stepid: the step id to retrieve
        :param integer buildid: the build from which to get the step
        :param integer number: the step number
        :param name: the step name
        :type name: 50-character :ref:`identifier <type-identifier>`
        :returns: stepdict via Deferred

        Get a single step.
        The step can be specified by

            * ``stepid`` alone;
            * ``buildid`` and ``number``, the step number within that build; or
            * ``buildid`` and ``name``, the unique step name within that build.

    .. py:method:: getSteps(buildid)

        :param integer buildid: the build from which to get the step
        :returns: list of stepdicts, sorted by number, via Deferred

        Get all steps in the given build, in order by number.

    .. py:method:: addStep(self, buildid, name, state_string)

        :param integer buildid: the build to which to add the step
        :param name: the step name
        :type name: 50-character :ref:`identifier <type-identifier>`
        :param unicode state_string: the initial state of the step
        :returns: tuple of step ID, step number, and step name, via Deferred

        Add a new step to a build.
        The given name will be used if it is unique; otherwise, a unique numerical suffix will be appended.

    .. py:method:: setStepStateString(stepid, state_string):

        :param integer stepid: step ID
        :param unicode state_string: updated state of the step
        :returns: Deferred

        Update the state string for the given step.

    .. py:method:: finishStep(stepid, results, hidden)

        :param integer stepid: step ID
        :param integer results: step result
        :param bool hidden: true if the step should be hidden
        :returns: Deferred

        Mark the given step as finished, with ``complete_at`` set to the current time.

        .. note::

            This update is done unconditionally, even if the steps are already finished.

    .. py:method:: addURL(self, stepid, name, url)

        :param integer stepid: the stepid to add the url.
        :param string name: the url name
        :param string url: the actual url
        :returns: None via deferred

        Add a new url to a step.
        The new url is added to the list of urls.

logs
~~~~

.. py:module:: buildbot.db.logs

.. index:: double: Logs; DB Connector Component

.. py:class:: LogsConnectorComponent

    This class handles log data.
    Build steps can have zero or more logs.
    Logs are uniquely identified by name within a step.

    Information about a log, apart from its contents, is represented as a dictionary with the following keys, referred to as a *logdict*:

    * ``id`` (log ID, globally unique)
    * ``stepid`` (step ID, indicating the containing step)
    * ``name`` free-form name of this log
    * ``slug`` (50-identifier for the log, unique within the step)
    * ``complete`` (true if the log is complete and will not receive more lines)
    * ``num_lines`` (number of lines in the log)
    * ``type`` (log type; see below)

    Each log has a type that describes how to interpret its contents.
    See the :bb:rtype:`logchunk` resource type for details.

    A log is contains a sequence of newline-separated lines of unicode.
    Log line numbering is zero-based.

    Each line must be less than 64k when encoded in UTF-8.
    Longer lines will be truncated, and a warning logged.

    Lines are stored internally in "chunks", and optionally compressed, but the implementation hides these details from callers.

    .. py:method:: getLog(logid)

        :param integer logid: ID of the requested log
        :returns: logdict via Deferred

        Get a log, identified by logid.

    .. py:method:: getLogBySlug(stepid, slug)

        :param integer stepid: ID of the step containing this log
        :param slug: slug of the logfile to retrieve
        :type name: 50-character identifier
        :returns: logdict via Deferred

        Get a log, identified by name within the given step.

    .. py:method:: getLogs(stepid)

        :param integer stepid: ID of the step containing the desired logs
        :returns: list of logdicts via Deferred

        Get all logs within the given step.

    .. py:method:: getLogLines(logid, first_line, last_line)

        :param integer logid: ID of the log
        :param first_line: first line to return
        :param last_line: last line to return
        :returns: see below

        Get a subset of lines for a logfile.

        The return value, via Deferred, is a concatenation of newline-terminated strings.
        If the requested last line is beyond the end of the logfile, only existing lines will be included.
        If the log does not exist, or has no associated lines, this method returns an empty string.

    .. py:method:: addLog(stepid, name, type)

        :param integer stepid: ID of the step containing this log
        :param string name: name of the logfile
        :param slug: slug (unique identifier) of the logfile
        :type slug: 50-character identifier
        :param string type: log type (see above)
        :raises KeyError: if a log with the given slug already exists in the step
        :returns: ID of the new log, via Deferred

        Add a new log file to the given step.

    .. py:method:: appendLog(logid, content)

        :param integer logid: ID of the requested log
        :param string content: new content to be appended to the log
        :returns: tuple of first and last line numbers in the new chunk, via Deferred

        Append content to an existing log.
        The content must end with a newline.
        If the given log does not exist, the method will silently do nothing.

        It is not safe to call this method more than once simultaneously for the same ``logid``.

    .. py:method:: finishLog(logid)

        :param integer logid: ID of the log to mark complete
        :returns: Deferred

        Mark a log as complete.

        Note that no checking for completeness is performed when appending to a log.
        It is up to the caller to avoid further calls to ``appendLog`` after ``finishLog``.

    .. py:method:: compressLog(logid)

        :param integer logid: ID of the log to compress
        :returns: Deferred

        Compress the given log.
        This method performs internal optimizations of a log's chunks to reduce the space used and make read operations more efficient.
        It should only be called for finished logs.
        This method may take some time to complete.

    .. py:method:: deleteOldLogChunks(older_than_timestamp)

        :param integer older_than_timestamp: the logs whose step's ``started_at`` is older than ``older_than_timestamp`` will be deleted.
        :returns: Deferred

        Delete old logchunks (helper for the ``logHorizon`` policy).
        Old logs have their logchunks deleted from the database, but they keep their ``num_lines`` metadata.
        They have their types changed to 'd', so that the UI can display something meaningful.


buildsets
~~~~~~~~~

.. py:module:: buildbot.db.buildsets

.. index:: double: Buildsets; DB Connector Component

.. py:class:: BuildsetsConnectorComponent

    This class handles getting buildsets into and out of the database.
    Buildsets combine multiple build requests that were triggered together.

    An instance of this class is available at ``master.db.buildsets``.

    .. index:: bsdict, bsid

    Buildsets are indexed by *bsid* and their contents represented as *bsdicts*
    (buildset dictionaries), with keys

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
        :param unicode parent_relationship: relationship identifier for the parent, this is is configured relationship between the parent build, and the childs buildsets
        :returns: buildset ID and buildrequest IDs, via a Deferred

        Add a new Buildset to the database, along with BuildRequests for each builder, returning the resulting bsid via a Deferred.
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
        :param resultSpec: resultSpec containing filters sorting and paging request from data/REST API.
            If possible, the db layer can optimize the SQL query using this information.

        :returns: list of bsdicts, via Deferred

        Get a list of bsdicts matching the given criteria.

    .. py:method:: getRecentBuildsets(count=None, branch=None, repository=None,
                           complete=None):

        :param count: maximum number of buildsets to retrieve (required).
        :type count: integer
        :param branch: optional branch name. If specified, only buildsets
            affecting such branch will be returned.
        :type branch: string
        :param repository: optional repository name. If specified, only
            buildsets affecting such repository will be returned.
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

workers
~~~~~~~

.. py:module:: buildbot.db.workers

.. index:: double: Workers; DB Connector Component

.. py:class:: WorkersConnectorComponent

    This class handles Buildbot's notion of workers.
    The worker information is returned as a dictionary:

    * ``id``
    * ``name`` - the name of the worker
    * ``workerinfo`` - worker information as dictionary
    * ``paused`` - boolean indicating worker is paused and shall not take new builds
    * ``graceful`` - boolean indicating worker will be shutdown as soon as build finished
    * ``connected_to`` - a list of masters, by ID, to which this worker is currently connected.
      This list will typically contain only one master, but in unusual circumstances the same worker may appear to be connected to multiple masters simultaneously.
    * ``configured_on`` - a list of master-builder pairs, on which this worker is configured.
      Each pair is represented by a dictionary with keys ``buliderid`` and ``masterid``.

    The worker information can be any JSON-able object.
    See :bb:rtype:`worker` for more detail.

    .. py:method:: findWorkerId(name=name)

        :param name: worker name
        :type name: 50-character identifier
        :returns: worker ID via Deferred

        Get the ID for a worker, adding a new worker to the database if necessary.
        The worker information for a new worker is initialized to an empty dictionary.

    .. py:method:: getWorkers(masterid=None, builderid=None)

        :param integer masterid: limit to workers configured on this master
        :param integer builderid: limit to workers configured on this builder
        :returns: list of worker dictionaries, via Deferred

        Get a list of workers.
        If either or both of the filtering parameters either specified, then the result is limited to workers configured to run on that master or builder.
        The ``configured_on`` results are limited by the filtering parameters as well.
        The ``connected_to`` results are limited by the ``masterid`` parameter.

    .. py:method:: getWorker(workerid=None, name=None, masterid=None, builderid=None)

        :param string name: the name of the worker to retrieve
        :param integer workerid: the ID of the worker to retrieve
        :param integer masterid: limit to workers configured on this master
        :param integer builderid: limit to workers configured on this builder
        :returns: info dictionary or None, via Deferred

        Looks up the worker with the given name or ID, returning ``None`` if no matching worker is found.
        The ``masterid`` and ``builderid`` arguments function as they do for :py:meth:`getWorkers`.

    .. py:method:: workerConnected(workerid, masterid, workerinfo)

        :param integer workerid: the ID of the worker
        :param integer masterid: the ID of the master to which it connected
        :param workerinfo: the new worker information dictionary
        :type workerinfo: dict
        :returns: Deferred

        Record the given worker as attached to the given master, and update its cached worker information.
        The supplied information completely replaces any existing information.

    .. py:method:: workerDisconnected(workerid, masterid)

        :param integer workerid: the ID of the worker
        :param integer masterid: the ID of the master to which it connected
        :returns: Deferred

        Record the given worker as no longer attached to the given master.

    .. py:method:: workerConfigured(workerid, masterid, builderids)

        :param integer workerid: the ID of the worker
        :param integer masterid: the ID of the master to which it configured
        :param list of integer builderids: the ID of the builders to which it is configured
        :returns: Deferred

        Record the given worker as being configured on the given master and for given builders.
        This method will also remove any other builder that were configured previously for same (worker, master) combination.


    .. py:method:: deconfigureAllWorkersForMaster(masterid)

        :param integer masterid: the ID of the master to which it configured
        :returns: Deferred

        Unregister all the workers configured to a master for given builders.
        This shall happen when master disabled or before reconfiguration

    .. py:method:: setWorkerState(workerid, paused, graceful)

        :param integer workerid: the ID of the worker whose state is being changed
        :param integer paused: the paused state
        :param integer graceful: the graceful state
        :returns: Deferred

        Change the state of a worker (see definition of states above in worker dict description)

changes
~~~~~~~

.. py:module:: buildbot.db.changes

.. index:: double: Changes; DB Connector Component

.. py:class:: ChangesConnectorComponent

    This class handles changes in the buildbot database, including pulling
    information from the changes sub-tables.

    An instance of this class is available at ``master.db.changes``.

    .. index:: chdict, changeid

    Changes are indexed by *changeid*, and are represented by a *chdict*, which
    has the following keys:

    * ``changeid`` (the ID of this change)
    * ``parent_changeids`` (list of ID; change's parents)
    * ``author`` (unicode; the author of the change)
    * ``files`` (list of unicode; source-code filenames changed)
    * ``comments`` (unicode; user comments)
    * ``is_dir`` (deprecated)
    * ``links`` (list of unicode; links for this change, e.g., to web views,
      review)
    * ``revision`` (unicode string; revision for this change, or ``None`` if
      unknown)
    * ``when_timestamp`` (datetime instance; time of the change)
    * ``branch`` (unicode string; branch on which the change took place, or
      ``None`` for the "default branch", whatever that might mean)
    * ``category`` (unicode string; user-defined category of this change, or
      ``None``)
    * ``revlink`` (unicode string; link to a web view of this change)
    * ``properties`` (user-specified properties for this change, represented as
      a dictionary mapping keys to (value, source))
    * ``repository`` (unicode string; repository where this change occurred)
    * ``project`` (unicode string; user-defined project to which this change
      corresponds)

    .. py:method:: getParentChangeIds(branch, repository, project, codebase)

        :param branch: the branch of the change
        :type branch: unicode string
        :param repository: the repository in which this change took place
        :type repository: unicode string
        :param project: the project this change is a part of
        :type project: unicode string
        :param codebase:
        :type codebase: unicode string

        return the last changeID which matches the repository/project/codebase

    .. py:method:: addChange(author=None, files=None, comments=None, is_dir=0, links=None, revision=None, when_timestamp=None, branch=None, category=None, revlink='', properties={}, repository='', project='', uid=None)

        :param author: the author of this change
        :type author: unicode string
        :param files: a list of filenames that were changed
        :type branch: list of unicode strings
        :param comments: user comments on the change
        :type branch: unicode string
        :param is_dir: deprecated
        :param links: a list of links related to this change, e.g., to web
            viewers or review pages
        :type links: list of unicode strings
        :param revision: the revision identifier for this change
        :type revision: unicode string
        :param when_timestamp: when this change occurred, or the current time
            if None
        :type when_timestamp: datetime instance or None
        :param branch: the branch on which this change took place
        :type branch: unicode string
        :param category: category for this change (arbitrary use by Buildbot
            users)
        :type category: unicode string
        :param revlink: link to a web view of this revision
        :type revlink: unicode string
        :param properties: properties to set on this change, where values are
            tuples of (value, source).  At the moment, the source must be
            ``'Change'``, although this may be relaxed in later versions.
        :type properties: dictionary
        :param repository: the repository in which this change took place
        :type repository: unicode string
        :param project: the project this change is a part of
        :type project: unicode string
        :param uid: uid generated for the change author
        :type uid: integer
        :returns: new change's ID via Deferred

        Add a Change with the given attributes to the database, returning the
        changeid via a Deferred.  All arguments should be given as keyword
        arguments.

        The ``project`` and ``repository`` arguments must be strings; ``None``
        is not allowed.

    .. py:method:: getChange(changeid, no_cache=False)

        :param changeid: the id of the change instance to fetch
        :param no_cache: bypass cache and always fetch from database
        :type no_cache: boolean
        :returns: chdict via Deferred

        Get a change dictionary for the given changeid, or ``None`` if no such
        change exists.

    .. py:method:: getChangeUids(changeid)

        :param changeid: the id of the change instance to fetch
        :returns: list of uids via Deferred

        Get the userids associated with the given changeid.

    .. py:method:: getRecentChanges(count)

        :param count: maximum number of instances to return
        :returns: list of dictionaries via Deferred, ordered by changeid

        Get a list of the ``count`` most recent changes, represented as
        dictionaries; returns fewer if that many do not exist.

        .. note::
            For this function, "recent" is determined by the order of the
            changeids, not by ``when_timestamp``.  This is most apparent in
            DVCS's, where the timestamp of a change may be significantly
            earlier than the time at which it is merged into a repository
            monitored by Buildbot.

    .. py:method:: getChanges()

        :returns: list of dictionaries via Deferred

        Get a list of the changes, represented as
        dictionaries; changes are sorted, and paged using generic data query options

    .. py:method:: getChangesCount()

        :returns: list of dictionaries via Deferred

        Get the number changes, that the query option would return if no
        paging option where set


    .. py:method:: getLatestChangeid()

        :returns: changeid via Deferred

        Get the most-recently-assigned changeid, or ``None`` if there are no
        changes at all.


    .. py:method:: getChangesForBuild(buildid)

        :param buildid: ID of the build
        :returns: list of dictionaries via Deferred

        Get the "blame" list of changes for a build.

    .. py:method:: getChangeFromSSid(sourcestampid)

        :param sourcestampid: ID of the sourcestampid
        :returns: chdict via Deferred

        returns the change dictionary related to the sourcestamp ID.

changesources
~~~~~~~~~~~~~

.. py:module:: buildbot.db.changesources

.. index:: double: ChangeSources; DB Connector Component

.. py:exception:: ChangeSourceAlreadyClaimedError

    Raised when a changesource request is already claimed by another master.

.. py:class:: ChangeSourcesConnectorComponent

    This class manages the state of the Buildbot changesources.

    An instance of this class is available at ``master.db.changesources``.

    Changesources are identified by their changesourceid, which can be obtained from :py:meth:`findChangeSourceId`.

    Changesources are represented by dictionaries with the following keys:

        * ``id`` - changesource's ID
        * ``name`` - changesource's name
        * ``masterid`` - ID of the master currently running this changesource, or None if it is inactive

    Note that this class is conservative in determining what changesources are inactive: a changesource linked to an inactive master is still considered active.
    This situation should never occur, however; links to a master should be deleted when it is marked inactive.

    .. py:method:: findChangeSourceId(name)

        :param name: changesource name
        :returns: changesource ID via Deferred

        Return the changesource ID for the changesource with this name.
        If such a changesource is already in the database, this returns the ID.
        If not, the changesource is added to the database and its ID returned.

    .. py:method:: setChangeSourceMaster(changesourceid, masterid)

        :param changesourceid: changesource to set the master for
        :param masterid: new master for this changesource, or None
        :returns: Deferred

        Set, or unset if ``masterid`` is None, the active master for this changesource.
        If no master is currently set, or the current master is not active, this method will complete without error.
        If the current master is active, this method will raise :py:exc:`~buildbot.db.exceptions.ChangeSourceAlreadyClaimedError`.

    .. py:method:: getChangeSource(changesourceid)

        :param changesourceid: changesource ID
        :returns: changesource dictionary or None, via Deferred

        Get the changesource dictionary for the given changesource.

    .. py:method:: getChangeSources(active=None, masterid=None)

        :param boolean active: if specified, filter for active or inactive changesources
        :param integer masterid: if specified, only return changesources attached associated with this master
        :returns: list of changesource dictionaries in unspecified order

        Get a list of changesources.

        If ``active`` is given, changesources are filtered according to whether they are active (true) or inactive (false).
        An active changesource is one that is claimed by an active master.

        If ``masterid`` is given, the list is restricted to schedulers associated with that master.


schedulers
~~~~~~~~~~

.. py:module:: buildbot.db.schedulers

.. index:: double: Schedulers; DB Connector Component

.. py:exception:: SchedulerAlreadyClaimedError

    Raised when a scheduler request is already claimed by another master.

.. py:class:: SchedulersConnectorComponent

    This class manages the state of the Buildbot schedulers.  This state includes
    classifications of as-yet un-built changes.

    An instance of this class is available at ``master.db.schedulers``.

    Schedulers are identified by their schedulerid, which can be obtained from :py:meth:`findSchedulerId`.

    Schedulers are represented by dictionaries with the following keys:

        * ``id`` - scheduler's ID
        * ``name`` - scheduler's name
        * ``masterid`` - ID of the master currently running this scheduler, or None if it is inactive

    Note that this class is conservative in determining what schedulers are inactive: a scheduler linked to an inactive master is still considered active.
    This situation should never occur, however; links to a master should be deleted when it is marked inactive.

    .. py:method:: classifyChanges(objectid, classifications)

        :param schedulerid: ID of the scheduler classifying the changes
        :param classifications: mapping of changeid to boolean, where the boolean
            is true if the change is important, and false if it is unimportant
        :type classifications: dictionary
        :returns: Deferred

        Record the given classifications.  This method allows a scheduler to
        record which changes were important and which were not immediately,
        even if the build based on those changes will not occur for some time
        (e.g., a tree stable timer).  Schedulers should be careful to flush
        classifications once they are no longer needed, using
        :py:meth:`flushChangeClassifications`.

    .. py:method:: flushChangeClassifications(objectid, less_than=None)

        :param schedulerid: ID of the scheduler owning the flushed changes
        :param less_than: (optional) lowest changeid that should *not* be flushed
        :returns: Deferred

        Flush all scheduler_changes for the given scheduler, limiting to those
        with changeid less than ``less_than`` if the parameter is supplied.

    .. py:method:: getChangeClassifications(objectid[, branch])

        :param schedulerid: ID of scheduler to look up changes for
        :type schedulerid: integer
        :param branch: (optional) limit to changes with this branch
        :type branch: string or None (for default branch)
        :returns: dictionary via Deferred

        Return the classifications made by this scheduler, in the form of a
        dictionary mapping changeid to a boolean, just as supplied to
        :py:meth:`classifyChanges`.

        If ``branch`` is specified, then only changes on that branch will be
        given.  Note that specifying ``branch=None`` requests changes for the
        default branch, and is not the same as omitting the ``branch`` argument
        altogether.

    .. py:method:: findSchedulerId(name)

        :param name: scheduler name
        :returns: scheduler ID via Deferred

        Return the scheduler ID for the scheduler with this name.
        If such a scheduler is already in the database, this returns the ID.
        If not, the scheduler is added to the database and its ID returned.

    .. py:method:: setSchedulerMaster(schedulerid, masterid)

        :param schedulerid: scheduler to set the master for
        :param masterid: new master for this scheduler, or None
        :returns: Deferred

        Set, or unset if ``masterid`` is None, the active master for this scheduler.
        If no master is currently set, or the current master is not active, this method will complete without error.
        If the current master is active, this method will raise :py:exc:`~buildbot.db.exceptions.SchedulerAlreadyClaimedError`.

    .. py:method:: getScheduler(schedulerid)

        :param schedulerid: scheduler ID
        :returns: scheduler dictionary or None via Deferred

        Get the scheduler dictionary for the given scheduler.

    .. py:method:: getSchedulers(active=None, masterid=None)

        :param boolean active: if specified, filter for active or inactive schedulers
        :param integer masterid: if specified, only return schedulers attached associated with this master
        :returns: list of scheduler dictionaries in unspecified order

        Get a list of schedulers.

        If ``active`` is given, schedulers are filtered according to whether they are active (true) or inactive (false).
        An active scheduler is one that is claimed by an active master.

        If ``masterid`` is given, the list is restricted to schedulers associated with that master.


sourcestamps
~~~~~~~~~~~~

.. py:module:: buildbot.db.sourcestamps

.. index:: double: SourceStamps; DB Connector Component

.. py:class:: SourceStampsConnectorComponent

    This class manages source stamps, as stored in the database.
    A source stamp uniquely identifies a particular version a single codebase.
    Source stamps are identified by their ID.
    It is safe to use sourcestamp ID equality as a proxy for source stamp equality.
    For example, all builds of a particular version of a codebase will share the same sourcestamp ID.
    This equality does not extend to patches: two sourcestamps generated with exactly the same patch will have different IDs.

    Relative source stamps have a ``revision`` of None, meaning "whatever the latest is when this sourcestamp is interpreted".
    While such source stamps may correspond to a wide array of revisions over the lifetime of a buildbot install, they will only ever have one ID.

    An instance of this class is available at ``master.db.sourcestamps``.

    .. index:: ssid, ssdict

    * ``ssid``
    * ``branch`` (branch, or ``None`` for default branch)
    * ``revision`` (revision, or ``None`` to indicate the latest revision, in
      which case this is a relative source stamp)
    * ``patchid`` (ID of the patch)
    * ``patch_body`` (body of the patch, or ``None``)
    * ``patch_level`` (directory stripping level of the patch, or ``None``)
    * ``patch_subdir`` (subdirectory in which to apply the patch, or ``None``)
    * ``patch_author`` (author of the patch, or ``None``)
    * ``patch_comment`` (comment for the patch, or ``None``)
    * ``repository`` (repository containing the source; never ``None``)
    * ``project`` (project this source is for; never ``None``)
    * ``codebase`` (codebase this stamp is in; never ``None``)
    * ``created_at`` (timestamp when this stamp was first created)

    Note that the patch body is a bytestring, not a unicode string.

    .. py:method:: findSourceStampId(branch=None, revision=Node,
                        repository=None, project=None, patch_body=None,
                        patch_level=None, patch_author=None, patch_comment=None,
                        patch_subdir=None):

        :param branch:
        :type branch: unicode string or None
        :param revision:
        :type revision: unicode string or None
        :param repository:
        :type repository: unicode string or None
        :param project:
        :type project: unicode string or None
        :param codebase:
        :type codebase: unicode string (required)
        :param patch_body: patch body
        :type patch_body: unicode string or None
        :param patch_level: patch level
        :type patch_level: integer or None
        :param patch_author: patch author
        :type patch_author: unicode string or None
        :param patch_comment: patch comment
        :type patch_comment: unicode string or None
        :param patch_subdir: patch subdir
        :type patch_subdir: unicode string or None
        :returns: ssid, via Deferred

        Create a new SourceStamp instance with the given attributes, or find an existing one.
        In either case, return its ssid.
        The arguments all have the same meaning as in an ssdict.

        If a new SourceStamp is created, its ``created_at`` is set to the current time.

    .. py:method:: getSourceStamp(ssid)

        :param ssid: sourcestamp to get
        :param no_cache: bypass cache and always fetch from database
        :type no_cache: boolean
        :returns: ssdict, or ``None``, via Deferred

        Get an ssdict representing the given source stamp, or ``None`` if no
        such source stamp exists.

    .. py:method:: getSourceStamps()

        :returns: list of ssdict, via Deferred

        Get all sourcestamps in the database.
        You probably don't want to do this!
        This method will be extended to allow appropriate filtering.

    .. py:method:: getSourceStampsForBuild(buildid)

        :param buildid: build ID
        :returns: list of ssdict, via Deferred

        Get sourcestamps related to a build.

state
~~~~~

.. py:module:: buildbot.db.state

.. index:: double: State; DB Connector Component

.. py:class:: StateConnectorComponent

    This class handles maintaining arbitrary key/value state for Buildbot
    objects.  Each object can store arbitrary key/value pairs, where the values
    are any JSON-encodable value.  Each pair can be set and retrieved
    atomically.

    Objects are identified by their (user-visible) name and their
    class.  This allows, for example, a ``nightly_smoketest`` object of class
    ``NightlyScheduler`` to maintain its state even if it moves between
    masters, but avoids cross-contaminating state between different classes
    of objects with the same name.

    Note that "class" is not interpreted literally, and can be any string that
    will uniquely identify the class for the object; if classes are renamed,
    they can continue to use the old names.

    An instance of this class is available at ``master.db.state``.

    .. index:: objectid, objdict

    Objects are identified by *objectid*.

    .. py:method:: getObjectId(name, class_name)

        :param name: name of the object
        :param class_name: object class name
        :returns: the objectid, via a Deferred.

        Get the object ID for this combination of a name and a class.  This
        will add a row to the 'objects' table if none exists already.

    .. py:method:: getState(objectid, name[, default])

        :param objectid: objectid on which the state should be checked
        :param name: name of the value to retrieve
        :param default: (optional) value to return if ``name`` is not present
        :returns: state value via a Deferred
        :raises KeyError: if ``name`` is not present and no default is given
        :raises: TypeError if JSON parsing fails

        Get the state value for key ``name`` for the object with id
        ``objectid``.

    .. py:method:: setState(objectid, name, value)

        :param objectid: the objectid for which the state should be changed
        :param name: the name of the value to change
        :param value: the value to set
        :type value: JSON-able value
        :param returns: value actually written via Deferred
        :raises: TypeError if JSONification fails

        Set the state value for ``name`` for the object with id ``objectid``,
        overwriting any existing value.
        In case of two racing writes, the first (as per db rule) one wins, the seconds returns the value from the first.

    .. py:method:: atomicCreateState(objectid, name, thd_create_callback)

        :param objectid: the objectid for which the state should be created
        :param name: the name of the value to create
        :param thd_create_callback: the function to call from thread to create the value if non-existent. (returns JSON-able value)
        :param returns: Deferred
        :raises: TypeError if JSONification fails

        Atomically creates the state value for ``name`` for the object with id ``objectid``,
        If there is an existing value, returns that instead.
        This implementation ensures the state is created only once for the whole cluster.

    Those 3 methods have their threaded equivalent, ``thdGetObjectId``, ``thdGetState``, ``thdSetState`` that are intended to run in synchronous code, (e.g master.cfg environment)

users
~~~~~

.. py:module:: buildbot.db.users

.. index:: double: Users; DB Connector Component

.. py:class:: UsersConnectorComponent

    This class handles Buildbot's notion of users.  Buildbot tracks the usual
    information about users -- username and password, plus a display name.

    The more complicated task is to recognize each user across multiple
    interfaces with Buildbot.  For example, a user may be identified as
    'djmitche' in Subversion, 'dustin@v.igoro.us' in Git, and 'dustin' on IRC.
    To support this functionality, each user as a set of attributes, keyed by
    type.  The :py:meth:`findUserByAttr` method uses these attributes to match users,
    adding a new user if no matching user is found.

    Users are identified canonically by *uid*, and are represented by *usdicts* (user
    dictionaries) with keys

    * ``uid``
    * ``identifier`` (display name for the user)
    * ``bb_username`` (buildbot login username)
    * ``bb_password`` (hashed login password)

    All attributes are also included in the dictionary, keyed by type.  Types
    colliding with the keys above are ignored.

    .. py:method:: findUserByAttr(identifier, attr_type, attr_data)

        :param identifier: identifier to use for a new user
        :param attr_type: attribute type to search for and/or add
        :param attr_data: attribute data to add
        :returns: userid via Deferred

        Get an existing user, or add a new one, based on the given attribute.

        This method is intended for use by other components of Buildbot to
        search for a user with the given attributes.

        Note that ``identifier`` is *not* used in the search for an existing
        user.  It is only used when creating a new user.  The identifier should
        be based deterministically on the attributes supplied, in some fashion
        that will seem natural to users.

        For future compatibility, always use keyword parameters to call this
        method.

    .. py:method:: getUser(uid)

        :param uid: user id to look up
        :type key: int
        :param no_cache: bypass cache and always fetch from database
        :type no_cache: boolean
        :returns: usdict via Deferred

        Get a usdict for the given user, or ``None`` if no matching user is
        found.

    .. py:method:: getUserByUsername(username)

        :param username: username portion of user credentials
        :type username: string
        :returns: usdict or None via deferred

        Looks up the user with the bb_username, returning the usdict or
        ``None`` if no matching user is found.

    .. py:method:: getUsers()

        :returns: list of partial usdicts via Deferred

        Get the entire list of users.  User attributes are not included, so the
        results are not full userdicts.

    .. py:method:: updateUser(uid=None, identifier=None, bb_username=None, bb_password=None, attr_type=None, attr_data=None)

        :param uid: the user to change
        :type uid: int
        :param identifier: (optional) new identifier for this user
        :type identifier: string
        :param bb_username: (optional) new buildbot username
        :type bb_username: string
        :param bb_password: (optional) new hashed buildbot password
        :type bb_password: string
        :param attr_type: (optional) attribute type to update
        :type attr_type: string
        :param attr_data: (optional) value for ``attr_type``
        :type attr_data: string
        :returns: Deferred

        Update information about the given user.  Only the specified attributes
        are updated.  If no user with the given uid exists, the method will
        return silently.

        Note that ``bb_password`` must be given if ``bb_username`` appears;
        similarly, ``attr_type`` requires ``attr_data``.

    .. py:method:: removeUser(uid)

        :param uid: the user to remove
        :type uid: int
        :returns: Deferred

        Remove the user with the given uid from the database.  This will remove
        the user from any associated tables as well.

    .. py:method:: identifierToUid(identifier)

        :param identifier: identifier to search for
        :type identifier: string
        :returns: uid or ``None``, via Deferred

        Fetch a uid for the given identifier, if one exists.


masters
~~~~~~~

.. py:module:: buildbot.db.masters

.. index:: double: Masters; DB Connector Component

.. py:class:: MastersConnectorComponent

    This class handles tracking the buildmasters in a multi-master configuration.
    Masters "check in" periodically.
    Other masters monitor the last activity times, and mark masters that have not recently checked in as inactive.

    Masters are represented by master dictionaries with the following keys:

    * ``id`` -- the ID of this master
    * ``name`` -- the name of the master (generally of the form ``hostname:basedir``)
    * ``active`` -- true if this master is running
    * ``last_active`` -- time that this master last checked in (a datetime object)

    .. py:method:: findMasterId(name)

        :param unicode name: name of this master
        :returns: master id via Deferred

        Return the master ID for the master with this master name (generally ``hostname:basedir``).
        If such a master is already in the database, this returns the ID.
        If not, the master is added to the database, with ``active=False``, and its ID returned.

    .. py:method:: setMasterState(masterid, active)

        :param integer masterid: the master to check in
        :param boolean active: whether to mark this master as active or inactive
        :returns: boolean via Deferred

        Mark the given master as active or inactive, returning true if the state actually changed.
        If ``active`` is true, the ``last_active`` time is updated to the current time.
        If ``active`` is false, then any links to this master, such as schedulers, will be deleted.

    .. py:method:: getMaster(masterid)

        :param integer masterid: the master to check in
        :returns: Master dict or None via Deferred

        Get the indicated master.

    .. py:method:: getMasters()

        :returns: list of Master dicts via Deferred

        Get a list of the masters, represented as dictionaries; masters are sorted
        and paged using generic data query options

    .. py:method:: setAllMastersActiveLongTimeAgo()

        :returns: None via Deferred

        This method is intended to be call by upgrade-master, and will effectively force housekeeping on all masters at next startup.
        This method is not intended to be called outside of housekeeping scripts.

builders
~~~~~~~~

.. py:module:: buildbot.db.builders

.. index:: double: Builders; DB Connector Component

.. py:class:: BuildersConnectorComponent

    This class handles the relationship between builder names and their IDs, as well as tracking which masters are configured for this builder.

    Builders are represented by master dictionaries with the following keys:

    * ``id`` -- the ID of this builder
    * ``name``  -- the builder name, a 20-character :ref:`identifier <type-identifier>`
    * ``masterids`` -- the IDs of the masters where this builder is configured (sorted by id)

    .. py:method:: findBuilderId(name, autoCreate=True)

        :param name: name of this builder
        :type name: 20-character :ref:`identifier <type-identifier>`
        :param autoCreate: automatically create the builder if name not found
        :type autoCreate: bool
        :returns: builder id via Deferred

        Return the builder ID for the builder with this builder name.
        If such a builder is already in the database, this returns the ID.
        If not and ``autoCreate`` is True, the builder is added to the database.

    .. py:method:: addBuilderMaster(builderid=None, masterid=None)

        :param integer builderid: the builder
        :param integer masterid: the master
        :returns: Deferred

        Add the given master to the list of masters on which the builder is configured.
        This will do nothing if the master and builder are already associated.

    .. py:method:: removeBuilderMaster(builderid=None, masterid=None)

        :param integer builderid: the builder
        :param integer masterid: the master
        :returns: Deferred

        Remove the given master from the list of masters on which the builder is configured.

    .. py:method:: getBuilder(builderid)

        :param integer builderid: the builder to check in
        :returns: Builder dict or None via Deferred

        Get the indicated builder.

    .. py:method:: getBuilders(masterid=None)

        :param integer masterid: ID of the master to which the results should be limited
        :returns: list of Builder dicts via Deferred

        Get all builders (in unspecified order).
        If ``masterid`` is given, then only builders configured on that master are returned.


Writing Database Connector Methods
----------------------------------

The information above is intended for developers working on the rest of
Buildbot, and treating the database layer as an abstraction.  The remainder of
this section describes the internals of the database implementation, and is
intended for developers modifying the schema or adding new methods to the
database layer.

.. warning::

    It's difficult to change the database schema significantly after it has
    been released, and very disruptive to users to change the database API.
    Consider very carefully the future-proofing of any changes here!

The DB Connector and Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.connector

.. py:class:: DBConnector

    The root of the database connectors, ``master.db``, is a
    :class:`~buildbot.db.connector.DBConnector` instance.  Its main purpose is
    to hold reference to each of the connector components, but it also handles
    timed cleanup tasks.

    If you are adding a new connector component, import its module and create
    an instance of it in this class's constructor.

.. py:module:: buildbot.db.base

.. py:class:: DBConnectorComponent

    This is the base class for connector components.

    There should be no need to override the constructor defined by this base
    class.

    .. py:attribute:: db

        A reference to the :class:`~buildbot.db.connector.DBConnector`, so that
        connector components can use e.g., ``self.db.pool`` or
        ``self.db.model``.  In the unusual case that a connector component
        needs access to the master, the easiest path is ``self.db.master``.

    .. py:method:: checkLength(col, value)

        For use by subclasses to check that 'value' will fit in 'col', where 'col' is a table column from the model.
        Ignore this check for database engines that either provide this error themselves (postgres) or that do not enforce maximum-length restrictions (sqlite)

    .. py:method:: findSomethingId(self, tbl, whereclause, insert_values, _race_hook=None, autoCreate=True)

        Find (using ``whereclause``) or add (using ``insert_values``) a row to
        ``table``, and return the resulting ID. If ``autoCreate`` == False, we will not automatically insert the row.

    .. py:method:: hashColumns(*args)

        Hash the given values in a consistent manner: None is represented as \xf5, an invalid unicode byte; strings are converted to utf8; and integers are represented by their decimal expansion.
        The values are then joined by '\0' and hashed with sha1.

    .. py:method:: doBatch(batch, batch_n=500)

        returns an Iterator that batches stuff in order to not push to many thing in a single request.
        Especially sqlite has 999 limit on argument it can take in a requests.

Direct Database Access
~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.pool

The connectors all use `SQLAlchemy Core
<http://www.sqlalchemy.org/docs/index.html>`_ as a wrapper around database
client drivers.  Unfortunately, SQLAlchemy is a synchronous library, so some
extra work is required to use it in an asynchronous context like Buildbot.
This is accomplished by deferring all database operations to threads, and
returning a Deferred.  The :class:`~buildbot.db.pool.Pool` class takes care of
the details.

A connector method should look like this::

    def myMethod(self, arg1, arg2):
        def thd(conn):
            q = ... # construct a query
            for row in conn.execute(q):
                ... # do something with the results
            return ... # return an interesting value
        return self.db.pool.do(thd)

Picking that apart, the body of the method defines a function named ``thd``
taking one argument, a :class:`Connection
<sqlalchemy:sqlalchemy.engine.base.Connection>` object.  It then calls
``self.db.pool.do``, passing the ``thd`` function.  This function is called in
a thread, and can make blocking calls to SQLAlchemy as desired.  The ``do``
method will return a Deferred that will fire with the return value of ``thd``,
or with a failure representing any exceptions raised by ``thd``.

The return value of ``thd`` must not be an SQLAlchemy object - in particular,
any :class:`ResultProxy <sqlalchemy:sqlalchemy.engine.base.ResultProxy>`
objects must be parsed into lists or other data structures before they are
returned.

.. warning::

    As the name ``thd`` indicates, the function runs in a thread.  It should
    not interact with any other part of Buildbot, nor with any of the Twisted
    components that expect to be accessed from the main thread -- the reactor,
    Deferreds, etc.

Queries can be constructed using any of the SQLAlchemy core methods, using
tables from :class:`~buildbot.db.model.Model`, and executed with the connection
object, ``conn``.

.. note::

    SQLAlchemy requires the use of a syntax that is forbidden by pep8.
    If in where clauses you need to select rows where a value is NULL,
    you need to write (`tbl.c.value == None`). This form is forbidden by pep8
    which requires the use of `is None` instead of `== None`. As sqlalchemy is using operator
    overloading to implement pythonic SQL statements, and `is` operator is not overloadable,
    we need to keep the `==` operators. In order to solve this issue, buildbot
    uses `buildbot.db.NULL` constant, which is `None`.
    So instead of writing `tbl.c.value == None`, please write `tbl.c.value == NULL`)


.. py:class:: DBThreadPool

    .. py:method:: do(callable, ...)

        :returns: Deferred

        Call ``callable`` in a thread, with a :class:`Connection
        <sqlalchemy:sqlalchemy.engine.base.Connection>` object as first
        argument.  Returns a deferred that will fire with the results of the
        callable, or with a failure representing any exception raised during
        its execution.

        Any additional positional or keyword arguments are passed to
        ``callable``.

    .. py:method:: do_with_engine(callable, ...)

        :returns: Deferred

        Similar to :meth:`do`, call ``callable`` in a thread, but with an
        :class:`Engine <sqlalchemy:sqlalchemy.engine.base.Engine>` object as
        first argument.

        This method is only used for schema manipulation, and should not be
        used in a running master.

Database Schema
~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.model

Database connector methods access the database through SQLAlchemy, which
requires access to Python objects representing the database tables.  That is
handled through the model.

.. py:class:: Model

    This class contains the canonical description of the buildbot schema, It is
    presented in the form of SQLAlchemy :class:`Table
    <sqlalchemy:sqlalchemy.schema.Table>` instances, as class variables.  At
    runtime, the model is available at ``master.db.model``, so for example the
    ``buildrequests`` table can be referred to as
    ``master.db.model.buildrequests``, and columns are available in its ``c``
    attribute.

    The source file, :src:`master/buildbot/db/model.py`, contains comments describing each table; that information is not replicated in this documentation.

    Note that the model is not used for new installations or upgrades of the
    Buildbot database.  See :ref:`Modifying-the-Database-Schema` for more
    information.

    .. py:attribute:: metadata

        The model object also has a ``metadata`` attribute containing a
        :class:`MetaData <sqlalchemy:sqlalchemy.schema.MetaData>` instance.
        Connector methods should not need to access this object.  The metadata
        is not bound to an engine.

    The :py:class:`Model` class also defines some migration-related methods:

    .. py:method:: is_current()

        :returns: boolean via Deferred

        Returns true if the current database's version is current.

    .. py:method:: upgrade()

        :returns: Deferred

        Upgrades the database to the most recent schema version.

Caching
~~~~~~~

.. py:currentmodule:: buildbot.db.base

Connector component methods that get an object based on an ID are good
candidates for caching.  The :func:`~buildbot.db.base.cached` decorator
makes this automatic:

.. py:function:: cached(cachename)

    :param cache_name: name of the cache to use

    A decorator for "getter" functions that fetch an object from the database
    based on a single key.  The wrapped method will only be called if the named
    cache does not contain the key.

    The wrapped function must take one argument (the key); the wrapper will
    take a key plus an optional ``no_cache`` argument which, if true, will
    cause it to invoke the underlying method even if the key is in the cache.

    The resulting method will have a ``cache`` attribute which can be used to
    access the underlying cache.

In most cases, getter methods return a well-defined dictionary.  Unfortunately,
Python does not handle weak references to bare dictionaries, so components must
instantiate a subclass of ``dict``.  The whole assembly looks something like
this::

    class ThDict(dict):
        pass

    class ThingConnectorComponent(base.DBConnectorComponent):

        @base.cached('thdicts')
        def getThing(self, thid):
            def thd(conn):
                ...
                thdict = ThDict(thid=thid, attr=row.attr, ...)
                return thdict
            return self.db.pool.do(thd)

Tests
~~~~~

It goes without saying that any new connector methods must be fully tested!

You will also want to add an in-memory implementation of the methods to the
fake classes in ``master/buildbot/test/fake/fakedb.py``.  Non-DB Buildbot code
is tested using these fake implementations in order to isolate that code from
the database code, and to speed-up tests.

The keys and types used in the return value from a connector's ``get`` methods are described in :src:`master/buildbot/test/util/validation.py`, via the ``dbdict`` module-level value.
This is a dictionary of ``DictValidator`` objects, one for each return value.

These values are used within test methods like this::

    rv = yield self.db.masters.getMaster(7)
    validation.verifyDbDict(self, 'masterdict', rv)

.. _Modifying-the-Database-Schema:

Modifying the Database Schema
-----------------------------

Changes to the schema are accomplished through migration scripts, supported by
`SQLAlchemy-Migrate <https://github.com/openstack/sqlalchemy-migrate>`_.  In fact,
even new databases are created with the migration scripts -- a new database is
a migrated version of an empty database.

The schema is tracked by a version number, stored in the ``migrate_version``
table.  This number is incremented for each change to the schema, and used to
determine whether the database must be upgraded.  The master will refuse to run
with an out-of-date database.

To make a change to the schema, first consider how to handle any existing data.
When adding new columns, this may not be necessary, but table refactorings can
be complex and require caution so as not to lose information.

Create a new script in :src:`master/buildbot/db/migrate/versions`, following the numbering scheme already present.
The script should have an ``update`` method, which takes an engine as a parameter, and upgrades the database, both changing the schema and performing any required data migrations.
The engine passed to this parameter is "enhanced" by SQLAlchemy-Migrate, with methods to handle adding, altering, and dropping columns.
See the SQLAlchemy-Migrate documentation for details.

Next, modify :src:`master/buildbot/db/model.py` to represent the updated schema.
Buildbot's automated tests perform a rudimentary comparison of an upgraded database with the model, but it is important to check the details - key length, nullability, and so on can sometimes be missed by the checks.
If the schema and the upgrade scripts get out of sync, bizarre behavior can result.

Also, adjust the fake database table definitions in :src:`master/buildbot/test/fake/fakedb.py` according to your changes.

Your upgrade script should have unit tests.  The classes in :src:`master/buildbot/test/util/migration.py` make this straightforward.
Unit test scripts should be named e.g., :file:`test_db_migrate_versions_015_remove_bad_master_objectid.py`.

The :src:`master/buildbot/test/integration/test_upgrade.py <master/buildbot/test/integration/test_upgrade.py>` also tests
upgrades, and will confirm that the resulting database matches the model.  If
you encounter implicit indexes on MySQL, that do not appear on SQLite or
Postgres, add them to ``implied_indexes`` in
:file:`master/buidlbot/db/model.py`.

Foreign key checking
--------------------
PostgreSQL and SQlite db backends are checking the foreign keys consistency.
:bug:`2248` needs to be fixed so that we can support foreign key checking for MySQL.

To maintain consistency with real db, fakedb can check the foreign key consistency of your test data. For this, just enable it with::

    self.db = fakedb.FakeDBConnector(self.master, self)
    self.db.checkForeignKeys = True

Note that tests that only use fakedb do not really need foreign key consistency, even if this is a good practice to enable it in new code.


.. note:

    Since version `3.6.19 <https://www.sqlite.org/releaselog/3_6_19.html>`_, sqlite can do `foreignkey checks <https://www.sqlite.org/pragma.html#pragma_foreign_key_check>`_, which help a lot for testing foreign keys constraint in a developer friendly environment.
    For compat reason, they decided to disable foreign key checks by default.
    Since 0.9.0b8, buildbot now enforces by default the foreign key checking, and is now dependent on sqlite3 >3.6.19, which was released in 2009.
    One consequence of default disablement is that sqlalchemy-migrate backend for sqlite is not well prepared for foreign key checks, and we have to disable them in the migration scripts.


Database Compatibility Notes
----------------------------

Or: "If you thought any database worked right, think again"

Because Buildbot works over a wide range of databases, it is generally limited
to database features present in all supported backends.  This section
highlights a few things to watch out for.

In general, Buildbot should be functional on all supported database backends.
If use of a backend adds minor usage restrictions, or cannot implement some
kinds of error checking, that is acceptable if the restrictions are
well-documented in the manual.

The metabuildbot tests Buildbot against all supported databases, so most
compatibility errors will be caught before a release.

Index Length in MySQL
~~~~~~~~~~~~~~~~~~~~~

.. index:: single: MySQL; limitations

MySQL only supports about 330-character indexes. The actual index length is
1000 bytes, but MySQL uses 3-byte encoding for UTF8 strings.  This is a
longstanding bug in MySQL - see `"Specified key was too long; max key
length is 1000 bytes" with utf8 <http://bugs.mysql.com/bug.php?id=4541>`_.
While this makes sense for indexes used for record lookup, it limits the
ability to use unique indexes to prevent duplicate rows.

InnoDB only supports indexes up to 255 unicode characters, which is why
all indexed columns are limited to 255 characters in Buildbot.

Transactions in MySQL
~~~~~~~~~~~~~~~~~~~~~

.. index:: single: MySQL; limitations

Unfortunately, use of the MyISAM storage engine precludes real transactions in
MySQL.  ``transaction.commit()`` and ``transaction.rollback()`` are essentially
no-ops: modifications to data in the database are visible to other users
immediately, and are not reverted in a rollback.

Referential Integrity in SQLite and MySQL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. index:: single: SQLite; limitations
.. index:: single: MySQL; limitations

Neither MySQL nor SQLite enforce referential integrity based on foreign keys.
Postgres does enforce, however.  If possible, test your changes on Postgres
before committing, to check that tables are added and removed in the proper
order.

Subqueries in MySQL
~~~~~~~~~~~~~~~~~~~

.. index:: single: MySQL; limitations

MySQL's query planner is easily confused by subqueries.  For example, a DELETE
query specifying id's that are IN a subquery will not work.  The workaround is
to run the subquery directly, and then execute a DELETE query for each returned
id.

If this weakness has a significant performance impact, it would be acceptable to
conditionalize use of the subquery on the database dialect.

Too Many Variables in SQLite
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. index:: single: SQLite; limitations

Sqlite has a limitation on the number of variables it can use.
This limitation is usually `SQLITE_LIMIT_VARIABLE_NUMBER=999 <http://www.sqlite.org/c3ref/c_limit_attached.html#sqlitelimitvariablenumber>`_.
There is currently no way with pysqlite to query the value of this limit.
The C-api ``sqlite_limit`` is just not bound to the python.

When you hit this problem, you will get error like the following:

.. code-block:: none

    sqlalchemy.exc.OperationalError: (OperationalError) too many SQL variables
    u'DELETE FROM scheduler_changes WHERE scheduler_changes.changeid IN (?, ?, ?, ......tons of ?? and IDs .... 9363, 9362, 9361)

You can use the method :py:meth:`doBatch` in order to write batching code in a consistent manner.

Testing migrations with real databases
--------------------------------------

By default Buildbot test suite uses SQLite database for testings database
migrations.
To use other database set ``BUILDBOT_TEST_DB_URL`` environment variable to
value in `SQLAlchemy database URL specification
<http://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls>`_.

For example, to run tests with file-based SQLite database you can start
tests in the following way:

.. code-block:: bash

   BUILDBOT_TEST_DB_URL=sqlite:////tmp/test_db.sqlite trial buildbot.test

Run databases in Docker
~~~~~~~~~~~~~~~~~~~~~~~

`Docker <https://www.docker.com/>`_ allows to easily install and configure
different databases locally in containers.

To run tests with PostgreSQL:

.. code-block:: bash

   # Install psycopg.
   pip install psycopg2
   # Start container with PostgreSQL 9.5.
   # It will listen on port 15432 on localhost.
   sudo docker run --name bb-test-postgres -e POSTGRES_PASSWORD=password \
       -p 127.0.0.1:15432:5432 -d postgres:9.5
   # Start interesting tests
   BUILDBOT_TEST_DB_URL=postgresql://postgres:password@localhost:15432/postgres \
       trial buildbot.test

To run tests with MySQL:

.. code-block:: bash

   # Install mysqlclient
   pip install mysqlclient
   # Start container with MySQL 5.5.
   # It will listen on port 13306 on localhost.
   sudo docker run --name bb-test-mysql -e MYSQL_ROOT_PASSWORD=password \
       -p 127.0.0.1:13306:3306 -d mysql:5.5
   # Start interesting tests
   BUILDBOT_TEST_DB_URL=mysql+mysqldb://root:password@127.0.0.1:13306/mysql \
       trial buildbot.test
