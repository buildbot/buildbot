.. _WWW-Auth-GoogleAuth:

GoogleAuth
==========

.. py:class:: buildbot.www.oauth2.GoogleAuth(clientId, clientSecret)

    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application
    :param boolean ssl_verify: If False disables SSL certificate verification

    This class implements an authentication with Google_ single sign-on.
    You can look at the Google_ oauth2 documentation on how to register your Buildbot instance to the Google systems.
    The developer console will give you the two parameters you have to give to ``GoogleAuth``.

    Register your Buildbot instance with the ``BUILDBOT_URL/auth/login`` URL as the allowed redirect URI.

    Example:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GoogleAuth("clientid", "clientsecret"),
        }

    In order to use this module, you need to install the Python ``requests`` module:

    .. code-block:: bash

            pip install requests

.. _Google: https://developers.google.com/accounts/docs/OAuth2
