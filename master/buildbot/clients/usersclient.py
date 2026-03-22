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

# this class is known to contain cruft and will be looked at later, so
# no current implementation utilizes it aside from scripts.runner.

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import reactor
from twisted.spread import pb

from buildbot.util import unicode2bytes

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class UsersClient:
    """
    Client set up in buildbot.scripts.runner to send `buildbot user` args
    over a PB connection to perspective_commandline that will execute the
    args on the database.
    """

    def __init__(self, master: str, username: Any, password: Any, port: int | str) -> None:
        self.host = master
        self.username = unicode2bytes(username)
        self.password = unicode2bytes(password)
        self.port = int(port)

    @defer.inlineCallbacks
    def send(
        self, op: Any, bb_username: Any, bb_password: Any, ids: Any, info: Any
    ) -> InlineCallbacksType[Any]:
        f = pb.PBClientFactory()
        d = f.login(credentials.UsernamePassword(self.username, self.password))
        reactor.connectTCP(self.host, self.port, f)  # type: ignore[attr-defined]

        remote = yield d
        res = yield remote.callRemote("commandline", op, bb_username, bb_password, ids, info)
        remote.broker.transport.loseConnection()
        return res
