Auth
====

The Auth subsystem is designed to support several kind of authentication mechanism.
There are several kind of information that can be taken from external user directories:

    * User credentials: We use external user directory to check the user credentials
    * User informations: We use external user directory to get more information about our users

        * user email
        * full username
        * user groups

    * Avatar information: some user directories can provide a picture for each users. Those pictures are not only needed for logged users, but also for users in the blame list.

Kerberos + Ldap
~~~~~~~~~~~~~~~
Kerberos is an authentication system which allows passwordless authentication on corporate networks. User authenticate once on their desktop environment, then the OS, browser, webserver, and corporate directory cooperate in a secure manner to share the authentication to a webserver.
This mechanism only takes care about the authentication problem, and there is no user information shared other than the userid. The kerberos authentication is supported by a Apache front-end in mod_kerberos

Kerberos itself only manage the user credential part of the problem.
For user information and avatars, one need to use other means. The easie mean is to talk to the ldap server associated with the kerberos servers.

The following process is then used in that case:

    * web browser connects to the Apache reverse-proxy, configured with mod_kerberos.
    * mod_kerberos performs authentication negociation between browser, and kerberos servers.
    * once user is authenticated, the requests goes through the web proxy to buildbot webserver. The ``REMOTE_USER=homer@PLANT`` header has been added to the request.
    * buildbot webserver recognise the header, and connects to ldap to find more information about this user.
    * buildbot webserver store this information, and adds a cookie in the browser.
    * browser continue loading the page, wants to display the avatar for this user.
    * browser requests the avatar rest endpoint, which in turn goes to ldap to fetch the picture, and return the picture itself. If ldap picture is not available for this users, the avatar rest endpoint will redirect to de-facto standard gravatar web service.

OAuth2
~~~~~~
OAuth2 is a standard protocol for user directories in the public internet. Many big internet service companies are providing oauth2 services for website to indentify their users.
Most Oauth2 services provides authentication and user information in the same api.

The following process is then used in that case:

    * webbrowser connects to buildbot ui
    * session cookie is created, but user is not yet authenticated, UI adds a widget  ``Login via GitHub``
    * web browser is redirected to github servers.
    * github web page ask user to tell its password again, and allow this website to access its user information.
    * on success github web page redirects to buildbot, with an authentication token.
    * buildbot use this authentication token to talk to github server and get more information about the user.


BasicAuth
~~~~~~~~~
Aside from the fancy authentication mechanisms, there is a need for the simple method that have been supported by buildbot for long:

    * buildbot UI provides a form allowing user to specify user and password
    * The password is verified against the local database

Potential future auth systems
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Browserid/Persona: This method is very similar to oauth2, and should be implemented in a similar way (i.e. two stage redirect + token-verify)

* Use the User table in db: This is a very similar to the BasicAuth use cases (form + local db verification). Eventually, this method will require some work on the UI in order to populate the db, add a "register" button, verification email, etc. This has to be done in a ui plugin.


API documentation
~~~~~~~~~~~~~~~~~

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

.. py:class:: UserInfoBase

    Class that can be used, to get more info for the user like groups, in a separate database.

    .. py:method:: getUserInfo(username)

    returns the user infos, from the username used for login (via deferred)

    returns a :py:class:`dict` with following keys:

        * ``email``: email address of the user
        * ``full_name``: Full name of the user, like "Homer Simpson"
        * ``groups``: groups the user belongs to, like ["duff fans", "dads"]

.. py:module:: buildbot.www.avatar

.. py:class:: AvatarBase

    Class that can be used, to get more the avatars for the users. This can be used for the authenticated users, but also for the users referenced by changes.

    .. py:method:: getUserAvatar(self, email, size, defaultAvatarUrl)

    returns the user's avatar, from the user's email (via deferred). If the data is directly available, this function returns a tuple ``(mime_type, picture_raw_data)``. If the data is available in another URL, this function can raise ``resource.Redirect(avatar_url)``, and the web server will redirect to the avatar_url.

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
