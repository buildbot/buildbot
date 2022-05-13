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

from twisted.internet import defer

from buildbot.machine.latent import AbstractLatentMachine
from buildbot.machine.latent import States as MachineStates
from buildbot.util import service


class FakeMachineManager(service.AsyncMultiService):
    name = "MachineManager"

    @property
    def machines(self):
        return self.namedServices

    def getMachineByName(self, name):
        if name in self.machines:
            return self.machines[name]
        return None


class LatentMachineController:
    """A controller for ``ControllableLatentMachine``"""

    def __init__(self, name, **kwargs):
        self.machine = ControllableLatentMachine(name, self, **kwargs)
        self._start_deferred = None
        self._stop_deferred = None

    def start_machine(self, result):
        assert self.machine.state == MachineStates.STARTING
        d, self._start_deferred = self._start_deferred, None
        if isinstance(result, Exception):
            d.errback(result)
        else:
            d.callback(result)

    def stop_machine(self, result=True):
        assert self.machine.state == MachineStates.STOPPING
        d, self._stop_deferred = self._stop_deferred, None
        if isinstance(result, Exception):
            d.errback(result)
        else:
            d.callback(result)


class ControllableLatentMachine(AbstractLatentMachine):
    """A latent machine that can be controlled by tests"""

    def __init__(self, name, controller, **kwargs):
        self._controller = controller
        super().__init__(name, **kwargs)

    def start_machine(self):
        d = defer.Deferred()
        self._controller._start_deferred = d
        return d

    def stop_machine(self):
        d = defer.Deferred()
        self._controller._stop_deferred = d
        return d
