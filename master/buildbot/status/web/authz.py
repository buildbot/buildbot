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
from buildbot.status.web.auth import IAuth
from buildbot.status.web.session import SessionManager

COOKIE_KEY="BuildBotSession"
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
    ]

    def __init__(self,
            default_action=False,
            auth=None,
            **kwargs):
        self.auth = auth
        if auth:
            assert IAuth.providedBy(auth)
        self.config = dict( (a, default_action) for a in self.knownActions )
        for act in self.knownActions:
            if act in kwargs:
                self.config[act] = kwargs[act]
                del kwargs[act]

        self.sessions = SessionManager()
        if kwargs:
            raise ValueError("unknown authorization action(s) " + ", ".join(kwargs.keys()))

    def advertiseAction(self, action, request):
        """Should the web interface even show the form for ACTION?"""
        if action not in self.knownActions:
            raise KeyError("unknown action")
        cfg = self.config.get(action, False)
        if cfg:
            if cfg == 'auth' or callable(cfg):
                return self.authenticated(request)
        return False
    def session(self, request):
        if COOKIE_KEY in request.received_cookies:
            cookie = request.received_cookies[COOKIE_KEY]
            return self.sessions.get(cookie)
        return None
            
    def authenticated(self, request):
        return self.session(request) != None
    def currentUserHTML(self, request):
        s = self.session(request)
        if s:
            return s.userInfosHTML()
        return "not authenticated?!"

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
                    if callable(cfg) and not cfg(self.currentUser(), *args):
                        return False
                    return True
                # retain old behaviour, if people have scripts
                # without cookie support
                passwd = request.args.get("passwd", [None])[0]
                if self.authenticated(request):
                    return defer.succeed(check_authenticate)
                elif passwd:
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
        return defer.succeed(False)
    def login(self, request):
        """Login one user, and return session cookie"""
        user = request.args.get("username", ["<unknown>"])[0]
        passwd = request.args.get("passwd", ["<no-password>"])[0]
        if user == "<unknown>" or passwd == "<no-password>":
            return defer.succeed(False)
        d = defer.maybeDeferred(self.auth.authenticate, user, passwd)
        def check_authenticate(res):
            if res:
                cookie, s = self.sessions.new(user, self.auth.getUserInfo(user))
                request.addCookie(COOKIE_KEY, cookie, s.getExpiration())
                return cookie
            else:
                return False
        d.addBoth(check_authenticate)
        return d
    def logout(self, request):
        if COOKIE_KEY in request.received_cookies:
            cookie = request.received_cookies[COOKIE_KEY]
            self.sessions.remove(cookie)
