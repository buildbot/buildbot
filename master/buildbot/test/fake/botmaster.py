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

from typing import Any

from twisted.internet import defer

from buildbot.process import botmaster
from buildbot.util import service


class FakeBotMaster(service.AsyncMultiService, botmaster.LockRetrieverMixin):
    def __init__(self) -> None:
        super().__init__()
        self.setName("fake-botmaster")
        self.builders: dict[str, list[Any]] = {}
        self.buildsStartedForWorkers: list[str] = []
        self.delayShutdown = False
        self._starting_brid_to_cancel: dict[int, bool | str] = {}

    def getBuildersForWorker(self, workername: str) -> list[Any]:
        return self.builders.get(workername, [])

    def maybeStartBuildsForWorker(self, workername: str) -> None:
        self.buildsStartedForWorkers.append(workername)

    def maybeStartBuildsForAllBuilders(self) -> None:
        self.buildsStartedForWorkers += self.builders.keys()

    def workerLost(self, bot: Any) -> None:
        pass

    def cleanShutdown(
        self, quickMode: bool = False, stopReactor: bool = True
    ) -> defer.Deferred[None] | None:
        self.shuttingDown = True
        if self.delayShutdown:
            self.shutdownDeferred: defer.Deferred[None] = defer.Deferred()
            return self.shutdownDeferred
        return None

    def add_in_progress_buildrequest(self, brid: int) -> None:
        self._starting_brid_to_cancel[brid] = False

    def remove_in_progress_buildrequest(self, brid: int) -> bool | str | None:
        return self._starting_brid_to_cancel.pop(brid, None)

    def maybe_cancel_in_progress_buildrequest(self, brid: int, reason: str) -> None:
        if brid in self._starting_brid_to_cancel:
            self._starting_brid_to_cancel[brid] = reason
