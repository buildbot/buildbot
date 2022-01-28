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
from twisted.internet import defer
from twisted.python import log

from buildbot.util import service


class BaseManager(service.AsyncMultiService):
    """
    A centralized manager for connection ports and authentication on them.
    Allows various pieces of code to request a (port, username) combo, along
    with a password and a connection factory.
    """
    def __init__(self, name):
        super().__init__()
        self.setName(name)
        self.dispatchers = {}

    @defer.inlineCallbacks
    def register(self, config_portstr, username, password, pfactory):
        """
        Register a connection code to be executed after a user with its USERNAME/PASSWORD
        was authenticated and a valid high level connection can be established on a PORTSTR.
        Returns a Registration object which can be used to unregister later.
        """
        portstr = config_portstr

        # do some basic normalization of portstrs
        if isinstance(portstr, int) or ':' not in portstr:
            portstr = f"tcp:{portstr}".format(portstr)

        reg = Registration(self, portstr, username)

        if portstr not in self.dispatchers:
            disp = self.dispatchers[portstr] = self.dispatcher_class(config_portstr, portstr)
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
            del self.dispatchers[registration.portstr]
            yield disp.disownServiceParent()


class Registration:

    def __init__(self, manager, portstr, username):
        self.portstr = portstr
        "portstr this registration is active on"
        self.username = username
        "username of this registration"
        self.manager = manager

    def __repr__(self):
        return f"<base.Registration for {self.username} on {self.portstr}>"

    def unregister(self):
        """
        Unregister this registration, removing the username from the port, and
        closing the port if there are no more users left.  Returns a Deferred.
        """
        return self.manager._unregister(self)

    def getPort(self):
        """
        Helper method for testing; returns the TCP port used for this
        registration, even if it was specified as 0 and thus allocated by the
        OS.
        """
        disp = self.manager.dispatchers[self.portstr]
        return disp.port.getHost().port


class BaseDispatcher(service.AsyncService):
    debug = False

    def __init__(self, portstr):
        self.portstr = portstr
        self.users = {}
        self.port = None

    def __repr__(self):
        return f'<base.BaseDispatcher for {", ".join(list(self.users))} on {self.portstr}>'

    def start_listening_port(self):
        return strports.listen(self.portstr, self.serverFactory)

    def startService(self):
        assert not self.port
        self.port = self.start_listening_port()

        return super().startService()

    @defer.inlineCallbacks
    def stopService(self):
        # stop listening on the port when shut down
        assert self.port
        port, self.port = self.port, None
        yield port.stopListening()
        yield super().stopService()

    def register(self, username, password, pfactory):
        if self.debug:
            log.msg(f"registering username '{username}' on port {self.portstr}: {pfactory}")
        if username in self.users:
            raise KeyError(f"username '{username}' is already registered on port {self.portstr}")
        self.users[username] = (password, pfactory)

    def unregister(self, username):
        if self.debug:
            log.msg(f"unregistering username '{username}' on port {self.portstr}")
        del self.users[username]
