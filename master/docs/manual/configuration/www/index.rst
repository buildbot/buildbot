.. bb:cfg:: www

Web server configuration
========================

.. toctree::
    :hidden:
    :maxdepth: 2

    server
    ui/badges
    ui/console_view
    ui/grid_view
    ui/waterfall_view
    auth/bitbucket_auth
    auth/custom_auth
    auth/github_auth
    auth/gitlab_auth
    auth/google_auth
    auth/htpasswd_auth
    auth/keycloak_auth
    auth/remote_user_auth
    auth/user_password_auth


This section lists options to configure the web server.

* :ref:`Config-WWW-Server` - describes the options that adjust how complete web server works.

.. _UI-Plugins:

UI plugins
----------

Buildbot supports additional optional plugins that add additional UI functionality to Buildbot
web interface. The following is a list of plugins that are maintained as part of Buildbot project.

* :ref:`WaterfallView`
* :ref:`ConsoleView`
* :ref:`GridView`
* :ref:`Badges`

.. _Web-Authentication:

Authentication plugins
~~~~~~~~~~~~~~~~~~~~~~

By default, Buildbot does not require people to authenticate in order to access control features in the web UI.
To secure Buildbot, you will need to configure an authentication plugin.

.. note::

   To secure the Buildbot web interface, authorization rules must be provided via the 'authz' configuration.
   If you simply wish to lock down a Buildbot instance so that only read only access is permitted, you can
   restrict access to control endpoints to an unpopulated 'admin' role. For example:

   .. code-block:: python

      c['www']['authz'] = util.Authz(allowRules=[util.AnyControlEndpointMatcher(role="admins")],
                                     roleMatchers=[])

.. note::

   As of Buildbot 0.9.4, user session is managed via a JWT_ token, using HS256_ algorithm.
   The session secret is stored in the database in the ``object_state`` table with ``name`` column being ``session_secret``.
   Please make sure appropriate access restriction is made to this database table.

.. _JWT: https://en.wikipedia.org/wiki/JSON_Web_Token
.. _HS256: https://pyjwt.readthedocs.io/en/latest/algorithms.html

Authentication plugins are implemented as classes, and passed as the ``auth`` parameter to :bb:cfg:`www`.

The available classes are described here:

* NoAuth

    .. py:class:: buildbot.www.auth.NoAuth()

        This class is the default authentication plugin, which disables authentication.

* :ref:`WWW-Auth-UserPasswordAuth`
* :ref:`WWW-Auth-CustomAuth`
* :ref:`WWW-Auth-HTPasswdAuth`
* :ref:`WWW-Auth-BitbucketAuth`
* :ref:`WWW-Auth-GoogleAuth`
* :ref:`WWW-Auth-GitHubAuth`
* :ref:`WWW-Auth-GitLabAuth`
* :ref:`WWW-Auth-KeyCloakAuth`
* :ref:`WWW-Auth-RemoteUserAuth`

.. _User-Information:

User Information
~~~~~~~~~~~~~~~~

For authentication mechanisms which cannot provide complete information about a user, Buildbot needs another way to get user data.
This is useful both for authentication (to fetch more data about the logged-in user) and for avatars (to fetch data about other users).

This extra information is provided, appropriately enough, by user info providers.
These can be passed to :py:class:`~buildbot.www.auth.RemoteUserAuth` and as an element of ``avatar_methods``.

This can also be passed to oauth2 authentication plugins.
In this case the username provided by oauth2 will be used, and all other information will be taken from ldap (Full Name, email, and groups):

Currently only one provider is available:

.. py:class:: buildbot.ldapuserinfo.LdapUserInfo(uri, bindUser, bindPw, accountBase, accountPattern, groupBase=None, groupMemberPattern=None, groupName=None, accountFullName, accountEmail, avatarPattern=None, avatarData=None, accountExtraFields=None, tls=None)

        :param uri: uri of the ldap server
        :param bindUser: username of the ldap account that is used to get the infos for other users (usually a "faceless" account)
        :param bindPw: password of the ``bindUser``
        :param accountBase: the base dn (distinguished name)of the user database
        :param accountPattern: the pattern for searching in the account database.
                               This must contain the ``%(username)s`` string, which is replaced by the searched username
        :param accountFullName: the name of the field in account ldap database where the full user name is to be found.
        :param accountEmail: the name of the field in account ldap database where the user email is to be found.
        :param groupBase: the base dn of the groups database
        :param groupMemberPattern: the pattern for searching in the group database.
                                   This must contain the ``%(dn)s`` string, which is replaced by the searched username's dn
        :param groupName: the name of the field in groups ldap database where the group name is to be found.
        :param avatarPattern: the pattern for searching avatars from emails in the account database.
                              This must contain the ``%(email)s`` string, which is replaced by the searched email
        :param avatarData: the name of the field in groups ldap database where the avatar picture is to be found.
                           This field is supposed to contain the raw picture, format is automatically detected from jpeg, png or git.
        :param accountExtraFields: extra fields to extracts for use with the authorization policies
        :param tls: an instance of ``ldap.Tls`` that specifies TLS settings.

        If one of the three optional groups parameters is supplied, then all of them become mandatory. If none is supplied, the retrieved user info has an empty list of groups.

Example:

.. code-block:: python

            from buildbot.plugins import util

            # this configuration works for MS Active Directory ldap implementation
            # we use it for user info, and avatars
            userInfoProvider = util.LdapUserInfo(
                uri='ldap://ldap.mycompany.com:3268',
                bindUser='ldap_user',
                bindPw='p4$$wd',
                accountBase='dc=corp,dc=mycompany,dc=com',
                groupBase='dc=corp,dc=mycompany,dc=com',
                accountPattern='(&(objectClass=person)(sAMAccountName=%(username)s))',
                accountFullName='displayName',
                accountEmail='mail',
                groupMemberPattern='(&(objectClass=group)(member=%(dn)s))',
                groupName='cn',
                avatarPattern='(&(objectClass=person)(mail=%(email)s))',
                avatarData='thumbnailPhoto',
            )
            c['www'] = {
                "port": PORT,
                "allowed_origins": ["*"],
                "url": c['buildbotURL'],
                "auth": util.RemoteUserAuth(userInfoProvider=userInfoProvider),
                "avatar_methods": [
                    userInfoProvider,
                    util.AvatarGravatar()
                ]
            }

.. note::

            In order to use this module, you need to install the ``ldap3`` module:

            .. code-block:: bash

                pip install ldap3

In the case of oauth2 authentications, you have to pass the userInfoProvider as keyword argument:

.. code-block:: python

                from buildbot.plugins import util
                userInfoProvider = util.LdapUserInfo(...)
                c['www'] = {
                    # ...
                    'auth': util.GoogleAuth("clientid", "clientsecret", userInfoProvider=userInfoProvider),
                }



.. _Reverse_Proxy_Config:

Reverse Proxy Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is usually better to put Buildbot behind a reverse proxy in production.

* Provides automatic gzip compression
* Provides SSL support with a widely used implementation
* Provides support for http/2 or spdy for fast parallel REST api access from the browser

Reverse proxy however might be problematic for websocket, you have to configure it specifically to pass web socket requests.
Here is an nginx configuration that is known to work (nginx 1.6.2):

.. code-block:: none


    server {
            # Enable SSL and http2
            listen 443 ssl http2 default_server;

            server_name yourdomain.com;

            root html;
            index index.html index.htm;

            ssl on;
            ssl_certificate /etc/nginx/ssl/server.cer;
            ssl_certificate_key /etc/nginx/ssl/server.key;

            # put a one day session timeout for websockets to stay longer
            ssl_session_cache      shared:SSL:10m;
            ssl_session_timeout  1440m;

            # please consult latest nginx documentation for current secure encryption settings
            ssl_protocols ..
            ssl_ciphers ..
            ssl_prefer_server_ciphers   on;
            #

            # force https
            add_header Strict-Transport-Security "max-age=31536000; includeSubdomains;";
            spdy_headers_comp 5;

            proxy_set_header HOST $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto  $scheme;
            proxy_set_header X-Forwarded-Server  $host;
            proxy_set_header X-Forwarded-Host  $host;

            # you could use / if you use domain based proxy instead of path based proxy
            location /buildbot/ {
                proxy_pass http://127.0.0.1:5000/;
            }
            location /buildbot/sse/ {
                # proxy buffering will prevent sse to work
                proxy_buffering off;
                proxy_pass http://127.0.0.1:5000/sse/;
            }
            # required for websocket
            location /buildbot/ws {
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
                proxy_pass http://127.0.0.1:5000/ws;
                # raise the proxy timeout for the websocket
                proxy_read_timeout 6000s;
            }
    }

To run with Apache2, you'll need `mod_proxy_wstunnel <https://httpd.apache.org/docs/2.4/mod/mod_proxy_wstunnel.html>`_ in addition to `mod_proxy_http <https://httpd.apache.org/docs/2.4/mod/mod_proxy_http.html>`_. Serving HTTPS (`mod_ssl <https://httpd.apache.org/docs/2.4/mod/mod_ssl.html>`_) is advised to prevent issues with enterprise proxies (see :ref:`SSE`), even if you don't need the encryption itself.

Here is a configuration that is known to work (Apache 2.4.10 / Debian 8, Apache 2.4.25 / Debian 9, Apache 2.4.6 / CentOS 7), directly at the top of the domain.

If you want to add access control directives, just put them in a
``<Location />``.

.. code-block:: none


    <VirtualHost *:443>
        ServerName buildbot.example
        ServerAdmin webmaster@buildbot.example

        # replace with actual port of your Buildbot master
        ProxyPass /ws ws://127.0.0.1:8020/ws
        ProxyPassReverse /ws ws://127.0.0.1:8020/ws
        ProxyPass / http://127.0.0.1:8020/
        ProxyPassReverse / http://127.0.0.1:8020/

        SetEnvIf X-Url-Scheme https HTTPS=1
        ProxyPreserveHost On

        SSLEngine on
        SSLCertificateFile /path/to/cert.pem
        SSLCertificateKeyFile /path/to/cert.key

        # check Apache2 documentation for current safe SSL settings
        # This is actually the Debian 8 default at the time of this writing:
        SSLProtocol all -SSLv3

    </VirtualHost>


.. _Web-Authorization:

Authorization rules
~~~~~~~~~~~~~~~~~~~

The authorization framework in Buildbot is very generic and flexible.
The drawback is that it is not very obvious for newcomers.
The 'simple' example will however allow you to easily start by implementing an admins-have-all-rights setup.

Please carefully read the following documentation to understand how to setup authorization in Buildbot.

Authorization framework is tightly coupled to the REST API.
Authorization framework only works for HTTP, not for other means of interaction like IRC or try scheduler.
It allows or denies access to the REST APIs according to rules.

.. image:: ../../../_images/auth_rules.*
   :alt: Auth diagram

- Roles is a label that you give to a user.

  It is similar but different to the usual notion of group:

  - A user can have several roles, and a role can be given to several users.
  - Role is an application specific notion, while group is more organization specific notion.
  - Groups are given by the auth plugin, e.g ``ldap``, ``github``, and are not always in the precise control of the buildbot admins.
  - Roles can be dynamically assigned, according to the context.
    For example, there is the ``owner`` role, which can be given to a user for a build that he is at the origin, so that he can stop or rebuild only builds of his own.

- Endpoint matchers associate role requirements to REST API endpoints.
  The default policy is allow in case no matcher matches (see below why).

- Role matchers associate authenticated users to roles.

Restricting Read Access
+++++++++++++++++++++++

Please note that you can use this framework to deny read access to the REST API, but there is no access control in websocket or SSE APIs.
Practically this means user will still see live updates from running builds in the UI, as those will come from websocket.

The only resources that are only available for read in REST API are the log data (a.k.a `logchunks`).

From a strict security point of view you cannot really use Buildbot Authz framework to securely deny read access to your bot.
The access control is rather designed to restrict control APIs which are only accessible through REST API.
In order to reduce attack surface, we recommend to place Buildbot behind an access controlled reverse proxy like OAuth2Proxy_.

.. _OAuth2Proxy: https://github.com/oauth2-proxy/oauth2-proxy

Authz Configuration
+++++++++++++++++++

.. py:class:: buildbot.www.authz.Authz(allowRules=[], roleMatcher=[], stringsMatcher=util.fnmatchStrMatcher)

    :param allowRules: List of :py:class:`EndpointMatcherBase` processed in order for each endpoint grant request.
    :param roleMatcher: List of RoleMatchers
    :param stringsMatcher: Selects algorithm used to make strings comparison (used to compare roles and builder names).
       Can be :py:class:`util.fnmatchStrMatcher` or :py:class:`util.reStrMatcher` from ``from buildbot.plugins import util``

    :py:class:`Authz` needs to be configured in ``c['www']['authz']``

Endpoint matchers
+++++++++++++++++

Endpoint matchers are responsible for creating rules to match REST endpoints, and requiring roles for them.
Endpoint matchers are processed in the order they are configured.
The first rule matching an endpoint will prevent further rules from being checked.
To continue checking other rules when the result is `deny`, set `defaultDeny=False`.
If no endpoint matcher matches, then access is granted.

One can implement the default deny policy by putting an :py:class:`AnyEndpointMatcher` with nonexistent role in the end of the list.
Please note that this will deny all REST apis, and most of the UI do not implement proper access denied message in case of such error.

The following sequence is implemented by each EndpointMatcher class:

- Check whether the requested endpoint is supported by this matcher
- Get necessary info from data API and decide whether it matches
- Look if the user has the required role

Several endpoints matchers are currently implemented.
If you need a very complex setup, you may need to implement your own endpoint matchers.
In this case, you can look at the source code for detailed examples on how to write endpoint matchers.

.. py:class:: buildbot.www.authz.endpointmatchers.EndpointMatcherBase(role, defaultDeny=True)

    :param role: The role which grants access to this endpoint.
        List of roles is not supported, but a ``fnmatch`` expression can be provided to match several roles.

    :param defaultDeny: The role matcher algorithm will stop if this value is true and the endpoint matched.

    This is the base endpoint matcher.
    Its arguments are inherited by all the other endpoint matchers.

.. py:class:: buildbot.www.authz.endpointmatchers.AnyEndpointMatcher(role)

    :param role: The role which grants access to any endpoint.

    AnyEndpointMatcher grants all rights to people with given role (usually "admins").

.. py:class:: buildbot.www.authz.endpointmatchers.AnyControlEndpointMatcher(role)

    :param role: The role which grants access to any control endpoint.

    AnyControlEndpointMatcher grants control rights to people with given role (usually "admins").
    This endpoint matcher matches current and future control endpoints.
    You need to add this in the end of your configuration to make sure it is future proof.

.. py:class:: buildbot.www.authz.endpointmatchers.ForceBuildEndpointMatcher(builder, role)

    :param builder: Name of the builder.
    :param role: The role needed to get access to such endpoints.

    ForceBuildEndpointMatcher grants right to force builds.

.. py:class:: buildbot.www.authz.endpointmatchers.StopBuildEndpointMatcher(builder, role)

    :param builder: Name of the builder.
    :param role: The role needed to get access to such endpoints.

    StopBuildEndpointMatcher grants rights to stop builds.

.. py:class:: buildbot.www.authz.endpointmatchers.RebuildBuildEndpointMatcher(builder, role)

    :param builder: Name of the builder.
    :param role: The role needed to get access to such endpoints.

    RebuildBuildEndpointMatcher grants rights to rebuild builds.

.. py:class:: buildbot.www.authz.endpointmatchers.EnableSchedulerEndpointMatcher(builder, role)

    :param builder: Name of the builder.
    :param role: The role needed to get access to such endpoints.

    EnableSchedulerEndpointMatcher grants rights to enable and disable schedulers via the UI.

Role matchers
+++++++++++++
Role matchers are responsible for creating rules to match people and grant them roles.
You can grant roles from groups information provided by the Auth plugins, or if you prefer directly to people's email.


.. py:class:: buildbot.www.authz.roles.RolesFromGroups(groupPrefix)

    :param groupPrefix: Prefix to remove from each group

    RolesFromGroups grants roles from the groups of the user.
    If a user has group ``buildbot-admin``, and groupPrefix is ``buildbot-``, then user will be granted the role 'admin'

    ex:

    .. code-block:: python

        roleMatchers=[
          util.RolesFromGroups(groupPrefix="buildbot-")
        ]

.. py:class:: buildbot.www.authz.roles.RolesFromEmails(roledict)

    :param roledict: Dictionary with key=role, and value=list of email strings

    RolesFromEmails grants roles to users according to the hardcoded emails.

    ex:

    .. code-block:: python

        roleMatchers=[
          util.RolesFromEmails(admins=["my@email.com"])
        ]

.. py:class:: buildbot.www.authz.roles.RolesFromDomain(roledict)

    :param roledict: Dictionary with key=role, and value=list of domain strings

    RolesFromDomain grants roles to users according to their email domains.
    If a user tried to login with email ``foo@gmail.com``, then the user will be granted the role 'admins'.

    ex:

    .. code-block:: python

        roleMatchers=[
          util.RolesFromDomain(admins=["gmail.com"])
        ]

.. py:class:: buildbot.www.authz.roles.RolesFromOwner(roledict)

    :param roledict: Dictionary with key=role, and value=list of email strings

    RolesFromOwner grants a given role when property owner matches the email of the user

    ex:

    .. code-block:: python

        roleMatchers=[
            RolesFromOwner(role="owner")
        ]

.. py:class:: buildbot.www.authz.roles.RolesFromUsername(roles, usernames)

    :param roles: Roles to assign when the username matches.
    :param usernames: List of usernames that have the roles.

    RolesFromUsername grants the given roles when the ``username`` property is within the list of usernames.

    ex:

    .. code-block:: python

        roleMatchers=[
            RolesFromUsername(roles=["admins"], usernames=["root"]),
            RolesFromUsername(roles=["developers", "integrators"], usernames=["Alice", "Bob"])
        ]


Example Configs
+++++++++++++++

Simple config which allows admin people to control everything, but allow anonymous to look at build results:

.. code-block:: python

    from buildbot.plugins import *
    authz = util.Authz(
      allowRules=[
        util.AnyControlEndpointMatcher(role="admins"),
      ],
      roleMatchers=[
        util.RolesFromEmails(admins=["my@email.com"])
      ]
    )
    auth=util.UserPasswordAuth({'my@email.com': 'mypass'})
    c['www']['auth'] = auth
    c['www']['authz'] = authz

More complex config with separation per branch:

.. code-block:: python

    from buildbot.plugins import *

    authz = util.Authz(
        stringsMatcher=util.fnmatchStrMatcher,  # simple matcher with '*' glob character
        # stringsMatcher = util.reStrMatcher,   # if you prefer regular expressions
        allowRules=[
            # admins can do anything,
            # defaultDeny=False: if user does not have the admin role, we continue parsing rules
            util.AnyEndpointMatcher(role="admins", defaultDeny=False),

            util.StopBuildEndpointMatcher(role="owner"),

            # *-try groups can start "try" builds
            util.ForceBuildEndpointMatcher(builder="try", role="*-try"),
            # *-mergers groups can start "merge" builds
            util.ForceBuildEndpointMatcher(builder="merge", role="*-mergers"),
            # *-releasers groups can start "release" builds
            util.ForceBuildEndpointMatcher(builder="release", role="*-releasers"),
            # if future Buildbot implement new control, we are safe with this last rule
            util.AnyControlEndpointMatcher(role="admins")
        ],
        roleMatchers=[
            RolesFromGroups(groupPrefix="buildbot-"),
            RolesFromEmails(admins=["homer@springfieldplant.com"],
                            reaper-try=["007@mi6.uk"]),
            # role owner is granted when property owner matches the email of the user
            RolesFromOwner(role="owner")
        ]
    )
    c['www']['authz'] = authz

Using GitHub authentication and allowing access to control endpoints for users in the "Buildbot" organization:

.. code-block:: python

    from buildbot.plugins import *
    authz = util.Authz(
      allowRules=[
        util.AnyControlEndpointMatcher(role="BuildBot")
      ],
      roleMatchers=[
        util.RolesFromGroups()
      ]
    )
    auth=util.GitHubAuth('CLIENT_ID', 'CLIENT_SECRET')
    c['www']['auth'] = auth
    c['www']['authz'] = authz
