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

from twisted.internet import defer

from buildbot_worker.base import WorkerBase
from buildbot_worker.pb import BotPbLike
from buildbot_worker.pb import WorkerForBuilderPbLike

if TYPE_CHECKING:
    from buildbot_worker.util.twisted import InlineCallbacksType


class WorkerForBuilderNull(WorkerForBuilderPbLike):
    pass


class BotNull(BotPbLike):
    WorkerForBuilder = WorkerForBuilderNull


class LocalWorker(WorkerBase):
    def __init__(
        self,
        name: str,
        basedir: str,
        umask: int | None = None,
        unicode_encoding: str | None = None,
        delete_leftover_dirs: bool = False,
    ) -> None:
        super().__init__(
            name,
            basedir,
            BotNull,
            umask=umask,
            unicode_encoding=unicode_encoding,
            delete_leftover_dirs=delete_leftover_dirs,
        )

    @defer.inlineCallbacks
    def startService(self) -> InlineCallbacksType[None]:
        # importing here to avoid dependency on buildbot master package
        from buildbot.worker.protocols.null import Connection  # noqa: PLC0415

        yield WorkerBase.startService(self)
        self.workername = self.name
        conn = Connection(self)
        # I don't have a master property, but my parent has.
        assert self.parent is not None
        master = self.parent.master
        res = yield master.workers.newConnection(conn, self.name)
        if res:
            yield self.parent.attached(conn)
            # detached() will be called automatically on connection disconnection which is
            # invoked from the master side when the AbstarctWorker.stopService() is called.
