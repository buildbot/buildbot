Build data connector
~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.build_data

.. py:class:: BuildDataConnectorComponent

    This class handles build data.
    Build data is potentially large transient text data attached to the build that the steps can use for their operations.
    One of the use cases is to carry large amount of data from one step to another where storing that data on the worker is not feasible.
    This effectively forms a key-value store for each build.
    It is valid only until the build finishes and all reporters are done reporting the build result.
    After that the data may be removed from the database.

    An instance of this class is available at ``master.db.build_data``.

    Builds are indexed by *build_dataid* and their contents represented as *build_datadicts* (build data dictionaries), with the following keys:

    * ``id`` (the build data ID, globally unique)
    * ``buildid`` (the ID of the build that the data is attached to)
    * ``name`` (the name of the data)
    * ``value`` (the value of the data. It must be an instance of ``bytes``)
    * ``source`` (an string identifying the source of this value)

    .. py:method:: setBuildData(buildid, name, value, source)

        :param integer buildid: build id to attach data to
        :param unicode name: the name of the data
        :param bytestr value: the value of the data as ``bytes``.
        :parma unicode source: the source of the data
        :returns: Deferred

        Adds or replaces build data attached to the build.

    .. py:method:: getBuildData(buildid, name)

        :param integer buildid: build id retrieve data for
        :param unicode name: the name of the data
        :returns: Build data dictionary as above or ``None``, via Deferred

        Get a single build data, in the format described above, specified by build and by name.
        Returns ``None`` if build has no data with such name.

    .. py:method:: getBuildDataNoValue(buildid, name)

        :param integer buildid: build id retrieve data for
        :param unicode name: the name of the data
        :returns: Build data dictionary as above or ``None``, via Deferred

        Get a single build data, in the format described above, specified by build and by name.
        The ``value`` field is omitted.
        Returns ``None`` if build has no data with such name.

    .. py:method:: getAllBuildDataNoValues(buildid, name=None)

        :param integer buildid: build id retrieve data for
        :param unicode name: the name of the data
        :returns: a list of build data dictionaries

        Returns all data for a specific build.
        The values are not loaded.
        The returned values can be filtered by name

    .. py:method:: deleteOldBuildData(older_than_timestamp)

        :param integer older_than_timestamp: the build data whose build's ``complete_at`` is older than ``older_than_timestamp`` will be deleted.
        :returns: Deferred

        Delete old build data (helper for the ``build_data_horizon`` policy).
        Old logs have their build data deleted from the database as they are only useful while build is running and shortly afterwards.

