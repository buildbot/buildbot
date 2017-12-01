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

from __future__ import absolute_import
from __future__ import print_function

from twisted.application import strports
from twisted.cred import checkers
from twisted.cred import credentials
from twisted.cred import error
from twisted.cred import portal
from twisted.internet import defer
from twisted.python import failure
from twisted.python import log
from twisted.spread import pb
from zope.interface import implementer

from buildbot.util import bytes2NativeString
from buildbot.util import service
from buildbot.util import unicode2bytes

debug = False


class PBManager(service.AsyncMultiService):

    """
    A centralized manager for PB ports and authentication on them.

    Allows various pieces of code to request a (port, username) combo, along
    with a password and a perspective factory.
    """

    def __init__(self):
        service.AsyncMultiService.__init__(self)
        self.setName('pbmanager')
        self.dispatchers = {}

    def register(self, portstr, username, password, pfactory):
        """
        Register a perspective factory PFACTORY to be executed when a PB
        connection arrives on PORTSTR with USERNAME/PASSWORD.  Returns a
        Registration object which can be used to unregister later.
        """
        # do some basic normalization of portstrs
        if isinstance(portstr, type(0)) or ':' not in portstr:
            portstr = "tcp:%s" % portstr

        reg = Registration(self, portstr, username)

        if portstr not in self.dispatchers:
            disp = self.dispatchers[portstr] = Dispatcher(portstr)
            disp.setServiceParent(self)
        else:
            disp = self.dispatchers[portstr]

        disp.register(username, password, pfactory)

        return reg

    def _unregister(self, registration):
        disp = self.dispatchers[registration.portstr]
        disp.unregister(registration.username)
        registration.username = None
        if not disp.users:
            disp = self.dispatchers[registration.portstr]
            del self.dispatchers[registration.portstr]
            return defer.maybeDeferred(disp.disownServiceParent)
        return defer.succeed(None)


class Registration(object):

    def __init__(self, pbmanager, portstr, username):
        self.portstr = portstr
        "portstr this registration is active on"
        self.username = username
        "username of this registration"

        self.pbmanager = pbmanager

    def __repr__(self):
        return "<pbmanager.Registration for %s on %s>" % \
            (self.username, self.portstr)

    def unregister(self):
        """
        Unregister this registration, removing the username from the port, and
        closing the port if there are no more users left.  Returns a Deferred.
        """
        return self.pbmanager._unregister(self)

    def getPort(self):
        """
        Helper method for testing; returns the TCP port used for this
        registration, even if it was specified as 0 and thus allocated by the
        OS.
        """
        disp = self.pbmanager.dispatchers[self.portstr]
        return disp.port.getHost().port


@implementer(portal.IRealm, checkers.ICredentialsChecker)
class Dispatcher(service.AsyncService):

    credentialInterfaces = [credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword]

    def __init__(self, portstr):
        self.portstr = portstr
        self.users = {}

        # there's lots of stuff to set up for a PB connection!
        self.portal = portal.Portal(self)
        self.portal.registerChecker(self)
        self.serverFactory = pb.PBServerFactory(self.portal)
        self.serverFactory.unsafeTracebacks = True
        self.port = None

    def __repr__(self):
        return "<pbmanager.Dispatcher for %s on %s>" % \
            (", ".join(list(self.users)), self.portstr)

    def startService(self):
        assert not self.port
        self.port = strports.listen(self.portstr, self.serverFactory)
        return service.AsyncService.startService(self)

    def stopService(self):
        # stop listening on the port when shut down
        assert self.port
        port, self.port = self.port, None
        d = defer.maybeDeferred(port.stopListening)
        d.addCallback(lambda _: service.AsyncService.stopService(self))
        return d

    def register(self, username, password, pfactory):
        if debug:
            log.msg("registering username '%s' on pb port %s: %s"
                    % (username, self.portstr, pfactory))
        if username in self.users:
            raise KeyError("username '%s' is already registered on PB port %s"
                           % (username, self.portstr))
        self.users[username] = (password, pfactory)

    def unregister(self, username):
        if debug:
            log.msg("unregistering username '%s' on pb port %s"
                    % (username, self.portstr))
        del self.users[username]

    # IRealm

    def requestAvatar(self, username, mind, interface):
        assert interface == pb.IPerspective
        username = bytes2NativeString(username)
        if username not in self.users:
            d = defer.succeed(None)  # no perspective
        else:
            _, afactory = self.users.get(username)
            d = defer.maybeDeferred(afactory, mind, username)

        # check that we got a perspective
        @d.addCallback
        def check(persp):
            if not persp:
                raise ValueError("no perspective for '%s'" % username)
            return persp

        # call the perspective's attached(mind)
        @d.addCallback
        def call_attached(persp):
            d = defer.maybeDeferred(persp.attached, mind)
            d.addCallback(lambda _: persp)  # keep returning the perspective
            return d

        # return the tuple requestAvatar is expected to return
        @d.addCallback
        def done(persp):
            return (pb.IPerspective, persp, lambda: persp.detached(mind))

        return d

    # ICredentialsChecker

    def requestAvatarId(self, creds):
        username = bytes2NativeString(creds.username)
        if username in self.users:
            password, _ = self.users[username]
            d = defer.maybeDeferred(creds.checkPassword, unicode2bytes(password))

            @d.addCallback
            def check(matched):
                if not matched:
                    log.msg("invalid login from user '%s'" % creds.username)
                    return failure.Failure(error.UnauthorizedLogin())
                return creds.username
            return d
        log.msg("invalid login from unknown user '%s'" % creds.username)
        return defer.fail(error.UnauthorizedLogin())
