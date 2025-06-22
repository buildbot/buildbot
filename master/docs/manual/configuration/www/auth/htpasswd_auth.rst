.. _WWW-Auth-HTPasswdAuth:

HTPasswdAuth
============

.. py:class:: buildbot.www.auth.HTPasswdAuth(passwdFile)

    :param passwdFile: An :file:`.htpasswd` file to read

    This class implements simple username/password authentication against a standard :file:`.htpasswd` file.

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.HTPasswdAuth("my_htpasswd"),
        }
