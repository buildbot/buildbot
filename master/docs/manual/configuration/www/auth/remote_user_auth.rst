.. _WWW-Auth-RemoteUserAuth:

RemoteUserAuth
==============

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
