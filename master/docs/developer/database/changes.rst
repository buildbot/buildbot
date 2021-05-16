Changes connector
~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.changes

.. index:: double: Changes; DB Connector Component

.. py:class:: ChangesConnectorComponent

    This class handles changes in the Buildbot database, including pulling
    information from the changes sub-tables.

    An instance of this class is available at ``master.db.changes``.

    .. index:: chdict, changeid

    Changes are indexed by *changeid*, and are represented by a *chdict*, which
    has the following keys:

    * ``changeid`` (the ID of this change)
    * ``parent_changeids`` (list of ID; change's parents)
    * ``author`` (unicode; the author of the change)
    * ``committer`` (unicode; the committer of the change)
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

        :returns: the last changeID that matches the branch, repository, project, or codebase

    .. py:method:: addChange(author=None, committer=None, files=None, comments=None, is_dir=0, links=None, revision=None, when_timestamp=None, branch=None, category=None, revlink='', properties={}, repository='', project='', uid=None)

        :param author: the author of this change
        :type author: unicode string
        :param committer: the committer of this change
        :type committer: unicode string
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
            ``'Change'``, although this may be relaxed in later versions
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

    .. py:method:: getChanges(resultSpec=None)

        :param resultSpec: result spec containing filters sorting and paging requests from data/REST API.
            If possible, the db layer can optimize the SQL query using this information.
        :returns: list of dictionaries via Deferred

        Get a list of the changes, represented as dictionaries, matching the given
        criteria. if ``resultSpec`` is not provided, changes are sorted, and paged
        using generic data query options.

    .. py:method:: getChangesCount()

        :returns: list of dictionaries via Deferred

        Get the number of changes that the query option would return if no paging option was set.


    .. py:method:: getLatestChangeid()

        :returns: changeid via Deferred

        Get the most-recently-assigned changeid, or ``None`` if there are no changes at all.


    .. py:method:: getChangesForBuild(buildid)

        :param buildid: ID of the build
        :returns: list of dictionaries via Deferred

        Get the "blame" list of changes for a build.

    .. py:method:: getBuildsForChange(changeid)

        :param changeid: ID of the change
        :returns: list of buildDict via Deferred

        Get builds related to a change.

    .. py:method:: getChangeFromSSid(sourcestampid)

        :param sourcestampid: ID of the sourcestampid
        :returns: chdict via Deferred

        Returns the change dictionary related to the sourcestamp ID.
