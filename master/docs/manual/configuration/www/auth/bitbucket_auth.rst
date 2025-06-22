.. _WWW-Auth-BitbucketAuth:

BitbucketAuth
=============

.. py:class:: buildbot.www.oauth2.BitbucketAuth(clientId, clientSecret)

    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application
    :param boolean ssl_verify: If False disables SSL certificate verification

    This class implements an authentication with Bitbucket_ single sign-on.
    It functions almost identically to the :py:class:`~buildbot.www.oauth2.GoogleAuth` class.

    Register your Buildbot instance with the ``BUILDBOT_URL/auth/login`` URL as the allowed redirect URI.

    Example:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.BitbucketAuth("clientid", "clientsecret"),
        }

    In order to use this module, you need to install the Python ``requests`` module:

    .. code-block:: bash

            pip install requests

.. _Bitbucket: https://confluence.atlassian.com/bitbucket/oauth-on-bitbucket-cloud-238027431.html
