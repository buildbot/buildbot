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

from twisted.cred import checkers
from twisted.cred import credentials
from twisted.cred import error
from twisted.cred import portal
from twisted.internet import defer
from twisted.python import log
from twisted.spread import pb
from zope.interface import Interface
from zope.interface import implementer

from buildbot.process.properties import Properties
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.util.eventual import eventually
from buildbot.worker.protocols.manager.base import BaseDispatcher
from buildbot.worker.protocols.manager.base import BaseManager

if TYPE_CHECKING:
    from twisted.cred.credentials import IUsernamePassword

    from buildbot.util.twisted import InlineCallbacksType


@implementer(portal.IRealm, checkers.ICredentialsChecker)
class Dispatcher(BaseDispatcher):
    credentialInterfaces = [credentials.IUsernamePassword, credentials.IUsernameHashedPassword]

    def __init__(self, config_portstr: str | int, portstr: str) -> None:
        super().__init__(portstr)
        # there's lots of stuff to set up for a PB connection!
        self.portal = portal.Portal(self)
        self.portal.registerChecker(self)
        self.serverFactory = pb.PBServerFactory(self.portal)
        self.serverFactory.unsafeTracebacks = True

    # IRealm

    @defer.inlineCallbacks
    def requestAvatar(
        self, avatarId: bytes | tuple[()], mind: object, *interfaces: type[Interface]
    ) -> InlineCallbacksType[tuple[type[Interface], object, Callable[[], None]]]:
        assert interfaces[0] == pb.IPerspective

        if isinstance(avatarId, tuple) and not avatarId:
            avatarIdStr = None  # Handle the empty tuple case
        else:
            avatarIdStr = bytes2unicode(avatarId)

        persp = None
        if avatarIdStr and avatarIdStr in self.users:
            _, afactory = self.users.get(avatarIdStr)  # type: ignore[misc]
            persp = yield afactory(mind, avatarIdStr)

        if not persp:
            raise ValueError(f"no perspective for '{avatarIdStr}'")

        yield persp.attached(mind)

        return (pb.IPerspective, persp, lambda: persp.detached(mind))

    # ICredentialsChecker

    @defer.inlineCallbacks
    def requestAvatarId(self, creds: IUsernamePassword) -> InlineCallbacksType[bytes | tuple[()]]:
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
                    log.msg(f"invalid login from user '{username}'")
                    raise error.UnauthorizedLogin()
                return creds.username
            log.msg(f"invalid login from unknown user '{username}'")
            raise error.UnauthorizedLogin()
        finally:
            # brake the callback stack by returning to the reactor
            # before waking up other waiters
            eventually(self.master.initLock.release)


class PBManager(BaseManager[Dispatcher]):
    def __init__(self) -> None:
        super().__init__('pbmanager')

    dispatcher_class = Dispatcher
