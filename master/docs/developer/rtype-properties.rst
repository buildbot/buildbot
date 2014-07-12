Properties
==========

.. bb:rtype:: properties

    user-specified properties for this change, represented as an object mapping keys to tuple (value, source)

    Properties are present in several data resources, but have a separate endpoints, because they can represent a large dataset. They will be loaded only on demand by the UI.

    .. bb:rpath:: /buildsets/:buildsetid/properties

        This path lists properties for a given buildset.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

