.. bb:cfg:: www

Web Server
----------

.. note::

   As of Buildbot 0.9.0, the built-in web server replaces the old ``WebStatus`` plugin.

Buildbot contains a built-in web server.
This server is configured with the ``www`` configuration key, which specifies a dictionary with the following keys:

``port``
    The TCP port on which to serve requests.
    Note that SSL is not supported.
    To host Buildbot with SSL, use an HTTP proxy such as lighttpd, nginx, or Apache.
    If this is ``None``, the default, then the master will not implement a web server.

``json_cache_seconds``
    The number of seconds into the future at which an HTTP API response should expire.

``rest_minimum_version``
    The minimum supported REST API version.
    Any versions less than this value will not be available.
    This can be used to ensure that no clients are depending on API versions that will soon be removed from Buildbot.

``plugins``
    This key gives a dictionary of additional UI plugins to load, along with configuration for those plugins.
    These plugins must be separately installed in the Python environment, e.g., ``pip install buildbot-waterfall-view``.
    For example::

        c['www'] = {
            'plugins': {'waterfall_view': {'num_builds': 50}}
        }

``debug``
    If true, then debugging information will be output to the browser.
    This is best set to false (the default) on production systems, to avoid the possibility of information leakage.

``allowed_origins``
    This gives a list of origins which are allowed to access the Buildbot API (including control via JSONRPC 2.0).
    It implements cross-origin request sharing (CORS), allowing pages at origins other than the Buildbot UI to use the API.
    Each origin is interpreted as filename match expression, with ``?`` matching one character and ``*`` matching anything.
    Thus ``['*']`` will match all origins, and ``['https://*.buildbot.net']`` will match secure sites under ``buildbot.net``.
    The Buildbot UI will operate correctly without this parameter; it is only useful for allowing access from other web applications.

``auth``
   Authentication module to use for the web server.
   See :ref:`Web-Authentication`.

``avatar_methods``
    List of methods that can be used to get avatar pictures to use for the web server.
    By default, buildbot uses Gravatar to get images associated with each users, if you want to disable this you can just specify empty list::

        c['www'] = {
            'avatar_methods': []
        }

    For use of corporate pictures, you can use LdapUserInfo, which can also acts as an avatar provider.
    See :ref:`Web-Authentication`.

``logfileName``
    Filename used for http access logs, relative to the master directory.
    If set to ``None`` or the empty string, the content of the logs will land in the main :file:`twisted.log` log file.
    (Default to ``http.log``)

``logRotateLength``
    The amount of bytes after which the :file:`http.log` file will be rotated.
    (Default to the same value as for the :file:`twisted.log` file, set in :file:`buildbot.tac`)

``maxRotatedFiles``
    The amount of log files that will be kept when rotating
    (Default to the same value as for the :file:`twisted.log` file, set in :file:`buildbot.tac`)

``versions``
    Custom component versions that you'd like to display on the About page.
    Buildbot will automatically prepend the versions of Python, twisted and buildbot itself to the list.

    ``versions`` should be a list of tuples. for example::

        c['www'] = {
            # ...
            'versions': [
                ('master.cfg', '0.1'),
                ('OS', 'Ubuntu 14.04'),
            ]
        }

    The first element of a tuple stands for the name of the component, the second stands for the corresponding version.

``custom_templates_dir``
    This directory will be parsed for custom angularJS templates to replace the one of the original website templates.
    if the directory string is relative, it will be joined to the master's basedir.
    Either ``*.jade`` files or ``*.html`` files can be used, and will be used to override ``views/<filename>.html`` templates in the angularjs templateCache.
    Unlike with the regular nodejs based angularjs build system, Python only jade interpreter is used to parse the jade templates.
    ``pip install pyjade`` is be required to use jade templates.
    You can also override plugin's directives, but they have to be in another directory.

    .. code-block:: none

        # replace the template whose source is in:
        # www/base/src/app/builders/build/build.tpl.jade
        build.jade

        # replace the template whose source is in
        # www/console_view/src/module/view/builders-header/buildersheader.tpl.jade
        console_view/buildersheader.html

    Known differences between nodejs jade and pyjade:

        * quotes in attributes are not quoted. https://github.com/syrusakbary/pyjade/issues/132
          This means you should use double quotes for attributes e.g: ``tr(ng-repeat="br in buildrequests | orderBy:'-submitted_at'")``

``change_hook_dialects``
    See :ref:`Change-Hooks`.

.. note::

    The :bb:cfg:`buildbotURL` configuration value gives the base URL that all masters will use to generate links.
    The :bb:cfg:`www` configuration gives the settings for the webserver.
    In simple cases, the ``buildbotURL`` contains the hostname and port of the master, e.g., ``http://master.example.com:8010/``.
    In more complex cases, with multiple masters, web proxies, or load balancers, the correspondence may be less obvious.

.. _Web-Authentication:

Authentication plugins
~~~~~~~~~~~~~~~~~~~~~~

By default, Buildbot does not require people to authenticate in order to see the readonly data.
In order to access control features in the web UI, you will need to configure an authentication plugin.

Authentication plugins are implemented as classes, and passed as the ``auth`` parameter to :bb:cfg:`www`.

The available classes are described here:

.. py:class:: buildbot.www.auth.NoAuth()

    This class is the default authentication plugin, which disables authentication

.. py:class:: buildbot.www.auth.UserPasswordAuth(users)

    :param users: list of ``("user","password")`` tuples, or a dictionary of ``{"user": "password", ..}``

    Simple username/password authentication using a list of user/password tuples provided in the configuration file.

    ::

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.UserPasswordAuth({"homer": "doh!"}),
        }

.. py:class:: buildbot.www.auth.HTPasswdAuth(passwdFile)

    :param passwdFile: An :file:`.htpasswd` file to read

    This class implements simple username/password authentication against a standard :file:`.htpasswd` file.

    ::

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.HTPasswdAuth("my_htpasswd"),
        }

.. py:class:: buildbot.www.oauth2.GoogleAuth(clientId, clientSecret)

    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application

    This class implements an authentication with Google_ single sign-on.
    You can look at the Google_ oauth2 documentation on how to register your Buildbot instance to the Google systems.
    The developer console will give you the two parameters you have to give to ``GoogleAuth``

    Register your Buildbot instance with the ``BUILDBOT_URL/auth/login`` url as the allowed redirect URI.

    Example::

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GoogleAuth("clientid", "clientsecret"),
        }

    in order to use this module, you need to install the Python ``requests`` module

    .. code-block:: bash

            pip install requests

.. _Google: https://developers.google.com/accounts/docs/OAuth2

.. py:class:: buildbot.www.oauth2.GitHubAuth(clientId, clientSecret)

    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application

    This class implements an authentication with GitHub_ single sign-on.
    It functions almost identically to the :py:class:`~buildbot.www.oauth2.GoogleAuth` class.

    Register your Buildbot instance with the ``BUILDBOT_URL/auth/login`` url as the allowed redirect URI.

    The user's email-address (for e.g. authorization) is set to the "primary" address set by the user in GitHub.
    When using group-based authorization, the user's groups are equal to the names of the GitHub organizations the user
    is a member of.

    Example::

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GitHubAuth("clientid", "clientsecret"),
        }

.. _GitHub: http://developer.github.com/v3/oauth_authorizations/

.. py:class:: buildbot.www.oauth2.GitLabAuth(instanceUri, clientId, clientSecret)

    :param instanceUri: The URI of your GitLab instance
    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application

    This class implements an authentication with GitLab_ single sign-on.
    It functions almost identically to the :py:class:`~buildbot.www.oauth2.GoogleAuth` class.

    Register your Buildbot instance with the ``BUILDBOT_URL/auth/login`` url as the allowed redirect URI.

    Example::

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GitLabAuth("https://gitlab.com", "clientid", "clientsecret"),
        }

.. _GitLab: http://doc.gitlab.com/ce/integration/oauth_provider.html

.. py:class:: buildbot.www.oauth2.BitbucketAuth(clientId, clientSecret)

    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application

    This class implements an authentication with Bitbucket_ single sign-on.
    It functions almost identically to the :py:class:`~buildbot.www.oauth2.GoogleAuth` class.

    Register your Buildbot instance with the ``BUILDBOT_URL/auth/login`` url as the allowed redirect URI.

    Example::

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.BitbucketAuth("clientid", "clientsecret"),
        }

.. _Bitbucket: https://confluence.atlassian.com/bitbucket/oauth-on-bitbucket-cloud-238027431.html

.. py:class:: buildbot.www.auth.RemoteUserAuth

    :param header: header to use to get the username (defaults to ``REMOTE_USER``)
    :param headerRegex: regular expression to get the username from header value (defaults to ``"(?P<username>[^ @]+)@(?P<realm>[^ @]+)")``\.
                        Note that your at least need to specify a ``?P<username>`` regular expression named group.
    :param userInfoProvider: user info provider; see :ref:`User-Information`

    If the Buildbot UI is served through a reverse proxy that supports HTTP-based authentication (like apache or lighttpd), it's possible to to tell Buildbot to trust the web server and get the username from th request headers.

    Administrator must make sure that it's impossible to get access to Buildbot using other way than through frontend.
    Usually this means that Buildbot should listen for incoming connections only on localhost (or on some firewall-protected port).
    The reverse proxy must require HTTP authentication to access Buildbot pages (using any source for credentials, such as htpasswd, PAM, LDAP, Kerberos).

    Example::

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.RemoteUserAuth(),
        }

    A corresponding Apache configuration example

    .. code-block:: none

        <Location "/">
                AuthType Kerberos
                AuthName "Buildbot login via Kerberos"
                KrbMethodNegotiate On
                KrbMethodK5Passwd On
                KrbAuthRealms <<YOUR CORP REALMS>>
                KrbVerifyKDC off
                KrbServiceName Any
                Krb5KeyTab /etc/krb5/krb5.keytab
                KrbSaveCredentials Off
                require valid-user
                Order allow,deny

                Satisfy Any

                #] SSO
                RewriteEngine On
                RewriteCond %{LA-U:REMOTE_USER} (.+)$
                RewriteRule . - [E=RU:%1,NS]
                RequestHeader set REMOTE_USER %{RU}e

        </Location>

    The advantage of this sort of authentication is that it is uses a proven and fast implementation for authentication.
    The problem is that the only information that is passed to Buildbot is the username, and there is no way to pass any other information like user email, user groups, etc.
    That information can be very useful to the mailstatus plugin, or for authorization processes.
    See :ref:`User-Information` for a mechanism to supply that information.

.. _User-Information:

User Information
~~~~~~~~~~~~~~~~

For authentication mechanisms which cannot provide complete information about a user, Buildbot needs another way to get user data.
This is useful both for authentication (to fetch more data about the logged-in user) and for avatars (to fetch data about other users).

This extra information is provided by, appropriately enough, user info providers.
These can be passed to :py:class:`~buildbot.www.auth.RemoteUserAuth` and as an element of ``avatar_methods``.

This can also be passed to oauth2 authentication plugins.
In this case the username provided by oauth2 will be used, and all other informations will be taken from ldap (Full Name, email, and groups):

Currently only one provider is available:

.. py:class:: buildbot.ldapuserinfo.LdapUserInfo(uri, bindUser, bindPw, accountBase, accountPattern, groupBase=None, groupMemberPattern=None, groupName=None, accountFullName, accountEmail, avatarPattern=None, avatarData=None, accountExtraFields=None)

        :param uri: uri of the ldap server
        :param bindUser: username of the ldap account that is used to get the infos for other users (usually a "faceless" account)
        :param bindPw: password of the ``bindUser``
        :param accountBase: the base dn (distinguished name)of the user database
        :param accountPattern: the pattern for searching in the account database.
                               This must contain the ``%(username)s`` string, which is replaced by the searched username
        :param accountFullName: the name of the field in account ldap database where the full user name is to be found.
        :param accountEmail: the name of the field in account ldap database where the user email is to be found.
        :param groupBase: the base dn of the groups database.
        :param groupMemberPattern: the pattern for searching in the group database.
                                   This must contain the ``%(dn)s`` string, which is replaced by the searched username's dn
        :param groupName: the name of the field in groups ldap database where the group name is to be found.
        :param avatarPattern: the pattern for searching avatars from emails in the account database.
                              This must contain the ``%(email)s`` string, which is replaced by the searched email
        :param avatarData: the name of the field in groups ldap database where the avatar picture is to be found.
                           This field is supposed to contain the raw picture, format is automatically detected from jpeg, png or git.
        :param accountExtraFields: extra fields to extracts for use with the authorization policies.

        If one of the three optional groups parameters is supplied, then all of them become mandatory. If none is supplied, the retrieved user info has an empty list of groups.

Example::

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
            c['www'] = dict(port=PORT, allowed_origins=["*"],
                            url=c['buildbotURL'],
                            auth=util.RemoteUserAuth(userInfoProvider=userInfoProvider),
                            avatar_methods=[userInfoProvider,
                                            util.AvatarGravatar()])

.. note::

            In order to use this module, you need to install the ``python3-ldap`` module:

            .. code-block:: bash

                pip install python3-ldap

In the case of oauth2 authentications, you have to pass the userInfoProvider as keyword argument::

                from buildbot.plugins import util
                userInfoProvider = util.LdapUserInfo(...)
                c['www'] = {
                    # ...
                    'auth': util.GoogleAuth("clientid", "clientsecret", userInfoProvider=userInfoProvider),
                }



.. _Reverse_Proxy_Config:

Reverse Proxy Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is usually better to put buildbot behind a reverse proxy in production.

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
            ssl_session_cache      shared:SSL:1440m;
            ssl_session_timeout  1440m;

            # please consult latest nginx documentation for current secure encryption settings
            ssl_protocols ..
            ssl_ciphers ..
            ssl_prefer_server_ciphers   on;
            #

            # force https
            add_header Strict-Transport-Security "max-age=31536000; includeSubdomains;";
            spdy_headers_comp 5;

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

Here is a configuration that is known to work (Apache 2.4.10 / Debian 8), directly at the top of the domain.

.. code-block:: none


    <VirtualHost *:443>
        ServerName buildbot.example
        ServerAdmin webmaster@buildbot.example

        <Location /ws>
          ProxyPass ws://127.0.0.1:8020/ws
          ProxyPassReverse ws://127.0.0.1:8020/ws
        </Location>

        ProxyPass /ws !
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
Drawback is that it is not very obvious for newcomers.
The 'simple' example will however allow you to easily start by implementing an admins-have-all-rights setup.

Please carefully read the following documentation to understand how to setup authorization in Buildbot.

Authorization framework is tightly coupled to the REST API.
Authorization framework only works for HTTP, not for other means of interaction like IRC or try scheduler.
It allows or denies access to the REST APIs according to rules.

.. blockdiag::

    blockdiag {
      User -> AuthenticatedUser [label = Auth];
      AuthenticatedUser -> "RoleMatcher" -> Role <- "EndpointMatcher" <- "REST API Endpoint"

      User  [shape = actor];
      AuthenticatedUser  [shape = actor];
      RoleMatcher [shape = diamond];
      EndpointMatcher [shape = diamond];
    }

- Roles is a label that you give to a user.

  It is similar but different to the usual notion of group:

  - A user can have several roles, and a role can be given to several users.
  - Role is an application specific notion, while group is more organization specific notion.
  - Groups are given by the auth plugin, e.g ``ldap``, ``github``, and are not always in the precise control of the buildbot admins.
  - Roles can be dynamically assigned, according to the context.
    For example, there is the ``owner`` role, which can be given to a user for a build that he is at the origin, so that he can stop or rebuild only builds of his own.

- Endpoint matchers associate role requirements to REST API endpoints.
  The default policy is allow in case no matcher matches (see below why)

- Role matchers associate authenticated users to roles.

Authz Configuration
+++++++++++++++++++

.. py:class:: buildbot.www.authz.Authz(allowRules=[], roleMatcher=[], stringsMatcher=util.fnmatchStrMatcher)

    :param allowRules: List of :py:class:`EndpointMatcherBase` processed in order for each endpoint grant request.
    :param roleMatcher: List of RoleMatchers
    :param stringsMatcher: Selects algorithm used to make strings comparison (used to compare roles and builder names).
       can be :py:class:`util.fnmatchStrMatcher` or :py:class:`util.reStrMatcher` from ``from buildbot.plugins import util``

    :py:class:`Authz` needs to be configured in ``c['www']['authz']``

Endpoint matchers
+++++++++++++++++

Endpoint matchers are responsible for creating rules to match REST endpoints, and requiring roles for them.
Endpoint matchers are processed in the order they are configured.
The first rule matching an endpoint will prevent further rules from being checked.
To continue checking other rules when the result is `deny`, set `defaultDeny=False`.
If no endpoint matcher matches, then the access is granted.

One can implement the default deny policy by putting an :py:class:`AnyEndpointMatcher` with nonexistent role in the end of the list.
Please note that this will deny all REST apis, and most of the UI do not implement proper access denied message in case of such error.

The following sequence is implemented by each EndpointMatcher class.

- Check whether the requested endpoint is supported by this matcher
- Get necessary info from data api, and decides whether it matches.
- Look if the users has the required role.

Several endpoints matchers are currently implemented.
If you need a very complex setup, you may need to implement your own endpoint matchers.
In this case, you can look at the source code for detailed examples on how to write endpoint matchers.

.. py:class:: buildbot.www.authz.endpointmatchers.EndpointMatcherBase(role, defaultDeny=True)

    :param role: The role which grants access to this endpoint.
        List of roles is not supported, but a ``fnmatch`` expression can be provided to match several roles.

    :param defaultDeny: The role matcher algorithm will stop if this value is true, and if the endpoint matched.

    This is the base endpoint matcher.
    Its arguments are inherited by all the other endpoint matchers.

.. py:class:: buildbot.www.authz.endpointmatchers.AnyEndpointMatcher(role)

    :param role: The role which grants access to any endpoint.

    AnyEndpointMatcher grants all rights to a people with given role (usually "admins")

.. py:class:: buildbot.www.authz.endpointmatchers.ForceBuildEndpointMatcher(builder, role)

    :param builder: name of the builder.
    :param role: The role needed to get access to such endpoints.

    ForceBuildEndpointMatcher grants all rights to a people with given role (usually "admins")

.. py:class:: buildbot.www.authz.endpointmatchers.StopBuildEndpointMatcher(builder, role)

    :param builder: name of the builder.
    :param role: The role needed to get access to such endpoints.

    StopBuildEndpointMatcher grants all rights to a people with given role (usually "admins")

.. py:class:: buildbot.www.authz.endpointmatchers.RebuildBuildEndpointMatcher(builder, role)

    :param builder: name of the builder.
    :param role: The role needed to get access to such endpoints.

    RebuildBuildEndpointMatcher grants all rights to a people with given role (usually "admins")

Role matchers
+++++++++++++
Endpoint matchers are responsible for creating rules to match people and grant them roles.
You can grant roles from groups information provided by the Auth plugins, or if you prefer directly to people's email.


.. py:class:: buildbot.www.authz.roles.RolesFromGroups(groupPrefix)

    :param groupPrefix: prefix to remove from each group

    RolesFromGroups grants roles from the groups of the user.
    If a user has group ``buildbot-admin``, and groupPrefix is ``buildbot-``, then user will be granted the role 'admin'

    ex::

        roleMatchers=[
          util.RolesFromGroups(groupPrefix="buildbot-")
        ]

.. py:class:: buildbot.www.authz.roles.RolesFromEmails(roledict)

    :param roledict: dictionary with key=role, and value=list of email strings

    RolesFromEmails grants roles to users according to the hardcoded emails.

    ex::

        roleMatchers=[
          util.RolesFromEmails(admins=["my@email.com"])
        ]

.. py:class:: buildbot.www.authz.roles.RolesFromOwner(roledict)

    :param roledict: dictionary with key=role, and value=list of email strings

    RolesFromOwner grants a given role when property owner matches the email of the user

    ex::

        roleMatchers=[
            RolesFromOwner(role="owner")
        ]

.. py:class:: buildbot.www.authz.roles.RolesFromUsername(roles, usernames)

    :param roles: roles to assign when the username matches.
    :param usernames: list of usernames that have the roles.

    RolesFromUsername grants the given roles when the ``username`` property is within the list of usernames.

    ex::

        roleMatchers=[
            RolesFromUsername(roles=["admins"], usernames=["root"]),
            RolesFromUsername(roles=["developers", "integrators"], usernames=["Alice", "Bob"])
        ]


Example Configs
+++++++++++++++

Simple config which allows admin people to run everything:

.. code-block:: python

    from buildbot.plugins import *
    authz = util.Authz(
      allowRules=[
        util.StopBuildEndpointMatcher(role="admins"),
        util.ForceBuildEndpointMatcher(role="admins"),
        util.RebuildBuildEndpointMatcher(role="admins")
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

            StopBuildEndpointMatcher(role="owner"),

            # *-try groups can start "try" builds
            util.ForceBuildEndpointMatcher(builder="try", role="*-try"),
            # *-mergers groups can start "merge" builds
            util.ForceBuildEndpointMatcher(builder="merge", role="*-mergers"),
            # *-releasers groups can start "release" builds
            util.ForceBuildEndpointMatcher(builder="release", role="*-releasers"),
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

Using GitHub authentication and allowing access to all endpoints for users in the "BuildBot" organization:

.. code-block:: python

    from buildbot.plugins import *
    authz = util.Authz(
      allowRules=[
        util.AnyEndpointMatcher(role="BuildBot", defaultDeny=True)
      ],
      roleMatchers=[
        util.RolesFromGroups()
      ]
    )
    auth=util.GitHubAuth('CLIENT_ID', 'CLIENT_SECRET')
    c['www']['auth'] = auth
    c['www']['authz'] = authz
