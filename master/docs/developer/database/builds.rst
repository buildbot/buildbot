Builds connector
~~~~~~~~~~~~~~~~

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

        Returns the last successful build from the current build number with the same repository, branch, or codebase.

    .. py:method:: getBuilds(builderid=None, buildrequestid=None, complete=None, resultSpec=None)

        :param integer builderid: builder to get builds for
        :param integer buildrequestid: buildrequest to get builds for
        :param boolean complete: if not None, filters results based on completeness
        :param resultSpec: result spec containing filters sorting and paging requests from data/REST API.
            If possible, the db layer can optimize the SQL query using this information.
        :returns: list of build dictionaries as above, via Deferred

        Get a list of builds, in the format described above.
        Each of the parameters limits the resulting set of builds.

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

    .. py:method:: getBuildProperties(buildid, resultSpec=None)

        :param buildid: build ID
        :param resultSpec: resultSpec
        :returns: dictionary mapping property name to ``value, source``, via Deferred

        Return the properties for a build, in the same format they were given to :py:meth:`addBuild`.
        Optional filtering via resultSpec is available and optimized in the db layer.

        Note that this method does not distinguish a non-existent build from a build with no properties, and returns ``{}`` in either case.

    .. py:method:: setBuildProperty(buildid, name, value, source)

        :param integer buildid: build ID
        :param string name: Name of the property to set
        :param value: Value of the property
        :param string source: Source of the Property to set
        :returns: Deferred

        Set a build property.
        If no property with that name existed in that build, a new property will be created.
