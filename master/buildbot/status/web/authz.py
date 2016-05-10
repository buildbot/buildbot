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

from twisted.internet import defer
from twisted.internet.defer import Deferred
from buildbot.status.web.auth import IAuth
from buildbot.status.web.session import SessionManager, get_session_manager
from zope.interface import Interface, implements, Attribute

SESSION_KEY="BuildBotSession"

class ISessionHandler(Interface):
    """
    Represents a session handler.
    """

    key = Attribute('key', "Session key")
    sessions = Attribute('sessions', "Session manager")

    def createSessionToken(self, userinfo, user, request, sessions):
        """Creates a cookie or JWT token once the user is authenticated"""

    def removeSessionToken(self, request, sessions):
        """Removes the cookie or JWT token"""

    def validateSessionToken(self, request, sessions):
        """Validates the cookie or JWT token"""

    def getSession(self, request, sessions):
        """Return the session object for the request"""

    def logoutSession(self, request, sessions):
        """Handle the user logout when using cookie or JWT token"""

class BuildbotSession(object):
    implements(ISessionHandler)

    def __init__(self, key=None, useHttpHeader=False):
        self.key = key if key else SESSION_KEY
        self.useHttpHeader = useHttpHeader

    def createSessionToken(self, userinfo, user, request, sessions):
        cookie, s = sessions.new(user, userinfo)
        request.addCookie(self.key, cookie, expires=s.getExpiration(),path="/")
        request.received_cookies = {self.key: cookie}
        return cookie

    def removeSessionToken(self, request, sessions):
        if self.key in request.received_cookies:
            cookie = request.received_cookies[self.key]
            sessions.remove(cookie)

    def getSession(self, request, sessions):
        if self.key in request.received_cookies:
            cookie = request.received_cookies[self.key]
            return sessions.get(cookie)
        return None

    def validateSessionToken(self, request, sessions):
        if self.useHttpHeader:
            return request.getUser() != ''

        return self.getSession(request, sessions) is not None

    def logoutSession(self, request, sessions):
        session = self.getSession(request, sessions)
        if session is not None:
            session.expire()
            request.addCookie(self.key, None, expires=session.getExpiration(), path="/")

class JsonWebTokens(object):
    implements(ISessionHandler)

    def __init__(self, key=None, algorithm='HS256'):
        self.key = self.key = key if key else SESSION_KEY
        self.algorithm = algorithm

    def createSessionToken(self, userinfo, user, request, sessions):
        pass

    def removeSessionToken(self, request, sessions):
        pass

    def validateSessionToken(self, request, sessions):
        pass

    def getSession(self, request, sessions):
        pass

    def logoutSession(self, request, sessions):
        pass

class Authz(object):
    """Decide who can do what."""

    knownActions = [
    # If you add a new action here, be sure to also update the documentation
    # at docs/cfg-statustargets.texinfo
            'gracefulShutdown',
            'forceBuild',
            'forceAllBuilds',
            'pingBuilder',
            'stopBuild',
            'stopAllBuilds',
            'cancelPendingBuild',
            'stopChange',
            'cleanShutdown',
            'showUsersPage',
            'pauseSlave',
    ]

    defaultUserSettings = {
        "colorBlind": 0,
        "oldBuildDays": 7,
    }

    def __init__(self,
                 default_action=False,
                 auth=None,
                 useHttpHeader=False,
                 httpLoginUrl=False,
                 sessionHandler=None,
                 **kwargs):

        self.auth = auth
        if auth:
            assert IAuth.providedBy(auth)

        self.useHttpHeader = useHttpHeader
        self.httpLoginUrl = httpLoginUrl

        self.config = dict( (a, default_action) for a in self.knownActions )
        for act in self.knownActions:
            if act in kwargs:
                self.config[act] = kwargs[act]
                del kwargs[act]

        self.sessions = get_session_manager()
        if kwargs:
            raise ValueError("unknown authorization action(s) " + ", ".join(kwargs.keys()))

        self.sessionHandler = sessionHandler if sessionHandler is not None \
            else BuildbotSession(useHttpHeader=useHttpHeader)
        assert ISessionHandler.providedBy(self.sessionHandler)

    def session(self, request):
        return self.sessionHandler.getSession(request, self.sessions)

    def logoutUser(self, request):
        self.sessionHandler.logoutSession(request=request, sessions=self.sessions)

    def authenticated(self, request):
        return self.sessionHandler.validateSessionToken(request, self.sessions)

    def getUserInfo(self, user):
        if self.useHttpHeader:
            return dict(userName=user, fullName=user, email=user, groups=[ user ])
        s = self.sessions.getUser(user)
        if s:
            return s.infos

    def getUsername(self, request):
        """Get the userid of the user"""
        if self.useHttpHeader:
            return request.getUser()
        s = self.session(request)
        if s:
            return s.user
        return request.args.get("username", ["<unknown>"])[0]

    def getUsernameHTML(self, request):
        """Get the user formatated in html (with possible link to email)"""
        if self.useHttpHeader:
            return request.getUser()
        s = self.session(request)
        if s:
            return s.userInfosHTML()
        return "not authenticated?!"

    def getUsernameFull(self, request):
        """Get the full username as fullname <email>"""
        if self.useHttpHeader:
            return request.getUser()
        s = self.session(request)
        if s:
            fullname = "%(fullName)s %(email)s"%(s.infos)
            return fullname.decode('utf-8', 'ignore')
        else:
            return request.args.get("username", ["<unknown>"])[0]


    def getPassword(self, request):
        if self.useHttpHeader:
            return request.getPassword()
        return request.args.get("passwd", ["<no-password>"])[0]

    @defer.inlineCallbacks
    def getAllUserAttr(self, request):
        s = self.getUserInfo(self.getUsername(request))
        if s:
            userdb = request.site.buildbot_service.master.db.users
            user_settings = yield userdb.get_all_user_props(s['uid'])
            merged = dict(self.defaultUserSettings.items() + user_settings.items())
            defer.returnValue(merged)
        else:
            defer.returnValue(self.defaultUserSettings)

    @defer.inlineCallbacks
    def getUserAttr(self, request, attr, default=None):
        s = self.getUserInfo(self.getUsername(request))
        if s:
            userdb = request.site.buildbot_service.master.db.users
            val = yield userdb.get_user_prop(s['uid'], attr)
            if val is not None:
                defer.returnValue(val)

        defer.returnValue(default)

    def setUserAttr(self, request, attr_type, attr_data):
        s = self.getUserInfo(self.getUsername(request))
        if s:
            userdb = request.site.buildbot_service.master.db.users
            userdb.set_user_prop(s['uid'], attr_type, attr_data)

    def advertiseAction(self, action, request):
        """Should the web interface even show the form for ACTION?"""
        if action not in self.knownActions:
            raise KeyError("unknown action")
        cfg = self.config.get(action, False)
        if cfg:
            if cfg == 'auth' or callable(cfg):
                return self.authenticated(request)
        return cfg

    def actionAllowed(self, action, request, *args):
        """Is this ACTION allowed, given this http REQUEST?"""
        if action not in self.knownActions:
            raise KeyError("unknown action")
        cfg = self.config.get(action, False)
        if cfg:
            if cfg == 'auth' or callable(cfg):
                if not self.auth:
                    return defer.succeed(False)
                def check_authenticate(res):
                    if callable(cfg) and not cfg(self.getUsername(request), *args):
                        return False
                    return True
                # retain old behaviour, if people have scripts
                # without cookie support
                passwd = self.getPassword(request)
                if self.authenticated(request):
                    return defer.succeed(check_authenticate(None))
                elif passwd != "<no-password>":
                    def check_login(cookie):
                        ret = False
                        if type(cookie) is str:
                            ret = check_authenticate(None)
                            self.sessions.remove(cookie)
                        return ret
                    d = self.login(request)
                    d.addBoth(check_login)
                    return d
                else:
                    return defer.succeed(False)
        return defer.succeed(cfg)

    def login(self, request):
        """Login one user, and return session cookie"""
        if self.authenticated(request):
            return defer.succeed(False)

        user = request.args.get("username", ["<unknown>"])[0]
        passwd = request.args.get("passwd", ["<no-password>"])[0]
        if user == "<unknown>" or passwd == "<no-password>":
            return defer.succeed(False)
        if not self.auth:
            return defer.succeed(False)
        d = defer.maybeDeferred(self.auth.authenticate, user, passwd)

        def check_authenticate(res):
            if res:
                infos = self.auth.getUserInfo(user)
                if isinstance(infos, Deferred):
                    return infos.addBoth(self.sessionHandler.createSessionToken,
                                         user=user,
                                         request=request,
                                         sessions=self.sessions)
                else:
                    return self.sessionHandler.createSessionToken(userinfo=infos,
                                                                  user=user,
                                                                  request=request,
                                                                  sessions=self.sessions)
            else:
                return False

        d.addBoth(check_authenticate)
        return d

    def logout(self, request):
        self.sessionHandler.removeSessionToken(request=request, sessions=self.sessions)
