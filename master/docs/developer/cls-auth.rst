Authentication
==============

.. py:module:: buildbot.www.auth

.. py:class:: AuthBase

    This class is the base class for all authentication methods.
    All authentications are not done at the same level, so several optional methods are available.
    This class implements default implementation.
    The login session is stored via twisted's ``request.getSession()``, and detailed used information is stored in ``request.getSession().user_info``.
    The session information is then sent to the UI via the ``config`` constant (in the ``user`` attribute of ``config``)

    .. py:attribute:: userInfoProvider

        Authentication modules are responsible for providing user information as detailed as possible.
        When there is a need to get additional information from another source, a userInfoProvider can optionally be specified.

    .. py:method:: reconfigAuth(master, new_config)

        :param master: the reference to the master
        :param new_config: the reference to the new configuration

        Reconfigure the authentication module.
        In the base class, this simply sets ``self.master``.

    .. py:method:: maybeAutoLogin(request)

        :param request: the request object
        :returns: Deferred

        This method is called when ``/config.js`` is fetched.
        If the authentication method supports automatic login, e.g., from a header provided by a frontend proxy, this method handles the login.

        If it succeeds, the method sets ``request.getSession().user_info``.
        If the login fails unexpectedly, it raises ``resource.Error``.
        The default implementation simply returns without setting ``user_info``.

    .. py:method:: getLoginResource()

        Return the resource representing ``/auth/login``.

    .. py:method:: getLogout()

        Return the resource representing ``/auth/logout``.

    .. py:method:: updateUserInfo(request)

        :param request: the request object

        Separate entrypoint for getting user information.
        This is a mean to call self.userInfoProvider if provided.

.. py:class:: UserInfoProviderBase

    Class that can be used, to get more info for the user like groups, in a separate database.

    .. py:method:: getUserInfo(username)

    returns the user infos, from the username used for login (via deferred)

    returns a :py:class:`dict` with following keys:

        * ``email``: email address of the user
        * ``full_name``: Full name of the user, like "Homer Simpson"
        * ``groups``: groups the user belongs to, like ["duff fans", "dads"]

.. py:module:: buildbot.www.oauth2

.. py:class:: OAuth2Auth

    OAuth2Auth implements oauth2 2 phases authentication.
    With this method ``/auth/login`` is called twice.
    Once without argument.
    It should return the URL the browser has to redirect in order to perform oauth2 authentication, and authorization.
    Then the oauth2 provider will redirect to ``/auth/login?code=???``, and buildbot web server will verify the code using the oauth2 provider.

    Typical login process is:

    * UI calls the ``/auth/login`` api, and redirect the browser to the returned oauth2 provider url
    * oauth2 provider shows a web page with a form for the user to authenticate, and ask the user the permission for buildbot to access its account.
    * oauth2 provider redirects the browser to ``/auth/login?code=???``
    * OAuth2Auth module verifies the code, and get the user's additional information
    * buildbot UI is reloaded, with the user authenticated.

    This implementation is using requests_
    subclasses must override following class attributes:
    * ``name`` Name of the oauth plugin
    * ``faIcon`` font awesome class to use for login button logo
    * ``resourceEndpoint`` URI of the resource where the authentication token is used
    * ``authUri`` URI the browser is pointed to to let the user enter creds
    * ``tokenUri`` URI to verify the browser code and get auth token
    * ``authUriAdditionalParams`` Additional parameters for the authUri
    * ``tokenUriAdditionalParams`` Additional parameters for the tokenUri

    .. py:method:: getUserInfoFromOAuthClient(self, c)

        This method is called after a successful authentication to get additional information about the user from the oauth2 provider.

.. _requests: http://docs.python-requests.org/en/latest/
