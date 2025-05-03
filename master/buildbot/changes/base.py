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
from typing import Any

from twisted.internet import defer
from twisted.python import log
from zope.interface import implementer

from buildbot import config
from buildbot.interfaces import IChangeSource
from buildbot.util import service
from buildbot.util.poll import method as poll_method

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


@implementer(IChangeSource)
class ChangeSource(service.ClusteredBuildbotService):
    def describe(self) -> str:
        return "ChangeSource"

    # activity handling

    def activate(self) -> defer.Deferred[None]:
        return defer.succeed(None)

    def deactivate(self) -> defer.Deferred[None]:
        return defer.succeed(None)

    # service handling

    def _getServiceId(self) -> defer.Deferred[int]:
        return self.master.data.updates.findChangeSourceId(self.name)

    def _claimService(self) -> defer.Deferred[bool]:
        return self.master.data.updates.trySetChangeSourceMaster(
            self.serviceid, self.master.masterid
        )

    def _unclaimService(self) -> defer.Deferred[bool]:
        return self.master.data.updates.trySetChangeSourceMaster(self.serviceid, None)


class ReconfigurablePollingChangeSource(ChangeSource):
    pollInterval: int | None = None
    pollAtLaunch: bool | None = None
    pollRandomDelayMin: int | None = None
    pollRandomDelayMax: int | None = None

    def checkConfig(
        self,
        name: str | None = None,
        pollInterval: int = 60 * 10,
        pollAtLaunch: bool = False,
        pollRandomDelayMin: int = 0,
        pollRandomDelayMax: int = 0,
    ) -> None:  # type: ignore[override]
        super().checkConfig(name=name)
        if pollInterval < 0:
            config.error(f"interval must be >= 0: {pollInterval}")
        if pollRandomDelayMin < 0:
            config.error(f"min random delay must be >= 0: {pollRandomDelayMin}")
        if pollRandomDelayMax < 0:
            config.error(f"max random delay must be >= 0: {pollRandomDelayMax}")
        if pollRandomDelayMin > pollRandomDelayMax:
            config.error(f"min random delay must be <= {pollRandomDelayMax}: {pollRandomDelayMin}")
        if pollRandomDelayMax >= pollInterval:
            config.error(f"max random delay must be < {pollInterval}: {pollRandomDelayMax}")

    @defer.inlineCallbacks
    def reconfigService(
        self,
        name: str | None = None,
        pollInterval: int = 60 * 10,
        pollAtLaunch: bool = False,
        pollRandomDelayMin: int = 0,
        pollRandomDelayMax: int = 0,
    ) -> InlineCallbacksType[None]:  # type: ignore[override]
        prevPollInterval = self.pollInterval
        self.pollInterval = pollInterval
        self.pollAtLaunch = pollAtLaunch
        self.pollRandomDelayMin = pollRandomDelayMin
        self.pollRandomDelayMax = pollRandomDelayMax
        yield super().reconfigService(name=name)

        # pollInterval change is the only value which makes sense to reconfigure check.
        if prevPollInterval != pollInterval and self.doPoll.running:
            yield self.doPoll.stop()
            # As a implementation detail, poller will 'pollAtReconfigure' if poll interval changes
            # and pollAtLaunch=True
            yield self.doPoll.start(
                interval=self.pollInterval,
                now=self.pollAtLaunch,
                random_delay_min=self.pollRandomDelayMin,
                random_delay_max=self.pollRandomDelayMax,
            )

    def poll(self) -> None:
        pass

    @poll_method
    def doPoll(self) -> defer.Deferred[Any]:
        d = defer.maybeDeferred(self.poll)
        d.addErrback(log.err, f'{self}: while polling for changes')
        return d

    def force(self) -> None:
        self.doPoll()

    def activate(self) -> defer.Deferred[None]:
        self.doPoll.start(
            interval=self.pollInterval,
            now=self.pollAtLaunch,
            random_delay_min=self.pollRandomDelayMin,
            random_delay_max=self.pollRandomDelayMax,
        )
        return defer.succeed(None)

    def deactivate(self) -> defer.Deferred[None]:
        return self.doPoll.stop()
