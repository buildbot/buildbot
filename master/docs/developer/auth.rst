Authentication
==============

Buildbot's HTTP authentication subsystem supports a rich set of information about users:

* User credentials: Username and proof of ownership of that username.
* User information: Additional information about the user, including

    * email address
    * full name
    * group membership

* Avatar information: a small image to represent the user.

Buildbot's authentication subsystem is designed to support several authentication modes:

* Simple username/password authentication.
    The Buildbot UI prompts for a username and password and the backend verifies them.

* External authentication by an HTTP Proxy.
    An HTTP proxy in front of Buildbot performs the authentication and passes the verified username to Buildbot in an HTTP Header.

* Authentication by a third-party website.
    Buildbot sends the user to another site such as GitHub to authenticate and receives a trustworthy assertion of the user's identity from that site.

Implementation
--------------

Authentication is implemented by an instance of :py:class:`~buildbot.www.auth.AuthBase`.
This instance is supplied directly by the user in the configuration file.
A reference to the instance is available at ``self.master.www.auth``.

Username / Password Authentication
----------------------------------

In this mode, the Buildbot UI displays a form allowing the user to specify a username and password.
When this form is submitted, the UI makes an AJAX call to ``/auth/login`` including HTTP Basic Authentication headers.
The master verifies the contents of the header and updates the server-side session to indicate a successful login or to contain a failure message.
Once the AJAX call is complete, the UI reloads the page, re-fetching ``/config.js``, which will include the username or failure message from the session.

Subsequent access is authorized based on the information in the session; the authentication credentials are not sent again.

External Authentication
-----------------------

Buildbot's web service can be run behind an HTTP proxy.
Many such proxies can be configured to perform authentication on HTTP connections before forwarding the request to Buildbot.
In these cases, the results of the authentication are passed to Buildbot in an HTTP header.

In this mode, authentication proceeds as follows:

* The web browser connects to the proxy, requesting the Buildbot home page
* The proxy negotiates authentication with the browser, as configured
* Once the user is authenticated, the proxy forwards the request goes to the Buildbot web service.
  The request includes a header, typically ``Remote-User``, containing the authenticated username.
* Buildbot reads the header and optionally connects to another service to fetch additional user information about the user.
* Buildbot stores all of the collected information in the server-side session.
* The UI fetches ``/config.js``, which includes the user information from the server-side session.

Note that in this mode, the HTTP proxy will send the header with every request, although it is only interpreted during the fetch of ``/config.js``.

Kerberos Example
~~~~~~~~~~~~~~~~

Kerberos is an authentication system which allows passwordless authentication on corporate networks.
Users authenticate once on their desktop environment, and the OS, browser, webserver, and corporate directory cooperate in a secure manner to share the authentication to a webserver.
This mechanism only takes care about the authentication problem, and no user information is shared other than the username.
The kerberos authentication is supported by a Apache front-end in ``mod_kerberos``.

Third-Party Authentication
--------------------------

Third-party authentication involves Buildbot redirecting a user's browser to another site to establish the user's identity.
Once that is complete, that site redirects the user back to Buildbot, including a cryptographically signed assertion about the user's identity.

The most common implementation of this sort of authentication is oAuth2.
Many big internet service companies are providing oAuth2 services to identify their users.
Most oAuth2 services provide authentication and user information in the same api.

The following process is used for third-party authentication:

* The web browser connects to buildbot ui
* A session cookie is created, but user is not yet authenticated.
  The UI adds a widget entitled ``Login via GitHub`` (or whatever third party is configured)
* When the user clicks on the widget, the UI fetches ``/auth/login``, which returns a bare URL on ``github.com``.
  The UI loads that URL in the browser, with an effect similar to a redirect.
* GitHub authenticates the user, if necessary, and requests permission for Buildbot to access the user's information.
* On success, the GitHub web page redirects back to Buildbot's ``/auth/login?code=..``, with an authentication code.
* Buildbot uses this code to request more information from GitHub, and stores the results in the server-side session.
  Finally, Buildbot returns a redirect response, sending the user's browser to the root of the Buildbot UI.
  The UI code will fetch ``/config.js``, which contains the login data from the session.

Logout
------

A "logout" button is available in the simple and third-party modes.
Such a button doesn't make sense for external authentication, since the proxy will immediately re-authenticate the user.

This button fetches ``/auth/logout``, which destroys the server-side session.
After this point, any stored authentication information is gone and the user is logged out.

Future Additions
----------------

* Browserid/Persona: This method is very similar to oauth2, and should be implemented in a similar way (i.e. two stage redirect + token-verify)
* Use the User table in db: This is a very similar to the UserPasswordAuth use cases (form + local db verification). Eventually, this method will require some work on the UI in order to populate the db, add a "register" button, verification email, etc. This has to be done in a ui plugin.
