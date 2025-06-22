.. _WWW-Auth-UserPasswordAuth:

UserPasswordAuth
================

.. py:class:: buildbot.www.auth.UserPasswordAuth(users)

    :param users: list of ``("user","password")`` tuples, or a dictionary of ``{"user": "password", ..}``

    Simple username/password authentication using a list of user/password tuples provided in the configuration file.

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.UserPasswordAuth({"homer": "doh!"}),
        }