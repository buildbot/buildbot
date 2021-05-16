State connector
~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.state

.. index:: double: State; DB Connector Component

.. py:class:: StateConnectorComponent

    This class handles maintaining arbitrary key-value state for Buildbot
    objects.  Each object can store arbitrary key-value pairs, where the values
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

        Get the object ID for this combination of name and class.
        This will add a row to the 'objects' table if none exists already.

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

        Atomically creates the state value for ``name`` for the object with id ``objectid``.
        If there is an existing value, returns that instead.
        This implementation ensures the state is created only once for the whole cluster.

    Those 3 methods have their threaded equivalent, ``thdGetObjectId``, ``thdGetState``, ``thdSetState`` that is intended to run in synchronous code, (e.g master.cfg environment).
