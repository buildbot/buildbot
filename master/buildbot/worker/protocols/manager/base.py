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

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Callable
from typing import Generic
from typing import TypeVar

from twisted.application import strports
from twisted.internet import defer
from twisted.python import log

from buildbot.util import service

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IListeningPort
    from twisted.internet.protocol import ServerFactory

    from buildbot.util.twisted import InlineCallbacksType
    from buildbot.worker.protocols.base import Connection

_Dispatcher = TypeVar("_Dispatcher", bound="BaseDispatcher")


class BaseManager(service.AsyncMultiService, Generic[_Dispatcher]):
    """
    A centralized manager for connection ports and authentication on them.
    Allows various pieces of code to request a (port, username) combo, along
    with a password and a connection factory.
    """

    dispatcher_class: type[_Dispatcher]

    def __init__(self, name: str) -> None:
        super().__init__()
        self.setName(name)
        self.dispatchers: dict[str, _Dispatcher] = {}

    @defer.inlineCallbacks
    def register(
        self,
        config_portstr: str | int,
        username: str,
        password: str,
        pfactory: Callable[[object, str], Deferred[Connection]],
    ) -> InlineCallbacksType[Registration]:
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
            # FIXME: BaseDispatcher.__init__
            disp = self.dispatchers[portstr] = self.dispatcher_class(config_portstr, portstr)  # type: ignore[call-arg,arg-type]
            yield disp.setServiceParent(self)
        else:
            disp = self.dispatchers[portstr]

        disp.register(username, password, pfactory)

        return reg

    @defer.inlineCallbacks
    def _unregister(self, registration: Registration) -> InlineCallbacksType[None]:
        disp = self.dispatchers[registration.portstr]
        assert registration.username is not None
        disp.unregister(registration.username)
        registration.username = None
        if not disp.users:
            del self.dispatchers[registration.portstr]
            yield disp.disownServiceParent()


class Registration:
    def __init__(self, manager: BaseManager, portstr: str, username: str) -> None:
        self.portstr = portstr
        "portstr this registration is active on"
        self.username: str | None = username
        "username of this registration"
        self.manager = manager

    def __repr__(self) -> str:
        return f"<base.Registration for {self.username} on {self.portstr}>"

    def unregister(self) -> Deferred:
        """
        Unregister this registration, removing the username from the port, and
        closing the port if there are no more users left.  Returns a Deferred.
        """
        return self.manager._unregister(self)

    def getPort(self) -> int:
        """
        Helper method for testing; returns the TCP port used for this
        registration, even if it was specified as 0 and thus allocated by the
        OS.
        """
        disp = self.manager.dispatchers[self.portstr]
        assert disp.port is not None
        return disp.port.getHost().port


class BaseDispatcher(service.AsyncService):
    debug = False

    serverFactory: ServerFactory

    def __init__(self, portstr: str) -> None:
        self.portstr = portstr
        self.users: dict[str, tuple[str, Callable[[object, str], Deferred[Connection]]]] = {}
        self.port: IListeningPort | None = None

    def __repr__(self) -> str:
        return f'<base.BaseDispatcher for {", ".join(list(self.users))} on {self.portstr}>'

    def start_listening_port(self) -> IListeningPort:
        return strports.listen(self.portstr, self.serverFactory)

    def startService(self) -> None:
        assert not self.port
        self.port = self.start_listening_port()

        return super().startService()

    @defer.inlineCallbacks
    def stopService(self) -> InlineCallbacksType[None]:
        # stop listening on the port when shut down
        assert self.port
        port = self.port
        self.port = None
        yield port.stopListening()
        yield super().stopService()

    def register(
        self,
        username: str,
        password: str,
        pfactory: Callable[[object, str], Deferred[Connection]],
    ) -> None:
        if self.debug:
            log.msg(f"registering username '{username}' on port {self.portstr}: {pfactory}")
        if username in self.users:
            raise KeyError(f"username '{username}' is already registered on port {self.portstr}")
        self.users[username] = (password, pfactory)

    def unregister(self, username: str) -> None:
        if self.debug:
            log.msg(f"unregistering username '{username}' on port {self.portstr}")
        del self.users[username]
