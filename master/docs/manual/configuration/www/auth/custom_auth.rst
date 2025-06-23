.. _WWW-Auth-CustomAuth:

CustomAuth
==========

.. py:class:: buildbot.www.auth.CustomAuth()

    This authentication class means to be overridden with a custom ``check_credentials`` method that gets username and password
    as arguments and check if the user can login. You may use it e.g. to check the credentials against an external database or file.

    .. code-block:: python

        from buildbot.plugins import util

        class MyAuth(util.CustomAuth):
            def check_credentials(self, user, password):
                if user == 'snow' and password == 'white':
                    return True
                else:
                    return False

        from buildbot.plugins import util
        c['www']['auth'] = MyAuth()