Authentication
==============

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


