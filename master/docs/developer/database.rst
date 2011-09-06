The Buildbot Database
=====================

As of version 0.8.0, Buildbot has used a database for its storage backend.
This section describes the database connector classes, which allow other parts
of Buildbot to access the database.  It also describes how to modify the
database schema and the connector classes themsleves.

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

The database schema is maintained with `SQLAlchemy-Migrate
<http://code.google.com/p/sqlalchemy-migrate/>`_.  This package handles the
details of upgrading users between different schema versions.

While the most up-to-date schema is available in
:file:`master/buildbot/db/model.py`, this file is not used for new
installations of Buildbot.  Instead, Buildbot begins with an empty database and
applies all of the upgrade scripts.  This ensures that the upgrade scripts
define the schema, so that existing and new users are always on an equal
footing.

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

    .. py:method:: BuildRequestsConnectorComponent.getBuildRequest(brid)

        :param brid: build request id to look up
        :returns: brdict or ``None``, via Deferred

        Get a single BuildRequest, in the format described above.  This method
        returns ``None`` if there is no such buildrequest.  Note that build
        requests are not cached, as the values in the database are not fixed.

    .. py:method:: getBuildRequests(buildername=None, complete=None, claimed=None, bsid=None)

        :param buildername: limit results to buildrequests for this builder
        :type buildername: string
        :param complete: if true, limit to completed buildrequests; if false,
            limit to incomplete buildrequests; if ``None``, do not limit based on
            completion.
        :param claimed: see below
        :param bsid: see below
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

    .. py:method:: claimBuildRequests(brids)

        :param brids: ids of buildrequests to claim
        :type brids: list
        :returns: Deferred
        :raises: :py:exc:`AlreadyClaimedError`

        Try to "claim" the indicated build requests for this buildmaster
        instance.  The resulting deferred will fire normally on success, or
        fail with :py:exc:`AlreadyClaimedError` if *any* of the build
        requests are already claimed by another master instance.  In this case,
        none of the claims will take effect.

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
            partial claims made before an :py:exc:`AlreadyClaimedError` was
            generated.

    .. py:method:: reclaimBuildRequests(brids)

        :param brids: ids of buildrequests to reclaim
        :type brids: list
        :returns: Deferred
        :raises: :py:exc:`AlreadyClaimedError`

        Re-claim the given build requests, updating the timestamp, but checking
        that the requsts are owned by this master.  The resulting deferred will
        fire normally on success, or fail with :py:exc:`AleadyClaimedError` if
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

    .. py:method:: completeBuildRequests(brids, results)

        :param brids: build request IDs to complete
        :type brids: integer
        :param results: integer result code
        :type results: integer
        :returns: Deferred
        :raises: :py:exc:`NotClaimedError`

        Complete a set of build requests, all of which are owned by this master
        instance.  This will fail with :py:exc:`NotClaimedError` if the build
        request is already completed or does not exist.

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
    * ``sourcestampid`` (source stamp for this buildset)
    * ``submitted_at`` (datetime object; time this buildset was created)
    * ``complete`` (boolean; true if all of the builds for this buildset are complete)
    * ``complete_at`` (datetime object; time this buildset was completed)
    * ``results`` (aggregate result of this buildset; see :ref:`Build-Result-Codes`)

    .. py:method:: addBuildset(ssid, reason, properties, builderNames, external_idstring=None)

        :param ssid: id of the SourceStamp for this buildset
        :type ssid: integer
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

    .. py:method:: completeBuildset(bsid, results)

        :param bsid: buildset ID to complete
        :type bsid: integer
        :param results: integer result code
        :type results: integer
        :returns: Deferred
        :raises: :py:exc:`KeyError` if the buildset does not exist or is already complete

        Complete a buildset, marking it with the given ``results`` and setting
        its ``completed_at`` to the current time.

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

        Get a list of the ``count`` most recent changes, represented as
        dictionaies; returns fewer if that many do not exist.

        .. note::
            For this function, "recent" is determined by the order of the
            changeids, not by ``when_timestamp``.  This is most apparent in
            DVCS's, where the timestamp of a change may be significantly
            earlier than the time at which it is merged into a repository
            monitored by Buildbot.

        @param count: maximum number of instances to return

        @returns: list of dictionaries via Deferred, ordered by changeid

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

    .. index:: schedulerid

    Schedulers are identified by a *schedulerid*, which can be determined from
    the scheduler name and class by :py:meth:`getSchedulerId`.

    .. py:method:: classifyChanges(schedulerid, classifications)

        :param schedulerid: scheduler classifying the changes
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

    .. py:method: flushChangeClassifications(schedulerid, less_than=None)

        :param schedulerid: scheduler owning the flushed changes
        :param less_than: (optional) lowest changeid that should *not* be flushed
        :returns: Deferred

        Flush all scheduler_changes for the given scheduler, limiting to those
        with changeid less than ``less_than`` if the parameter is supplied.

    .. py:method:: getChangeClassifications(schedulerid[, branch])

        :param schedulerid: scheduler to look up changes for
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

    .. py:method:: getSchedulerId(sched_name, sched_class)

        :param sched_name: the scheduler's configured name
        :param sched_class: the class name of this scheduler
        :returns: schedulerid, via a Deferred

        Get the schedulerid for the given scheduler, creating a new id if no
        matching record is found.

        Note that this makes no attempt to "claim" the schedulerid: schedulers
        with the same name and class, but running in different masters, will be
        assigned the same schedulerid - with disastrous results.

sourcestamps
~~~~~~~~~~~~

.. py:module:: buildbot.db.sourcestamps

.. index:: double: SourceStamps; DB Connector Component

.. py:class:: SourceStampsConnectorComponent

    This class manages source stamps, as stored in the database.  Source stamps
    are linked to changes, and build sets link to source stamps, via their
    id's.

    An instance of this class is available at ``master.db.sourcestamps``.

    .. index:: ssid, ssdict

    Source stamps are identified by a *ssid*, and represented internally as an *ssdict*, with keys

    * ``ssid``
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
    type.  The :py:meth:`addUser` method uses these attributes to match users,
    adding a new user if no matching user is found.

    Users are identified canonically by *uid*, and are represented by *usdicts* (user
    dictionaries) with keys

    * ``uid``
    * ``identifier`` (display name for the user)
    * ``bb_username`` (buildbot login username)
    * ``bb_password`` (hashed login password)

    All attributes are also included in the dictionary, keyed by type.  Types
    colliding with the keys above are ignored.

    .. py:method:: addUser(identifier, attr_type, attr_data)

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

.. todo::

    connector
    enginestrategy
    pool
    exceptions
    model
    Caching
    Schema Changes
    Compatibility Notes

Outdated Info
-------------

Ignore this.

Database Schema
~~~~~~~~~~~~~~~

The SQL for the database schema is available in
:file:`master/buildbot/db/model.py`.  However, note that this file is not used
for new installations or upgrades of the Buildbot database.

Instead, the :class:`buildbot.db.schema.DBSchemaManager` handles this task.  The
operation of this class centers around a linear sequence of database versions.
Versions start at 0, which is the old pickle-file format.  The manager has
methods to query the version of the database, and the current version from the
source code.  It also has an :meth:`upgrade` method which will upgrade the
database to the latest version.  This operation is currently irreversible.

There is no operation to "install" the latest schema.  Instead, a fresh install
of buildbot begins with an (empty) version-0 database, and upgrades to the
current version.  This trades a bit of efficiency at install time for
assurances that the upgrade code is well-tested.

Changing the Schema
~~~~~~~~~~~~~~~~~~~

To make a change to the database schema, follow these steps:

 1. Increment ``CURRENT_VERSION`` in :file:`buildbot/db/schema/manager.py` by
     one.  This is your new version number.

 2. Create :file:`buildbot/db/schema/v{N}.py`, where *N* is your version number, by
    copying the previous script and stripping it down.  This script should define a
    subclass of :class:`buildbot.db.schema.base.Updater` named ``Updater``. 
    
    The class must define the method :meth:`upgrade`, which takes no arguments.  It
    should upgrade the database from the previous version to your version,
    including incrementing the number in the ``VERSION`` table, probably with an
    ``UPDATE`` query.
    
    Consult the API documentation for the base class for information on the
    attributes that are available.

 3. Edit :file:`buildbot/test/unit/test_db_schema_master.py`.  If your upgrade
    involves moving data from the basedir into the database proper, then edit
    :meth:`fill_basedir` to add some test data.
    
    Add code to :meth:`assertDatabaseOKEmpty` to check that your upgrade works on an
    empty database.
    
    Add code to :meth:`assertDatabaseOKFull` to check that your upgrade works on a
    database with pre-existing data.  Do this even if your changes do not move any
    data from the basedir.
    
    Run the tests to find the bugs you introduced in step 2.

 4. Increment the version number in the ``test_get_current_version`` test in the)
    same file.  Only do this after you've finished the previous step - a failure of
    this test is a good reminder that testing isn't done yet.


 5. Updated the version number in :file:`buildbot/db/schema/tables.sql`, too.

 6. Finally, make the corresponding changes to :file:`buildbot/db/schema/tables.sql`.


