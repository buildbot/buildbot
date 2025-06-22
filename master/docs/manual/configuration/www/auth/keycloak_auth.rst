.. _WWW-Auth-KeyCloakAuth:

KeyCloakAuth
============

.. py:class:: buildbot.www.oauth2.KeyCloakAuth(instance_uri, realm, client_id, client_secret)

    :param str instance_uri: The URI of your KeyCloak instance (e.g. `keycloak.example.com`)
    :param str realm: The realm that buildbot should authenticate to (e.g. `master`)
    :param str client_id: The client ID of your buildbot application
    :param str client_secret: The client secret of your buildbot application
    :param boolean ssl_verify: If False disables SSL certificate verification

    This class implements an authentication with self-hosted KeyCloak single sign-on.

    As of KeyCloak 26, basic configuration is as follows:

    Add new client with "OpenID Connect" type:

     - Home URL: `https://buildbot.example.com`

     - Valid redirect URIs: `https://buildbot.example.com/*`

     - Valid post-logout redirect URIs: `https://buildbot.example.com/*`

     - Web origins: `+`

     - Authentication flow: Standard flow

    In addition to the above, you can configure additional information that KeyCloak will
    send to Buildbot as part of userinfo query. Go to the details of the created client,
    then to "Client scopes", then to "Dedicated scope and mappers for this client".
    Click "Add mapper", then "From predefined mappers". Select "email", "full name" and
    "groups" mappers

    Example:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.KeyCloakAuth("https://keycloak.example.com", "master", "clientid", "clientsecret"),
        }

    In order to use this module, you need to install the Python ``requests`` module:

    .. code-block:: bash

            pip install requests
