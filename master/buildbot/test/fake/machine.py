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

from buildbot.machine.latent import AbstractLatentMachine
from buildbot.machine.latent import States as MachineStates
from buildbot.util import service


class FakeMachineManager(service.AsyncMultiService):
    name: str | None = 'MachineManager'  # type: ignore

    @property
    def machines(self) -> dict[str, Any]:
        return self.namedServices

    def getMachineByName(self, name: str) -> Any | None:
        if name in self.machines:
            return self.machines[name]
        return None


class LatentMachineController:
    """A controller for ``ControllableLatentMachine``"""

    def __init__(self, name: str, **kwargs: Any) -> None:
        self.machine = ControllableLatentMachine(name, self, **kwargs)
        self._start_deferred: defer.Deferred[Any] | None = None
        self._stop_deferred: defer.Deferred[Any] | None = None

    def start_machine(self, result: Any) -> None:
        assert self.machine.state == MachineStates.STARTING
        d = self._start_deferred
        self._start_deferred = None
        if isinstance(result, Exception):
            d.errback(result)  # type: ignore[union-attr]
        else:
            d.callback(result)  # type: ignore[union-attr]

    def stop_machine(self, result: Any = True) -> None:
        assert self.machine.state == MachineStates.STOPPING
        d = self._stop_deferred
        self._stop_deferred = None
        if isinstance(result, Exception):
            d.errback(result)  # type: ignore[union-attr]
        else:
            d.callback(result)  # type: ignore[union-attr]


class ControllableLatentMachine(AbstractLatentMachine):
    """A latent machine that can be controlled by tests"""

    def __init__(self, name: str, controller: LatentMachineController, **kwargs: Any) -> None:
        self._controller = controller
        super().__init__(name, **kwargs)

    def start_machine(self) -> defer.Deferred[Any]:
        d: defer.Deferred[Any] = defer.Deferred()
        self._controller._start_deferred = d
        return d

    def stop_machine(self) -> defer.Deferred[Any]:
        d: defer.Deferred[Any] = defer.Deferred()
        self._controller._stop_deferred = d
        return d
