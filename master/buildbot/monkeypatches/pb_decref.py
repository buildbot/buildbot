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
from typing import cast

if TYPE_CHECKING:
    from twisted.internet.interfaces import IReactorThreads
    from twisted.spread.pb import Broker


def patch() -> None:
    """
    RemoteReference.__del__ needs to send its decref from the reactor thread.

    __del__ can be called from a gc in another thread (eg. in the DB pool of Buildbot).
    """
    from twisted.internet import reactor  # noqa: PLC0415
    from twisted.spread.pb import RemoteReference  # noqa: PLC0415

    _reactor = cast("IReactorThreads", reactor)

    def sendDecRef(
        broker: Broker,
        luid: int,
    ) -> None:
        if not broker.disconnected:
            broker.sendDecRef(luid)

    def __del__(self: RemoteReference) -> None:
        if self.doRefCount:
            _reactor.callFromThread(sendDecRef, self.broker, self.luid)

    RemoteReference.__del__ = __del__  # type: ignore[method-assign]
