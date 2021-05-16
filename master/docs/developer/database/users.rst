Users connector
~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.users

.. index:: double: Users; DB Connector Component

.. py:class:: UsersConnectorComponent

    This class handles Buildbot's notion of users.  Buildbot tracks the usual
    information about users -- username and password, plus a display name.

    The more complicated task is to recognize each user across multiple
    interfaces with Buildbot.  For example, a user may be identified as
    'djmitche' in Subversion, 'dustin@v.igoro.us' in Git, and 'dustin' on IRC.
    To support this functionality, each user has a set of attributes, keyed by
    type.  The :py:meth:`findUserByAttr` method uses these attributes to match users,
    adding a new user if no matching user is found.

    Users are identified canonically by *uid*, and are represented by *usdicts* (user
    dictionaries) with the following keys:

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
        results are not full usdicts.

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
