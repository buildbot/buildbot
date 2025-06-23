
.. _Config-WWW-Server:

Web Server
==========

Buildbot contains a built-in web server.
This server is configured with the ``www`` configuration key, which specifies a dictionary with the following keys:

``port``
    The TCP port on which to serve requests.
    It might be an integer or any string accepted by `serverFromString <https://docs.twistedmatrix.com/en/stable/api/twisted.internet.endpoints.html#serverFromString>`_ (ex: `"tcp:8010:interface=127.0.0.1"` to listen on another interface).
    Note that using twisted's SSL endpoint is discouraged.
    Use a reverse proxy that offers proper SSL hardening instead (see :ref:`Reverse_Proxy_Config`).
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

    .. py:class:: AvatarGitHub(github_api_endpoint=None, token=None, debug=False, verify=True)

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

``theme``

    Allows configuring certain properties of the web frontend, such as colors.
    The configuration value is a dictionary.
    The keys correspond to certain CSS variable names that are used throughout web frontend and made configurable.
    The values correspond to CSS values of these variables.

    The keys and values are not sanitized, so using data derived from user-supplied information is a security risk.

    The default is the following:

    .. code-block:: python

        c["www"]["theme"] = {
            "bb-sidebar-background-color": "#30426a",
            "bb-sidebar-header-background-color": "#273759",
            "bb-sidebar-header-text-color": "#fff",
            "bb-sidebar-title-text-color": "#627cb7",
            "bb-sidebar-footer-background-color": "#273759",
            "bb-sidebar-button-text-color": "#b2bfdc",
            "bb-sidebar-button-hover-background-color": "#1b263d",
            "bb-sidebar-button-hover-text-color": "#fff",
            "bb-sidebar-button-current-background-color": "#273759",
            "bb-sidebar-button-current-text-color": "#b2bfdc",
            "bb-sidebar-stripe-hover-color": "#e99d1a",
            "bb-sidebar-stripe-current-color": "#8c5e10",
        }

.. note::

    The :bb:cfg:`buildbotURL` configuration value gives the base URL that all masters will use to generate links.
    The :bb:cfg:`www` configuration gives the settings for the webserver.
    In simple cases, the ``buildbotURL`` contains the hostname and port of the master, e.g., ``http://master.example.com:8010/``.
    In more complex cases, with multiple masters, web proxies, or load balancers, the correspondence may be less obvious.
