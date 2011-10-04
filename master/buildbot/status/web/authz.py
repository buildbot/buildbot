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

        if kwargs:
            raise ValueError("unknown authorization action(s) " + ", ".join(kwargs.keys()))

    def getUsername(self, request):
        return request.args.get("username", ["<unknown>"])[0]

    def getPassword(self, request):
        return request.args.get("passwd", ["<no-password>"])[0]

    def advertiseAction(self, action):
        """Should the web interface even show the form for ACTION?"""
        if action not in self.knownActions:
            raise KeyError("unknown action")
        cfg = self.config.get(action, False)
        if cfg:
            return True
        return False

    def needAuthForm(self, action):
        """Does this action require an authentication form?"""
        if action not in self.knownActions:
            raise KeyError("unknown action")
        cfg = self.config.get(action, False)
        if cfg == 'auth' or callable(cfg):
            return True
        return False

    def actionAllowed(self, action, request, *args):
        """Is this ACTION allowed, given this http REQUEST?"""
        if action not in self.knownActions:
            raise KeyError("unknown action")
        cfg = self.config.get(action, False)
        if cfg:
            if cfg == 'auth' or callable(cfg):
                if not self.auth:
                    return defer.succeed(False)
                user = self.getUsername(request)
                passwd = self.getPassword(request)
                if user == "<unknown>" or passwd == "<no-password>":
                    return defer.succeed(False)

                d = defer.maybeDeferred(self.auth.authenticate, user, passwd)
                def check_authenticate(res, cfg, user, *args):
                    if res:
                        if callable(cfg) and not cfg(user, *args):
                            return False
                        return True
                    return False
                d.addCallback(check_authenticate, cfg, user, *args)
                return d
            else:
                return defer.succeed(True) # anyone can do this..
        return defer.succeed(False)
