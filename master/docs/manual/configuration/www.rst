.. bb:cfg:: www

Web Server
----------

.. note::

   As of Buildbot 0.9.0, the built-in web server replaces the old ``WebStatus`` plugin.

Buildbot contains a built-in web server.
This server is configured with the ``www`` configuration key, which specifies a dictionary with the following keys:

``port``
    The TCP port on which to serve requests.
    It might be an integer or any string accepted by `serverFromString <https://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.html#serverFromString>`_ (ex: "tcp:8010:interface=127.0.0.1" to listen on another interface).
    Note that SSL is not supported.
    To host Buildbot with SSL, use an HTTP proxy such as lighttpd, nginx, or Apache.
    If this is ``None`` (the default), then the master will not implement a web server.

``json_cache_seconds``
    The number of seconds into the future at which an HTTP API response should expire.

``rest_minimum_version``
    The minimum supported REST API version.
    Any versions less than this value will not be available.
    This can be used to ensure that no clients are depending on API versions that will soon be removed from Buildbot.

``plugins``
    This key gives a dictionary of additional UI plugins to load, along with configuration for those plugins.
    These plugins must be separately installed in the Python environment, e.g., ``pip install buildbot-waterfall-view``.
    See :ref:`UI-Plugins`.
    For example:

    .. code-block:: python

        c['www'] = {
            'plugins': {'waterfall_view': True}
        }

``default_page``
    Configure the default landing page of the web server, for example, to forward directly to another plugin. For example:

    .. code-block:: python

        c['www']['default_page'] = 'console'

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
    By default, Buildbot uses Gravatar to get images associated with each users, if you want to disable this you can just specify empty list:

    .. code-block:: python

        c['www'] = {
            'avatar_methods': []
        }

    You could also use the GitHub user avatar if GitHub authentication is enabled:

    .. code-block:: python

        c['www'] = {
            'avatar_methods': [util.AvatarGitHub()]
        }

    .. py:class:: AvatarGitHub(github_api_endpoint=None, token=None, debug=False, verify=False)

        :param string github_api_endpoint: specify the github api endpoint if you work with GitHub Enterprise
        :param string token: a GitHub API token to execute all requests to the API authenticated. It is strongly recommended to use a API token since it increases GitHub API rate limits significantly
        :param string client_id: a GitHub OAuth client ID to use with client secret to execute all requests to the API authenticated in place of token
        :param string client_secret: a GitHub OAuth client secret to use with client ID above
        :param boolean debug: logs every requests and their response
        :param boolean verify: disable ssl verification for the case you use temporary self signed certificates on a GitHub Enterprise installation

        This class requires `txrequests`_ package to allow interaction with GitHub REST API.

.. _txrequests: https://pypi.python.org/pypi/txrequests

    For use of corporate pictures, you can use LdapUserInfo, which can also act as an avatar provider.
    See :ref:`Web-Authentication`.

``logfileName``
    Filename used for HTTP access logs, relative to the master directory.
    If set to ``None`` or the empty string, the content of the logs will land in the main :file:`twisted.log` log file.
    (Defaults to ``http.log``)

``logRotateLength``
    The amount of bytes after which the :file:`http.log` file will be rotated.
    (Defaults to the same value as for the :file:`twisted.log` file, set in :file:`buildbot.tac`)

``maxRotatedFiles``
    The amount of log files that will be kept when rotating
    (Defaults to the same value as for the :file:`twisted.log` file, set in :file:`buildbot.tac`)

``versions``
    Custom component versions that you'd like to display on the About page.
    Buildbot will automatically prepend the versions of Python, twisted and Buildbot itself to the list.

    ``versions`` should be a list of tuples. For example:

    .. code-block:: python

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
    You can use this to slightly customize buildbot look for your project, but to add any logic, you will need to create a full-blown plugin.
    If the directory string is relative, it will be joined to the master's basedir.
    Buildbot uses the jade file format natively (which has been renamed to 'pug' in the nodejs ecosystem), but you can also use HTML format if you prefer.

    Either ``*.jade`` files or ``*.html`` files can be used to override templates with the same name in the UI.
    On the regular nodejs UI build system, we use nodejs's pug module to compile jade into html.
    For custom_templates, we use the pypugjs interpreter to parse the jade templates, before sending them to the UI.
    ``pip install pypugjs`` is required to use jade templates.
    You can also override plugin's directives, but they have to be in another directory, corresponding to the plugin's name in its ``package.json``.
    For example:

    .. code-block:: none

        # replace the template whose source is in:
        # www/base/src/app/builders/build/build.tpl.jade
        build.jade  # here we use a jade (aka pug) file

        # replace the template whose source is in
        # www/console_view/src/module/view/builders-header/console.tpl.jade
        console_view/console.html  # here we use html format

    Known differences between nodejs's pug and pyjade:

        * quotes in attributes are not quoted (https://github.com/syrusakbary/pyjade/issues/132).
          This means you should use double quotes for attributes, e.g.: ``tr(ng-repeat="br in buildrequests | orderBy:'-submitted_at'")``

        * pypugjs may have some differences but it is a maintained fork of pyjade. https://github.com/kakulukia/pypugjs

``change_hook_dialects``
    See :ref:`Change-Hooks`.

``cookie_expiration_time``

    This allows to define the timeout of the session cookie.
    Should be a `datetime.timedelta <https://docs.python.org/2/library/datetime.html#timedelta-objects>`_.
    Default is one week.

    .. code-block:: python

        import datetime
        c['www'] = {
            # ...
            'cookie_expiration_time': datetime.timedelta(weeks=2)
        }

``ui_default_config``

    Settings in the settings page are stored per browser.
    This configuration parameter allows to override the default settings for all your users.
    If a user already has changed a value from the default, this will have no effect to them.
    The settings page in the UI will tell you what to insert in your master.cfg to reproduce the configuration you have in your own browser.
    For example:

    .. code-block:: python

        c['www']['ui_default_config'] = {
            'Builders.buildFetchLimit': 500,
            'Workers.showWorkerBuilders': True,
        }

``ws_ping_interval``

    Send websocket pings every ``ws_ping_interval`` seconds.
    This is useful to avoid websocket timeouts when using reverse proxies or CDNs.
    If the value is 0 (the default), pings are disabled.

.. note::

    The :bb:cfg:`buildbotURL` configuration value gives the base URL that all masters will use to generate links.
    The :bb:cfg:`www` configuration gives the settings for the webserver.
    In simple cases, the ``buildbotURL`` contains the hostname and port of the master, e.g., ``http://master.example.com:8010/``.
    In more complex cases, with multiple masters, web proxies, or load balancers, the correspondence may be less obvious.

.. _UI-Plugins:

UI plugins
~~~~~~~~~~

.. _WaterfallView:

Waterfall View
++++++++++++++

Waterfall shows the whole Buildbot activity in a vertical time line.
Builds are represented with boxes whose height vary according to their duration.
Builds are sorted by builders in the horizontal axes, which allows you to see how builders are scheduled together.

    .. code-block:: bash

        pip install buildbot-waterfall-view

    .. code-block:: python

        c['www'] = {
            'plugins': {'waterfall_view': True}
        }


.. note::

    Waterfall is the emblematic view of Buildbot Eight.
    It allowed to see the whole Buildbot activity very quickly.
    Waterfall however had big scalability issues, and larger installs had to disable the page in order to avoid tens of seconds master hang because of a big waterfall page rendering.
    The whole Buildbot Eight internal status API has been tailored in order to make Waterfall possible.
    This is not the case anymore with Buildbot Nine, which has a more generic and scalable :ref:`Data_API` and :ref:`REST_API`.
    This is the reason why Waterfall does not display the steps details anymore.
    However nothing is impossible.
    We could make a specific REST api available to generate all the data needed for waterfall on the server.
    Please step-in if you want to help improve the Waterfall view.

.. _ConsoleView:

Console View
++++++++++++++

Console view shows the whole Buildbot activity arranged by changes as discovered by :ref:`Change-Sources` vertically and builders horizontally.
If a builder has no build in the current time range, it will not be displayed.
If no change is available for a build, then it will generate a fake change according to the ``got_revision`` property.

Console view will also group the builders by tags.
When there are several tags defined per builders, it will first group the builders by the tag that is defined for most builders.
Then given those builders, it will group them again in another tag cluster.
In order to keep the UI usable, you have to keep your tags short!

    .. code-block:: bash

        pip install buildbot-console-view

    .. code-block:: python

        c['www'] = {
            'plugins': {'console_view': True}
        }


.. note::

    Nine's Console View is the equivalent of Buildbot Eight's Console and tgrid views.
    Unlike Waterfall, we think it is now feature equivalent and even better, with its live update capabilities.
    Please submit an issue if you think there is an issue displaying your data, with screen shots of what happen and suggestion on what to improve.

.. _GridView:

Grid View
+++++++++

Grid view shows the whole Buildbot activity arranged by builders vertically and changes horizontally.
It is equivalent to Buildbot Eight's grid view.

By default, changes on all branches are displayed but only one branch may be filtered by the user.
Builders can also be filtered by tags.
This feature is similar to the one in the builder list.

   .. code-block:: bash

      pip install buildbot-grid-view

   .. code-block:: python

      c['www'] = {
          'plugins': {'grid_view': True}
      }

.. _Badges:

Badges
++++++

Buildbot badges plugin produces an image in SVG or PNG format with information about the last build for the given builder name.
PNG generation is based on the CAIRO_ SVG engine, it requires a bit more CPU to generate.


   .. code-block:: bash

      pip install buildbot-badges

   .. code-block:: python

      c['www'] = {
          'plugins': {'badges': {}}
      }

You can the access your builder's badges using urls like ``http://<buildbotURL>/badges/<buildername>.svg``.
The default templates are very much configurable via the following options:

.. code-block:: python

    {
        "left_pad"  : 5,
        "left_text": "Build Status",  # text on the left part of the image
        "left_color": "#555",  # color of the left part of the image
        "right_pad" : 5,
        "border_radius" : 5, # Border Radius on flat and plastic badges
        # style of the template availables are "flat", "flat-square", "plastic"
        "style": "plastic",
        "template_name": "{style}.svg.j2",  # name of the template
        "font_face": "DejaVu Sans",
        "font_size": 11,
        "color_scheme": {  # color to be used for right part of the image
            "exception": "#007ec6",  # blue
            "failure": "#e05d44",    # red
            "retry": "#007ec6",      # blue
            "running": "#007ec6",    # blue
            "skipped": "a4a61d",     # yellowgreen
            "success": "#4c1",       # brightgreen
            "unknown": "#9f9f9f",    # lightgrey
            "warnings": "#dfb317"    # yellow
        }
    }

Those options can be configured either using the plugin configuration:

.. code-block:: python

      c['www'] = {
          'plugins': {'badges': {"left_color": "#222"}}
      }

or via the URL arguments like ``http://<buildbotURL>/badges/<buildername>.svg?left_color=222``.
Custom templates can also be specified in a ``template`` directory nearby the ``master.cfg``.

The badgeio template
^^^^^^^^^^^^^^^^^^^^

A badges template was developed to standardize upon a consistent "look and feel" across the usage of
multiple CI/CD solutions, e.g.: use of Buildbot, Codecov.io, and Travis-CI. An example is shown below.

.. image:: ../../_images/badges-badgeio.png

To ensure the correct "look and feel", the following Buildbot configuration is needed:

.. code-block:: python

    c['www'] = {
        'plugins': {
            'badges': {
                "left_pad": 0,
                "right_pad": 0,
                "border_radius": 3,
                "style": "badgeio"
            }
        }
    }

.. note::

    It is highly recommended to use only with SVG.

.. _CAIRO: https://www.cairographics.org/

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

.. py:class:: buildbot.www.auth.NoAuth()

    This class is the default authentication plugin, which disables authentication.

.. py:class:: buildbot.www.auth.UserPasswordAuth(users)

    :param users: list of ``("user","password")`` tuples, or a dictionary of ``{"user": "password", ..}``

    Simple username/password authentication using a list of user/password tuples provided in the configuration file.

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.UserPasswordAuth({"homer": "doh!"}),
        }

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

.. py:class:: buildbot.www.auth.HTPasswdAuth(passwdFile)

    :param passwdFile: An :file:`.htpasswd` file to read

    This class implements simple username/password authentication against a standard :file:`.htpasswd` file.

    .. code-block:: python

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

.. py:class:: buildbot.www.oauth2.GitHubAuth(clientId, clientSecret)

    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application
    :param serverURL: The server URL if this is a GitHub Enterprise server
    :param apiVersion: The GitHub API version to use. One of ``3`` or ``4``
                       (V3/REST or V4/GraphQL). Defaults to 3.
    :param getTeamsMembership: When ``True`` fetch all team memberships for each of the
                               organizations the user belongs to. The teams will be included in the
                               user's groups as ``org-name/team-name``.
    :param debug: When ``True`` and using ``apiVersion=4`` show some additional log calls with the
                  GraphQL queries and responses for debugging purposes.

    This class implements an authentication with GitHub_ single sign-on.
    It functions almost identically to the :py:class:`~buildbot.www.oauth2.GoogleAuth` class.

    Register your Buildbot instance with the ``BUILDBOT_URL/auth/login`` url as the allowed redirect URI.

    The user's email-address (for e.g. authorization) is set to the "primary" address set by the user in GitHub.
    When using group-based authorization, the user's groups are equal to the names of the GitHub organizations the user
    is a member of.

    Example:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GitHubAuth("clientid", "clientsecret"),
        }

    Example for Enterprise GitHub:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GitHubAuth("clientid", "clientsecret",
                                    "https://git.corp.mycompany.com"),
        }

    An example on fetching team membership could be:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GitHubAuth("clientid", "clientsecret", apiVersion=4,
                                    getTeamsMembership=True),
            'authz': util.Authz(
                allowRules=[
                  util.AnyControlEndpointMatcher(role="core-developers"),
                ],
                roleMatchers=[
                  util.RolesFromGroups(groupPrefix='buildbot/')
                ]
              )
        }

  If the ``buildbot`` organization had two teams, for example, 'core-developers' and 'contributors',
  with the above example, any user belonging to those teams would be granted the roles matching those
  team names.

  In order to use this module, you need to install the Python ``requests`` module:

  .. code-block:: bash

          pip install requests

.. _GitHub: https://developer.github.com/apps/building-oauth-apps/authorizing-oauth-apps/#web-application-flow


.. py:class:: buildbot.www.oauth2.GitLabAuth(instanceUri, clientId, clientSecret)

    :param instanceUri: The URI of your GitLab instance
    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application

    This class implements an authentication with GitLab_ single sign-on.
    It functions almost identically to the :py:class:`~buildbot.www.oauth2.GoogleAuth` class.

    Register your Buildbot instance with the ``BUILDBOT_URL/auth/login`` URL as the allowed redirect URI.

    Example:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GitLabAuth("https://gitlab.com", "clientid", "clientsecret"),
        }

    In order to use this module, you need to install the Python ``requests`` module:

    .. code-block:: bash

            pip install requests

.. _GitLab: http://doc.gitlab.com/ce/integration/oauth_provider.html

.. py:class:: buildbot.www.oauth2.BitbucketAuth(clientId, clientSecret)

    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application

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

.. py:class:: buildbot.www.auth.RemoteUserAuth

    :param header: header to use to get the username (defaults to ``REMOTE_USER``)
    :param headerRegex: regular expression to get the username from header value (defaults to ``"(?P<username>[^ @]+)@(?P<realm>[^ @]+)")``\.
                        Note that you need at least to specify a ``?P<username>`` regular expression named group.
    :param userInfoProvider: user info provider; see :ref:`User-Information`

    If the Buildbot UI is served through a reverse proxy that supports HTTP-based authentication (like apache or lighttpd), it's possible to tell Buildbot to trust the web server and get the username from the request headers.

    The administrator must make sure that it's impossible to get access to Buildbot in any way other than through the frontend.
    Usually this means that Buildbot should listen for incoming connections only on localhost (or on some firewall-protected port).
    The reverse proxy must require HTTP authentication to access Buildbot pages (using any source for credentials, such as htpasswd, PAM, LDAP, Kerberos).

    Example:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.RemoteUserAuth(),
        }

    A corresponding Apache configuration example:

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
            c['www'] = dict(port=PORT, allowed_origins=["*"],
                            url=c['buildbotURL'],
                            auth=util.RemoteUserAuth(userInfoProvider=userInfoProvider),
                            avatar_methods=[userInfoProvider,
                                            util.AvatarGravatar()])

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

.. image:: ../../_images/auth_rules.*
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
