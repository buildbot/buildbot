Authentication
==============

.. py:module:: buildbot.www.auth

.. py:class:: AuthBase

    This class is the base class for all authentication methods.
    All authentications are not done at the same level, so several optional methods are available. This class implements default implementation. The login session is stored via twisted's ``request.getSession()``, and detailed used information is stored in ``request.getSession().user_info``. The session information is then sent to the UI via the ``config`` constant (in the ``user`` attribute of ``config``)

    .. py:attribute:: userInfoProvider

        Authentication modules are responsible for providing user information as detailed as possible. When there is a need to get additional information from another source, a userInfoProvider can optionally be specified.

    .. py:method:: reconfigAuth(master, new_config)

        :param master: the reference to the master
        :param new_config: the reference to the new configuration

        Auth module get information from the configuration

    .. py:method:: maybeAutoLogin(request)

        :param request: the request object

        Automatically login the user on one of the first request (when browser fetches ``/config.js``). This is the entry-point for reverse-proxy driven authentication.

        returns a deferred which fires with ignored results, when the authentication task is done.
        If it succeeded, ``request.getSession().user_info`` is defined.
        If it failed, ``resource.Error`` must be raised.
        If it is not implemented, the deferred will fire with user_info unset.

    .. py:method:: authenticateViaLogin(request)

        :param request: the request object

        Entry point for login via /login request. The default UI is passing the login credential via BasicAuth method. One can verify the login credential via deferred using this simple API. Once the user is authenticated, this method is responsible for filling ``request.getSession().user_info``, by calling ``updateUserInfo()``
        returns a deferred which fires with ignored results, when the authentication task is done.
        If it succeeded, ``request.getSession().user_info`` is defined.
        If it failed, ``resource.Error`` must be raised.
        If it is not implemented, the deferred will fire with user_info unset.

    .. py:method:: getLoginResource(master)

        :param request: the request object

        Entry point for getting a customized loginResource. This is a mean to reuse twisted code.

    .. py:method:: updateUserInfo(request)

        Separate entrypoint for getting user information. This is a mean to call self.userInfoProvider if provided.

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

    OAuth2Auth implements oauth2 2 phases authentication. With this method ``/login`` is called twice. Once without argument. It should return the URL the browser has to redirect in order to perform oauth2 authentication, and authorization. Then the oauth2 provider will redirect to ``/login?code=???``, and buildbot web server will verify the code using the oauth2 provider.

    Typical login process is:

    * UI calls the ``/login`` api, and redirect the browser to the returned oauth2 provider url
    * oauth2 provider shows a web page with a form for the user to authenticate, and ask the user the permission for buildbot to access its account.
    * oauth2 provider redirects the browser to ``/login?code=???``
    * OAuth2Auth module verifies the code, and get the user's additional information
    * buildbot UI is reloaded, with the user authenticated.

    This implementation is using sanction_

    .. py:method:: __init__(self, authUri, tokenUri, clientId, authUriConfig, tokenConfig)

        :param authUri: the Uri for the authentication part (first phase)

        :param tokenUri: the Uri for the verification of the token (second phase)

        :param clientId: the clientId

        :param authUriConfig: the additional configuration to pass to sanction_ ``auth_uri`` api.

        :param tokenConfig: the additional configuration to pass to sanction_ ``Client`` api for the verify token phase.

    .. py:method:: getUserInfoFromOAuthClient(self, c)

        This method is called after a successful authentication to get additional information about the user from the oauth2 provider.

.. _sanction: http://sanction.readthedocs.org/en/latest/
