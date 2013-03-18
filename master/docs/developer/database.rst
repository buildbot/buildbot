.. _developer-database:

Database
========

As of version 0.8.0, Buildbot has used a database as part of its storage
backend.  This section describes the database connector classes, which allow
other parts of Buildbot to access the database.  It also describes how to
modify the database schema and the connector classes themselves.

.. note::

    Buildbot is only half-migrated to a database backend.  Build and builder
    status information is still stored on disk in pickle files.  This is
    difficult to fix, although work is underway.

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
<http://code.google.com/p/sqlalchemy-migrate/>`_.  This package handles the
details of upgrading users between different schema versions.

The schema itself is considered an implementation detail, and may change
significantly from version to version.  Users should rely on the API (below),
rather than performing queries against the database itself.

API
---

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

    * ``brid``
    * ``buildsetid``
    * ``buildername``
    * ``priority``
    * ``claimed`` (boolean, true if the request is claimed)
    * ``claimed_at`` (datetime object, time this request was last claimed)
    * ``mine`` (boolean, true if the request is claimed by this master)
    * ``complete`` (boolean, true if the request is complete)
    * ``complete_at`` (datetime object, time this request was completed)

    .. py:method:: getBuildRequest(brid)

        :param brid: build request id to look up
        :returns: brdict or ``None``, via Deferred

        Get a single BuildRequest, in the format described above.  This method
        returns ``None`` if there is no such buildrequest.  Note that build
        requests are not cached, as the values in the database are not fixed.

    .. py:method:: getBuildRequests(buildername=None, complete=None, claimed=None, bsid=None, branch=None, repository=None))

        :param buildername: limit results to buildrequests for this builder
        :type buildername: string
        :param complete: if true, limit to completed buildrequests; if false,
            limit to incomplete buildrequests; if ``None``, do not limit based on
            completion.
        :param claimed: see below
        :param bsid: see below
        :param repository: the repository associated with the sourcestamps originating the requests
        :param branch: the branch associated with the sourcestamps originating the requests
        :returns: list of brdicts, via Deferred

        Get a list of build requests matching the given characteristics.

        Pass all parameters as keyword parameters to allow future expansion.

        The ``claimed`` parameter can be ``None`` (the default) to ignore the
        claimed status of requests; ``True`` to return only claimed builds,
        ``False`` to return only unclaimed builds, or ``"mine"`` to return only
        builds claimed by this master instance.  A request is considered
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

        As of 0.8.5, this method can no longer be used to re-claim build
        requests.  All given ID's must be unclaimed.  Use
        :py:meth:`reclaimBuildRequests` to reclaim.

        .. index:: single: MySQL; limitations
        .. index:: single: SQLite; limitations

        .. note::
            On database backends that do not enforce referential integrity
            (e.g., SQLite), this method will not prevent claims for nonexistent
            build requests.  On database backends that do not support
            transactions (MySQL), this method will not properly roll back any
            partial claims made before an :py:exc:`AlreadyClaimedError` is
            generated.

    .. py:method:: reclaimBuildRequests(brids)

        :param brids: ids of buildrequests to reclaim
        :type brids: list
        :returns: Deferred
        :raises: :py:exc:`AlreadyClaimedError`

        Re-claim the given build requests, updating the timestamp, but checking
        that the requests are owned by this master.  The resulting deferred will
        fire normally on success, or fail with :py:exc:`AlreadyClaimedError` if
        *any* of the build requests are already claimed by another master
        instance, or don't exist.  In this case, none of the reclaims will take
        effect.

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

    .. py:method:: unclaimExpiredRequests(old)

        :param old: number of seconds after which a claim is considered old
        :type old: int
        :returns: Deferred

        Find any incomplete claimed builds which are older than ``old``
        seconds, and clear their claim information.

        This is intended to catch builds that were claimed by a master which
        has since disappeared.  As a side effect, it will log a message if any
        requests are unclaimed.

builds
~~~~~~

.. py:module:: buildbot.db.builds

.. index:: double: Builds; DB Connector Component

.. py:class:: BuildsConnectorComponent

    This class handles a little bit of information about builds.

    .. note::
        The interface for this class will change - the builds table duplicates
        some information available in pickles, without including all such
        information.  Do not depend on this API.

    An instance of this class is available at ``master.db.builds``.

    .. index:: bdict, bid

    Builds are indexed by *bid* and their contents represented as *bdicts*
    (build dictionaries), with keys

    * ``bid`` (the build ID, globally unique)
    * ``number`` (the build number, unique only within this master and builder)
    * ``brid`` (the ID of the build request that caused this build)
    * ``start_time``
    * ``finish_time`` (datetime objects, or None).

    .. py:method:: getBuild(bid)

        :param bid: build id
        :type bid: integer
        :returns: Build dictionary as above or ``None``, via Deferred

        Get a single build, in the format described above.  Returns ``None`` if
        there is no such build.

    .. py:method:: getBuildsForRequest(brid)

        :param brids: list of build request ids
        :returns: List of build dictionaries as above, via Deferred

        Get a list of builds for the given build request.  The resulting build
        dictionaries are in exactly the same format as for :py:meth:`getBuild`.

    .. py:method:: addBuild(brid, number)

        :param brid: build request id
        :param number: build number
        :returns: build ID via Deferred

        Add a new build to the db, recorded as having started at the current
        time.

    .. py:method:: finishBuilds(bids)

        :param bids: build ids
        :type bids: list
        :returns: Deferred

        Mark the given builds as finished, with ``finish_time`` set to the
        current time.  This is done unconditionally, even if the builds are
        already finished.

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
    * ``sourcestampsetid`` (source stamp set for this buildset)
    * ``submitted_at`` (datetime object; time this buildset was created)
    * ``complete`` (boolean; true if all of the builds for this buildset are complete)
    * ``complete_at`` (datetime object; time this buildset was completed)
    * ``results`` (aggregate result of this buildset; see :ref:`Build-Result-Codes`)

    .. py:method:: addBuildset(sourcestampsetid, reason, properties, builderNames, external_idstring=None)

        :param sourcestampsetid: id of the SourceStampSet for this buildset
        :type sourcestampsetid: integer
        :param reason: reason for this buildset
        :type reason: short unicode string
        :param properties: properties for this buildset
        :type properties: dictionary, where values are tuples of (value, source)
        :param builderNames: builders specified by this buildset
        :type builderNames: list of strings
        :param external_idstring: external key to identify this buildset; defaults to None
        :type external_idstring: unicode string
        :returns: buildset ID and buildrequest IDs, via a Deferred

        Add a new Buildset to the database, along with BuildRequests for each
        named builder, returning the resulting bsid via a Deferred.  Arguments
        should be specified by keyword.

        The return value is a tuple ``(bsid, brids)`` where ``bsid`` is the
        inserted buildset ID and ``brids`` is a dictionary mapping buildernames
        to build request IDs.

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

    .. py:method:: getBuildsets(complete=None)

        :param complete: if true, return only complete buildsets; if false,
            return only incomplete buildsets; if ``None`` or omitted, return all
            buildsets
        :returns: list of bsdicts, via Deferred

        Get a list of bsdicts matching the given criteria.

    .. py:method:: getRecentBuildsets(count, branch=None, repository=None,
                           complete=None):

        :param count: maximum number of buildsets to retrieve.
        :type branch: integer
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

    .. py:method:: getBuildsetProperties(buildsetid)

        :param buildsetid: buildset ID
        :returns: dictionary mapping property name to ``value, source``, via
            Deferred

        Return the properties for a buildset, in the same format they were
        given to :py:meth:`addBuildset`.

        Note that this method does not distinguish a nonexistent buildset from
        a buildset with no properties, and returns ``{}`` in either case.

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

    .. py:method:: getLatestChangeid()

        :returns: changeid via Deferred

        Get the most-recently-assigned changeid, or ``None`` if there are no
        changes at all.

schedulers
~~~~~~~~~~

.. py:module:: buildbot.db.schedulers

.. index:: double: Schedulers; DB Connector Component

.. py:class:: SchedulersConnectorComponent

    This class manages the state of the Buildbot schedulers.  This state includes
    classifications of as-yet un-built changes.

    An instance of this class is available at ``master.db.changes``.

    .. index:: objectid

    Schedulers are identified by a their objectid - see
    :py:class:`StateConnectorComponent`.

    .. py:method:: classifyChanges(objectid, classifications)

        :param objectid: scheduler classifying the changes
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

    .. py:method: flushChangeClassifications(objectid, less_than=None)

        :param objectid: scheduler owning the flushed changes
        :param less_than: (optional) lowest changeid that should *not* be flushed
        :returns: Deferred

        Flush all scheduler_changes for the given scheduler, limiting to those
        with changeid less than ``less_than`` if the parameter is supplied.

    .. py:method:: getChangeClassifications(objectid[, branch])

        :param objectid: scheduler to look up changes for
        :type objectid: integer
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

sourcestamps
~~~~~~~~~~~~

.. py:module:: buildbot.db.sourcestamps

.. index:: double: SourceStamps; DB Connector Component

.. py:class:: SourceStampsConnectorComponent

    This class manages source stamps, as stored in the database. Source stamps
    are linked to changes. Source stamps with the same sourcestampsetid belong
    to the same sourcestampset. Buildsets link to one or more source stamps via
    a sourcestampset id.

    An instance of this class is available at ``master.db.sourcestamps``.

    .. index:: ssid, ssdict

    Source stamps are identified by a *ssid*, and represented internally as a *ssdict*, with keys

    * ``ssid``
    * ``sourcestampsetid`` (set to which the sourcestamp belongs)
    * ``branch`` (branch, or ``None`` for default branch)
    * ``revision`` (revision, or ``None`` to indicate the latest revision, in
      which case this is a relative source stamp)
    * ``patch_body`` (body of the patch, or ``None``)
    * ``patch_level`` (directory stripping level of the patch, or ``None``)
    * ``patch_subdir`` (subdirectory in which to apply the patch, or ``None``)
    * ``patch_author`` (author of the patch, or ``None``)
    * ``patch_comment`` (comment for the patch, or ``None``)
    * ``repository`` (repository containing the source; never ``None``)
    * ``project`` (project this source is for; never ``None``)
    * ``changeids`` (list of changes, by id, that generated this sourcestamp)

    .. note::
        Presently, no attempt is made to ensure uniqueness of source stamps, so
        multiple ssids may correspond to the same source stamp.  This may be fixed
        in a future version.

    .. py:method:: addSourceStamp(branch, revision, repository, project, patch_body=None, patch_level=0, patch_author="", patch_comment="", patch_subdir=None, changeids=[])

        :param branch:
        :type branch: unicode string
        :param revision:
        :type revision: unicode string
        :param repository:
        :type repository: unicode string
        :param project:
        :type project: string
        :param patch_body: (optional)
        :type patch_body: string
        :param patch_level: (optional)
        :type patch_level: int
        :param patch_author: (optional)
        :type patch_author: unicode string
        :param patch_comment: (optional)
        :type patch_comment: unicode string
        :param patch_subdir: (optional)
        :type patch_subdir: unicode string
        :param changeids:
        :type changeids: list of ints
        :returns: ssid, via Deferred

        Create a new SourceStamp instance with the given attributes, and return
        its ssid.  The arguments all have the same meaning as in an ssdict.
        Pass them as keyword arguments to allow for future expansion.

    .. py:method:: getSourceStamp(ssid)

        :param ssid: sourcestamp to get
        :param no_cache: bypass cache and always fetch from database
        :type no_cache: boolean
        :returns: ssdict, or ``None``, via Deferred

        Get an ssdict representing the given source stamp, or ``None`` if no
        such source stamp exists.

    .. py:method:: getSourceStamps(sourcestampsetid)

        :param sourcestampsetid: identification of the set, all returned sourcestamps belong to this set
        :type sourcestampsetid: integer
        :returns: sslist of ssdict

        Get a set of sourcestamps identified by a set id. The set is returned as
        a sslist that contains one or more sourcestamps (represented as ssdicts).
        The list is empty if the set does not exist or no sourcestamps belong to the set.

sourcestampset
~~~~~~~~~~~~~~

.. py:module:: buildbot.db.sourcestampsets

.. index:: double: SourceStampSets; DB Connector Component

.. py:class:: SourceStampSetsConnectorComponent

    This class is responsible for adding new sourcestampsets to the database.
    Build sets link to sourcestamp sets, via their (set) id's.

    An instance of this class is available at ``master.db.sourcestampsets``.

    Sourcestamp sets are identified by a sourcestampsetid.

    .. py:method:: addSourceStampSet()

        :returns: new sourcestampsetid as integer, via Deferred

        Add a new (empty) sourcestampset to the database. The unique identification
        of the set is returned as integer. The new id can be used to add
        new sourcestamps to the database and as reference in a buildset.

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
        :param default: (optional) value to return if C{name} is not present
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
        :param returns: Deferred
        :raises: TypeError if JSONification fails

        Set the state value for ``name`` for the object with id ``objectid``,
        overwriting any existing value.

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

    The source file, :bb:src:`master/buildbot/db/model.py`, contains comments
    describing each table; that information is not replicated in this
    documentation.

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
the database code.

.. _Modifying-the-Database-Schema:

Modifying the Database Schema
-----------------------------

Changes to the schema are accomplished through migration scripts, supported by
`SQLAlchemy-Migrate <http://code.google.com/p/sqlalchemy-migrate/>`_.  In fact,
even new databases are created with the migration scripts -- a new database is
a migrated version of an empty database.

The schema is tracked by a version number, stored in the ``migrate_version``
table.  This number is incremented for each change to the schema, and used to
determine whether the database must be upgraded.  The master will refuse to run
with an out-of-date database.

To make a change to the schema, first consider how to handle any existing data.
When adding new columns, this may not be necessary, but table refactorings can
be complex and require caution so as not to lose information.

Create a new script in :bb:src:`master/buildbot/db/migrate/versions`, following
the numbering scheme already present.  The script should have an ``update``
method, which takes an engine as a parameter, and upgrades the database, both
changing the schema and performing any required data migrations.  The engine
passed to this parameter is "enhanced" by SQLAlchemy-Migrate, with methods to
handle adding, altering, and dropping columns.  See the SQLAlchemy-Migrate
documentation for details.

Next, modify :bb:src:`master/buildbot/db/model.py` to represent the updated
schema.  Buildbot's automated tests perform a rudimentary comparison of an
upgraded database with the model, but it is important to check the details -
key length, nullability, and so on can sometimes be missed by the checks.  If
the schema and the upgrade scripts get out of sync, bizarre behavior can
result.

Also, adjust the fake database table definitions in
:bb:src:`master/buildbot/test/fake/fakedb.py` according to your changes.

Your upgrade script should have unit tests.  The classes in
:bb:src:`master/buildbot/test/util/migration.py` make this straightforward.
Unit test scripts should be named e.g.,
:file:`test_db_migrate_versions_015_remove_bad_master_objectid.py`.

The :file:`master/buildbot/test/integration/test_upgrade.py` also tests
upgrades, and will confirm that the resulting database matches the model.  If
you encounter implicit indexes on MySQL, that do not appear on SQLite or
Postgres, add them to ``implied_indexes`` in
:file:`master/buidlbot/db/model.py`.

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

MySQL only supports about 330-character indexes.  The actual index length is
1000 bytes, but MySQL uses 3-byte encoding for UTF8 strings.  This is a
longstanding bug in MySQL - see `"Specified key was too long; max key
length is 1000 bytes" with utf8 <http://bugs.mysql.com/bug.php?id=4541>`_.
While this makes sense for indexes used for record lookup, it limits the
ability to use unique indexes to prevent duplicate rows.

InnoDB has even more severe restrictions on key lengths, which is why the MySQL
implementation requires a MyISAM storage engine.

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
