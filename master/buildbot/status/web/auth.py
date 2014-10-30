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
from twisted.python import log
from twisted.internet import defer
from zope.interface import Interface, Attribute, implements
from buildbot.status.web.base import HtmlResource, ActionResource
from buildbot.status.web.base import path_to_authfail

from buildbot.process.users import users

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
        d = defer.maybeDeferred(self.master.db.users.findUserByAttr, user, "ldap", user)

        def result(uid):
            return dict(uid=uid, userName=user, fullName=user, email=user+"@localhost", groups=[ user ])

        d.addBoth(result)
        return d


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
        from crypt import crypt #@UnresolvedImport
        return hash == crypt(passwd, hash[0:2])


class HTPasswdAprAuth(HTPasswdAuth):
    implements(IAuth)
    """Implement authentication against an .htpasswd file based on libaprutil"""

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


class LDAPAuth(AuthBase):
    implements(IAuth)
    """ Implement authentication against an LDAP server"""

    def __init__(self, server, base_dn, bind_user, bind_password, filter):
        self.server = server
        self.base_dn = base_dn
        self.bind_user = bind_user
        self.bind_password = bind_password
        self.filter = filter
        self.uid = "uid"
        self.user_filter = "uid={user},cn=users"

        try:
            import ldap
            ldap.set_option(ldap.OPT_TIMEOUT, 5.0)
            ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 5.0)
            ldap.set_option(ldap.OPT_REFERRALS, 0)
        except ImportError:
            log.msg("LDAP module missing authentications will fail")

    def authenticate(self, user, passwd):
        try:
            import ldap
            l = ldap.initialize(self.server)

            try:
                bind_filter = ",".join([self.user_filter.replace("{user}", user), self.base_dn])
                l.simple_bind_s(bind_filter, passwd)
                ldap_result = l.search_s(self.base_dn, ldap.SCOPE_SUBTREE, self.filter.replace("{user}", user), [self.uid])
                l.unbind()

                found_user = None
                if len(ldap_result) > 0 and len(ldap_result[0]) > 1:
                    ldap_dict = ldap_result[0][1]
                    if self.uid in ldap_dict.keys():
                        found_user = ldap_dict[self.uid][0]

                if found_user == user:
                    return True

                return False
            except Exception, e:
                log.msg('Error while authenticating: %r' % e)
                return False
        except ImportError:
            log.msg("Cannot authenticate while the LDAP module is missing")
            return False

    def getUserInfo(self, user):
        try:
            import ldap
            l = ldap.initialize(self.server)
            attr = [self.uid, "mail"]

            try:
                if self.bind_user is None and self.bind_password is None:
                    l.simple_bind()
                else:
                    bind_filter = ",".join([self.user_filter.replace("{user}", self.bind_user), self.base_dn])
                    l.simple_bind_s(bind_filter, self.bind_password)
                ldap_result = l.search_s(self.base_dn, ldap.SCOPE_SUBTREE,
                                         filterstr=self.filter.replace("{user}", user), attrlist=attr)
                l.unbind()

                fullname = user
                email = None
                if len(ldap_result) > 0 and len(ldap_result[0]) > 1:
                    ldap_dict = ldap_result[0][1]
                    if self.uid in ldap_dict.keys():
                        fullname = ldap_dict[self.uid][0]
                        email = ldap_dict['mail'][0]

                if email is not None:
                    ident = "{0} <{1}>".format(fullname, email)
                    d = defer.maybeDeferred(self.master.db.users.findUserByAttr, ident, "ldap", ident)

                    def result(uid):
                        return dict(uid=uid, userName=user, fullName=fullname, email=email, groups=[ user ])

                    d.addBoth(result)
                    return d

                return False
            except Exception, e:
                log.msg('Error while getting user info: %r' % e)
                return False
        except ImportError:
            return False


class ADAuth(LDAPAuth):
    """ Implement authentication against an AD server"""

    def __init__(self, server, base_dn, bind_user, bind_password, filter):
        LDAPAuth.__init__(self, server, base_dn, bind_user, bind_password, filter)
        self.uid = "sAMAccountName"
        self.user_filter = "cn={user},cn=users"


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

class AuthFailResource(HtmlResource):
    pageTitle = "Authentication Failed"

    def content(self, request, cxt):
        templates =request.site.buildbot_service.templates
        template = templates.get_template("authfail.html") 
        return template.render(**cxt)

class AuthzFailResource(HtmlResource):
    pageTitle = "Authorization Failed"

    def content(self, request, cxt):
        templates =request.site.buildbot_service.templates
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
        return request.requestHeaders.getRawHeaders('referer',[root])[0]
