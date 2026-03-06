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
# Portions Copyright Buildbot Team Members

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from zope.interface import implementer

from buildbot import interfaces
from buildbot.util import service

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType
    from buildbot.worker.base import AbstractWorker


@implementer(interfaces.IMachine)
class Machine(service.BuildbotService):
    def checkConfig(self, name: str, **kwargs: Any) -> None:
        super().checkConfig(**kwargs)
        self.name = name
        self.workers: list[AbstractWorker] = []

    @defer.inlineCallbacks
    def reconfigService(self, name: str, **kwargs: Any) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield super().reconfigService(**kwargs)
        assert self.name == name

    def registerWorker(self, worker: AbstractWorker) -> None:
        assert worker.machine_name == self.name
        self.workers.append(worker)

    def unregisterWorker(self, worker: AbstractWorker) -> None:
        assert worker in self.workers
        self.workers.remove(worker)

    def __repr__(self) -> str:
        return f"<Machine '{self.name}' at {id(self)}>"
