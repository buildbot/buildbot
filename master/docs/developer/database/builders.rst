Builders connector
~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.builders

.. index:: double: Builders; DB Connector Component

.. py:class:: BuildersConnectorComponent

    This class handles the relationship between builder names and their IDs, as well as tracking which masters are configured for this builder.

    Builders are represented by a :class:`BuilderModel` dataclass with the following fields:

    * ``id`` -- the ID of this builder
    * ``name``  -- the builder name
    * ``description`` -- the builder's description (optional)
    * ``description_format`` -- the format of builder's description (optional)
    * ``description_html`` -- the builder description rendered as html (optional, depends on ``description_format``)
    * ``projectid`` -- the builder's project
    * ``tags`` -- the builder's tags
    * ``masterids`` -- the IDs of the masters where this builder is configured (sorted by id)

    .. py:method:: findBuilderId(name, autoCreate=True)

        :param name: name of this builder
        :type name: string
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
        :returns: :class:`BuilderModel` or None via Deferred

        Get the indicated builder.

    .. py:method:: getBuilders(masterid=None, projectid=None, workerid=None)

        :param integer masterid: ID of the master to which the results should be limited
        :param integer masterid: ID of the project to which the results should be limited
        :param integer workerid: ID of the configured worker to which the results should be limited
        :returns: list of :class:`BuilderModel` via Deferred

        Get all builders (in unspecified order).
        If ``masterid`` is specified, then only builders configured on that master are returned.
        If ``projectid`` is specified, then only builders for a particular project are returned.
        If ``workerid`` is specified, then only builders for a particular configured worker are returned.
