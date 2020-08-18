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


from twisted.application import strports
from twisted.cred import checkers
from twisted.cred import credentials
from twisted.cred import error
from twisted.cred import portal
from twisted.internet import defer
from twisted.python import log
from twisted.spread import pb
from zope.interface import implementer

from buildbot.process.properties import Properties
from buildbot.util import bytes2unicode
from buildbot.util import service
from buildbot.util import unicode2bytes
from buildbot.util.eventual import eventually

debug = False


class PBManager(service.AsyncMultiService):

    """
    A centralized manager for PB ports and authentication on them.

    Allows various pieces of code to request a (port, username) combo, along
    with a password and a perspective factory.
    """

    def __init__(self):
        super().__init__()
        self.setName('pbmanager')
        self.dispatchers = {}

    @defer.inlineCallbacks
    def register(self, portstr, username, password, pfactory):
        """
        Register a perspective factory PFACTORY to be executed when a PB
        connection arrives on PORTSTR with USERNAME/PASSWORD.  Returns a
        Registration object which can be used to unregister later.
        """
        # do some basic normalization of portstrs
        if isinstance(portstr, type(0)) or ':' not in portstr:
            portstr = "tcp:{}".format(portstr)

        reg = Registration(self, portstr, username)

        if portstr not in self.dispatchers:
            disp = self.dispatchers[portstr] = Dispatcher(portstr)
            yield disp.setServiceParent(self)
        else:
            disp = self.dispatchers[portstr]

        disp.register(username, password, pfactory)

        return reg

    @defer.inlineCallbacks
    def _unregister(self, registration):
        disp = self.dispatchers[registration.portstr]
        disp.unregister(registration.username)
        registration.username = None
        if not disp.users:
            disp = self.dispatchers[registration.portstr]
            del self.dispatchers[registration.portstr]
            yield disp.disownServiceParent()


class Registration:

    def __init__(self, pbmanager, portstr, username):
        self.portstr = portstr
        "portstr this registration is active on"
        self.username = username
        "username of this registration"

        self.pbmanager = pbmanager

    def __repr__(self):
        return "<pbmanager.Registration for {} on {}>".format(self.username, self.portstr)

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
        return "<pbmanager.Dispatcher for {} on {}>".format(", ".join(list(self.users)),
                                                            self.portstr)

    def startService(self):
        assert not self.port
        self.port = strports.listen(self.portstr, self.serverFactory)
        return super().startService()

    @defer.inlineCallbacks
    def stopService(self):
        # stop listening on the port when shut down
        assert self.port
        port, self.port = self.port, None
        yield port.stopListening()
        yield super().stopService()

    def register(self, username, password, pfactory):
        if debug:
            log.msg("registering username '{}' on pb port {}: {}".format(username, self.portstr,
                                                                         pfactory))
        if username in self.users:
            raise KeyError("username '{}' is already registered on PB port {}".format(username,
                                                                                      self.portstr))
        self.users[username] = (password, pfactory)

    def unregister(self, username):
        if debug:
            log.msg("unregistering username '{}' on pb port {}".format(username, self.portstr))
        del self.users[username]

    # IRealm

    @defer.inlineCallbacks
    def requestAvatar(self, username, mind, interface):
        assert interface == pb.IPerspective
        username = bytes2unicode(username)

        persp = None
        if username in self.users:
            _, afactory = self.users.get(username)
            persp = yield afactory(mind, username)

        if not persp:
            raise ValueError("no perspective for '{}'".format(username))

        yield persp.attached(mind)

        return (pb.IPerspective, persp, lambda: persp.detached(mind))

    # ICredentialsChecker

    @defer.inlineCallbacks
    def requestAvatarId(self, creds):
        p = Properties()
        p.master = self.master
        username = bytes2unicode(creds.username)
        try:
            yield self.master.initLock.acquire()
            if username in self.users:
                password, _ = self.users[username]
                password = yield p.render(password)
                matched = creds.checkPassword(unicode2bytes(password))
                if not matched:
                    log.msg("invalid login from user '{}'".format(username))
                    raise error.UnauthorizedLogin()
                return creds.username
            log.msg("invalid login from unknown user '{}'".format(username))
            raise error.UnauthorizedLogin()
        finally:
            # brake the callback stack by returning to the reactor
            # before waking up other waiters
            eventually(self.master.initLock.release)
