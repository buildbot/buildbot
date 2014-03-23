Auth
====

.. py:module:: buildbot.www.auth

.. py:class:: AuthBase

    This class is the base class for all authentication methods.
    All authentications are not done at the same level, so several optional methods are available. This class implements default implementation. The login session is stored via twisted's ``request.getSession()``, and detailled used information is stored in ``request.getSession().user_infos``. The session information is then sent to the UI via the ``config`` constant (in the ``user`` attribute of ``config``)

    .. py:attribute:: userInfos

        Optionally additional user information can be gathered by this object.

    .. py:method:: reconfigAuth(master, new_config)

        :param master: the reference to the master
        :param new_config: the reference to the new configuration

        Auth module get information from the configuration

    .. py:method:: maybeAutoLogin(request)

        :param request: the request object

        Automatically login the user on one of the first request (when browser fetches ``/config.js``). This is the entrypoint for reverse-proxy driven authentication.

        returns a deferred which fires with ignored results, when the authentication task is done.
        If it succeeded, ``request.getSession().user_infos`` is defined.
        If it failed, ``resource.Error`` must be raised.
        If it is not implemented, the deferred will fire with user_infos unset.

    .. py:method:: authenticateViaLogin(request)

        :param request: the request object

        Entry point for login via /login request. The default UI is passing the login credential via BasicAuth method. One can verify the login credential via deferred using this simple API. Once the user is authenticated, this method is responsible for filling ``request.getSession().user_infos``, by calling ``updateUserInfos()``
        returns a deferred which fires with ignored results, when the authentication task is done.
        If it succeeded, ``request.getSession().user_infos`` is defined.
        If it failed, ``resource.Error`` must be raised.
        If it is not implemented, the deferred will fire with user_infos unset.

    .. py:method:: getLoginResource(master)

        :param request: the request object

        Entry point for getting a customized loginResource. This is a mean to reuse twisted code.

    .. py:method:: updateUserInfos(request)

        Separate entrypoint for getting user information. This is a mean to call self.userInfos if provided.

.. py:class:: UserInfosBase

    Class that can be used, to get more info for the user like groups, in a separate database.

    .. py:method:: getUserInfos(username)

    returns the user infos, from the username used for login (via deferred)

    returns a :py:class:`dict` with following keys:

        * ``email``: email address of the user
        * ``full_name``: Full name of the user, like "Homer Simpson"
        * ``groups``: groups the user belongs to, like ["duff fans", "dads"]

.. py:module:: buildbot.www.avatar

.. py:class:: AvatarBase

    Class that can be used, to get more the avatars for the users. This can be used for the authenticated users, but also for the users referenced by changes.

    .. py:method:: getUserAvatar(self, email, size, defaultAvatarUrl)

    returns the user's avatar, from the user's email (via deferred). If the data is directly available, this function returns a tuple ``(mime_type, picture_raw_data)``. If the data is available in another url, this function can raise ``resource.Redirect(avatar_url)``, and the web server will redirect to the avatar_url.

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

        :param authUri: the uri for the authentication part (first phasis)

        :param tokenUri: the uri for the verification of the token (second phasis)

        :param clientId: the clientId

        :param authUriConfig: the additionnal configuration to pass to sanction_ ``auth_uri`` api.

        :param tokenConfig: the additionnal configuration to pass to sanction_ ``Client`` api for the verify token phase.

    .. py:method:: getUserInfosFromOAuthClient(self, c)

        This method is called after a successful authentication to get additional information about the user from the oauth2 provider.

.. _sanction: http://sanction.readthedocs.org/en/latest/
