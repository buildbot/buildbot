# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import os

from buildbot.status.web.base import ActionResource
from buildbot.status.web.base import HtmlResource
from buildbot.status.web.base import path_to_authfail
from zope.interface import Attribute
from zope.interface import Interface
from zope.interface import implements
from buildbot.process.users import users
from twisted.python import log


class IAuth(Interface):

    """
    Represent an authentication method.

    Note that each IAuth instance contains a link to the BuildMaster that
    will be set once the IAuth instance is initialized.
    """

    master = Attribute('master', "Link to BuildMaster, set when initialized")

    def authenticate(self, user, passwd):
            """Check whether C{user} / C{passwd} are valid."""

    def getUserInfo(self, user):
            """return dict with user info.
            dict( fullName="", email="", groups=[])
            """

    def errmsg(self):
            """Get the reason authentication failed."""


class AuthBase:
    master = None  # set in status.web.baseweb
    err = ""

    def errmsg(self):
        return self.err

    def getUserInfo(self, user):
        """default dummy impl"""
        return dict(userName=user, fullName=user,
            email=user + "@localhost", groups=[user])


class BasicAuth(AuthBase):
    implements(IAuth)
    """Implement basic authentication against a list of user/passwd."""

    userpass = []
    """List of user/pass tuples."""

    def __init__(self, userpass):
        """C{userpass} is a list of (user, passwd)."""
        for item in userpass:
            assert isinstance(item, tuple) or isinstance(item, list)
            u, p = item
            assert isinstance(u, str)
            assert isinstance(p, str)
        self.userpass = userpass

    def authenticate(self, user, passwd):
        """Check that C{user}/C{passwd} is a valid user/pass tuple."""
        if not self.userpass:
            self.err = "Bad self.userpass data"
            return False
        for u, p in self.userpass:
            if user == u and passwd == p:
                self.err = ""
                return True
        self.err = "Invalid username or password"
        return False


class HTPasswdAuth(AuthBase):
    implements(IAuth)
    """Implement authentication against an .htpasswd file."""

    file = ""
    """Path to the .htpasswd file to use."""

    def __init__(self, file):
        """C{file} is a path to an .htpasswd file."""
        assert os.path.exists(file)
        self.file = file

    def authenticate(self, user, passwd):
        """Authenticate C{user} and C{passwd} against an .htpasswd file"""
        if not os.path.exists(self.file):
            self.err = "No such file: " + self.file
            return False
        # Fetch each line from the .htpasswd file and split it into a
        # [user, passwd] array.
        lines = [l.rstrip().split(':', 1)
                 for l in file(self.file).readlines()]
        # Keep only the line for this login
        lines = [l for l in lines if l[0] == user]
        if not lines:
            self.err = "Invalid user/passwd"
            return False
        hash = lines[0][1]
        res = self.validatePassword(passwd, hash)
        if res:
            self.err = ""
        else:
            self.err = "Invalid user/passwd"
        return res

    def validatePassword(self, passwd, hash):
        # This is the DES-hash of the password. The first two characters are
        # the salt used to introduce disorder in the DES algorithm.
        from crypt import crypt  # @UnresolvedImport
        return hash == crypt(passwd, hash[0:2])


class HTPasswdAprAuth(HTPasswdAuth):
    implements(IAuth)
    """Implement authentication against an .htpasswd file based on
libaprutil"""

    file = ""
    """Path to the .htpasswd file to use."""

    def __init__(self, file):
        HTPasswdAuth.__init__(self, file)

        # Try to load libaprutil throug ctypes
        self.apr = None
        try:
            from ctypes import CDLL
            from ctypes.util import find_library
            lib = find_library("aprutil-1")
            if lib:
                self.apr = CDLL(lib)
        except:
            self.apr = None

    def validatePassword(self, passwd, hash):
        # Use apr_password_validate from libaprutil if libaprutil is available.
        # Fallback to DES only checking from HTPasswdAuth
        if self.apr:
            return self.apr.apr_password_validate(passwd, hash) == 0
        else:
            return HTPasswdAuth.validatePassword(self, passwd, hash)


class UsersAuth(AuthBase):

    """Implement authentication against users in database"""
    implements(IAuth)

    def authenticate(self, user, passwd):
        """
        It checks for a matching uid in the database for the credentials
        and return True if a match is found, False otherwise.

        @param user: username portion of user credentials
        @type user: string

        @param passwd: password portion of user credentials
        @type passwd: string

        @returns: boolean via deferred.
        """
        d = self.master.db.users.getUserByUsername(user)

        def check_creds(user):
            if user:
                if users.check_passwd(passwd, user['bb_password']):
                    return True
            self.err = "no user found with those credentials"
            return False
        d.addCallback(check_creds)
        return d


class LDAPAuth(AuthBase):

    """Implement a synchronous authentication with an LDAP directory.
    modify from http://trac.buildbot.net/attachment/ticket/138/0012-Implement-an-LDAP-based-authentication-for-the-WebSt.patch"""
    implements(IAuth)

    basedn = ""
    """Base DN (Distinguished Name): the root of the LDAP directory tree

    e.g.: ou=people,dc=subdomain,dc=company,dc=com"""

    binddn = ""
    """The bind DN is the user on the external LDAP server permitted to
    search the LDAP directory.  You can leave this empty."""

    passwd = ""
    """Password required to query the LDAP server.  Leave this empty if
    you can query the server without password."""

    host = ""
    """Hostname of the LDAP server"""

    search = ""
    """Template string to use to search the user trying to login in the
    LDAP directory"""

    def __init__(self, server_uri, basedn, binddn="", passwd="",
                 search="(uid=%s)"):
        """Authenticate users against the LDAP server on C{host}.

        The arguments are documented above."""
        self.server_uri = server_uri
        self.basedn = basedn
        self.binddn = binddn
        self.passwd = passwd
        self.search = search

        self.search_conn = None
        # log.msg("ldap init")
        self.connect()

    def connect(self):
        """Setup the connections with the LDAP server."""
        import ldap
        # Close existing connections
        if self.search_conn:
            self.search_conn.unbind()
        # ldap v2 is outdated
        ldap.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)
        ldap.set_option(ldap.OPT_REFERRALS, 0)
        ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 10)
        # Connection used to locate the users in the LDAP DB.
        self.search_conn = ldap.initialize(self.server_uri)
        self.search_conn.bind_s(self.binddn, self.passwd,
                                ldap.AUTH_SIMPLE)

    def authenticate(self, username, password):
        """Authenticate the C{username} / C{password} with the LDAP server."""
        # log.msg("ldap %s %s" % (username,password))
        import ldap
        # Python-LDAP raises all sorts of exceptions to express various
        # failures, let's catch them all here and assume that if
        # anything goes wrong, the authentication failed.
        try:
            res = self._authenticate(username, password)
            log.msg("ldap res:%s" % (res))
            if res:
                self.err = ""
            return res
        except ldap.LDAPError, e:
            self.err = "LDAP error: " + str(e)
            log.msg(self.err)
            return False
        except:
            self.err = "unkown error: " + str(e)
            log.msg(self.err)
            return False

    def _authenticate(self, username, password):
        import ldap
        # Search the username in the LDAP DB
        try:
            result = self.search_conn.search_s(self.basedn,
                                               ldap.SCOPE_SUBTREE,
                                               self.search % username,
                                               ['objectclass'], 1)
            log.msg("ldap result:%s,%s" % (result, self.search % username))
        except ldap.SERVER_DOWN:
            self.err = "LDAP server seems down"
            log.msg(self.err)
            # Try to reconnect...
            self.connect()
            # FIXME: Check that this can't lead to an infinite recursion
            return self.authenticate(username, password)

        # Make sure we found a single user in the LDAP DB
        if not result or len(result) < 1:
            self.err = "user not found in the LDAP DB"
            log.msg(self.err)
            return False

        # Connection used to authenticate users with the LDAP DB.
        auth_conn = ldap.initialize(self.server_uri)
        # DN associated to this user
        ldap_dn = result[0][0]
        # log.msg('using ldap_dn = ' + ldap_dn)
        # Authenticate the user
        try:
            auth_conn.bind_s(ldap_dn, password, ldap.AUTH_SIMPLE)
        except ldap.INVALID_CREDENTIALS:
            self.err = "invalid credentials"
            log.msg(self.err)
            return False
        auth_conn.unbind()
        return True


class AuthFailResource(HtmlResource):
    pageTitle = "Authentication Failed"

    def content(self, request, cxt):
        templates = request.site.buildbot_service.templates
        template = templates.get_template("authfail.html")
        return template.render(**cxt)


class AuthzFailResource(HtmlResource):
    pageTitle = "Authorization Failed"

    def content(self, request, cxt):
        templates = request.site.buildbot_service.templates
        template = templates.get_template("authzfail.html")
        return template.render(**cxt)


class LoginResource(ActionResource):

    def performAction(self, request):
        authz = self.getAuthz(request)
        d = authz.login(request)

        def on_login(res):
            if res:
                status = request.site.buildbot_service.master.status
                root = status.getBuildbotURL()
                return request.requestHeaders.getRawHeaders('referer',
                                                            [root])[0]
            else:
                return path_to_authfail(request)
        d.addBoth(on_login)
        return d


class LogoutResource(ActionResource):

    def performAction(self, request):
        authz = self.getAuthz(request)
        authz.logout(request)
        status = request.site.buildbot_service.master.status
        root = status.getBuildbotURL()
        return request.requestHeaders.getRawHeaders('referer', [root])[0]
