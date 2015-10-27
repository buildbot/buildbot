Properties
==========

.. bb:rtype:: properties

    user-specified properties for this change, represented as an object mapping keys to tuple (value, source)

    Properties are present in several data resources, but have a separate endpoints, because they can represent a large dataset. They will be loaded only on demand by the UI.

    .. bb:rpath:: /buildsets/:buildsetid/properties

        This path lists properties for a given buildset.

    .. bb:rpath:: /builds/:buildid/properties

        This path lists properties for a given build.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.properties.Properties

    .. py:method:: setBuildProperty(buildid, name, value, source)

        :param integer buildid: build ID
        :param unicode name: Name of the property to set
        :param value: Value of the property
        :type value: Any JSON-able type is accepted (lists, dicts, strings and numbers)
        :param unicode source: Source of the property to set

        Set a build property.
        If no property with that name exists in that build, a new property will be created.

    .. py:method:: setBuildProperties(buildid, props)

        :param integer buildid: build ID
        :param IProperties props: Name of the property to set

        Synchronise build properties with the db.
        This sends only one event in the end of the sync, and only if properties changed.
        The event contains only the updated properties, for network efficiency reasons.
