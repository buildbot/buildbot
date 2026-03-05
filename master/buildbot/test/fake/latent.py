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

import enum
from typing import Any

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.trial.unittest import SkipTest

from buildbot.test.fake.worker import SeverWorkerConnectionMixin
from buildbot.test.fake.worker import disconnect_master_side_worker
from buildbot.util.twisted import async_to_deferred
from buildbot.worker import AbstractLatentWorker

RemoteWorker: type | None = None
try:
    from buildbot_worker.bot import LocalWorker as RemoteWorker
    from buildbot_worker.pb import BotPbLike
except ImportError:
    pass


class States(enum.Enum):
    STOPPED = 0
    STARTING = 1
    STARTED = 2
    STOPPING = 3


class LatentController(SeverWorkerConnectionMixin):
    """
    A controller for ``ControllableLatentWorker``.

    https://glyph.twistedmatrix.com/2015/05/separate-your-fakes-and-your-inspectors.html

    Note that by default workers will connect automatically if True is passed
    to start_instance().

    Also by default workers will disconnect automatically just as
    stop_instance() is executed.
    """

    def __init__(
        self,
        case: Any,
        name: str,
        kind: Any = None,
        build_wait_timeout: int = 600,
        starts_without_substantiate: bool | None = None,
        **kwargs: Any,
    ) -> None:
        self.case = case
        self.build_wait_timeout = build_wait_timeout
        self.has_crashed = False
        self.worker = ControllableLatentWorker(name, self, **kwargs)
        self.remote_worker: Any = None

        if starts_without_substantiate is not None:
            self.worker.starts_without_substantiate = starts_without_substantiate

        self.state = States.STOPPED
        self.auto_stop_flag = False
        self.auto_start_flag = False
        self.auto_connect_worker = True
        self.auto_disconnect_worker = True

        self._start_deferred: defer.Deferred[Any] | None = None
        self._stop_deferred: defer.Deferred[Any] | None = None

        self.kind = kind
        self._started_kind: Any = None
        self._started_kind_deferred: Any = None

    @property
    def starting(self) -> bool:
        return self.state == States.STARTING

    @property
    def started(self) -> bool:
        return self.state == States.STARTED

    @property
    def stopping(self) -> bool:
        return self.state == States.STOPPING

    @property
    def stopped(self) -> bool:
        return self.state == States.STOPPED

    def auto_start(self, result: bool) -> None:
        self.auto_start_flag = result
        if self.auto_start_flag and self.state == States.STARTING:
            self.start_instance(True)

    @async_to_deferred
    async def start_instance(self, result: Any) -> None:
        await self.do_start_instance(result)
        d = self._start_deferred
        self._start_deferred = None
        d.callback(result)  # type: ignore[union-attr]

    @async_to_deferred
    async def do_start_instance(self, result: Any) -> None:
        assert self.state == States.STARTING
        self.state = States.STARTED
        if self.auto_connect_worker and result is True:
            await self.connect_worker()

    @async_to_deferred
    async def auto_stop(self, result: bool) -> None:
        self.auto_stop_flag = result
        if self.auto_stop_flag and self.state == States.STOPPING:
            await self.stop_instance(True)

    @async_to_deferred
    async def stop_instance(self, result: Any) -> None:
        await self.do_stop_instance()
        d = self._stop_deferred
        self._stop_deferred = None
        d.callback(result)  # type: ignore[union-attr]

    @async_to_deferred
    async def do_stop_instance(self) -> None:
        assert self.state == States.STOPPING
        self.state = States.STOPPED
        self._started_kind = None
        if self.auto_disconnect_worker:
            await self.disconnect_worker()

    @async_to_deferred
    async def connect_worker(self) -> None:
        if self.remote_worker is not None:
            return
        if RemoteWorker is None:
            raise SkipTest("buildbot-worker package is not installed")
        workdir = FilePath(self.case.mktemp())
        workdir.createDirectory()
        self.remote_worker = RemoteWorker(self.worker.name, workdir.path, False)
        await self.remote_worker.setServiceParent(self.worker)

    @async_to_deferred
    async def disconnect_worker(self) -> None:
        await super().disconnect_worker()
        if self.remote_worker is None:
            return

        self.remote_worker, worker = None, self.remote_worker

        disconnect_master_side_worker(self.worker)

        await worker.disownServiceParent()

    def setup_kind(self, build: Any) -> None:
        if build:
            self._started_kind_deferred = build.render(self.kind)
        else:
            self._started_kind_deferred = self.kind

    @async_to_deferred
    async def get_started_kind(self) -> Any:
        if self._started_kind_deferred:
            self._started_kind = await self._started_kind_deferred
            self._started_kind_deferred = None
        return self._started_kind

    def patchBot(self, case: Any, remoteMethod: str, patch: Any) -> None:
        case.patch(BotPbLike, remoteMethod, patch)


class ControllableLatentWorker(AbstractLatentWorker):
    """
    A latent worker that can be controlled by tests.
    """

    builds_may_be_incompatible = True

    def __init__(self, name: str, controller: LatentController, **kwargs: Any) -> None:
        self._controller = controller
        self._random_password_id = 0
        AbstractLatentWorker.__init__(self, name, None, **kwargs)

    def checkConfig(self, name: str, _: Any, **kwargs: Any) -> None:  # type: ignore[override]
        AbstractLatentWorker.checkConfig(
            self, name, None, build_wait_timeout=self._controller.build_wait_timeout, **kwargs
        )

    def reconfigService(self, name: str, _: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        return super().reconfigService(
            name,
            self.getRandomPass(),
            build_wait_timeout=self._controller.build_wait_timeout,
            **kwargs,
        )

    def _generate_random_password(self) -> str:
        self._random_password_id += 1
        return f'password_{self._random_password_id}'

    @async_to_deferred
    async def isCompatibleWithBuild(self, build_props: Any) -> bool:
        if self._controller.state == States.STOPPED:
            return True

        requested_kind = await build_props.render(self._controller.kind)
        curr_kind = await self._controller.get_started_kind()
        return requested_kind == curr_kind

    def start_instance(self, build: Any) -> defer.Deferred[bool]:
        self._controller.setup_kind(build)

        assert self._controller.state == States.STOPPED
        self._controller.state = States.STARTING

        if self._controller.auto_start_flag:
            self._controller.do_start_instance(True)
            return defer.succeed(True)

        self._controller._start_deferred = defer.Deferred()
        return self._controller._start_deferred

    @async_to_deferred
    async def stop_instance(self, fast: bool = False) -> bool:
        assert self._controller.state == States.STARTED
        self._controller.state = States.STOPPING

        if self._controller.auto_stop_flag:
            await self._controller.do_stop_instance()
            return True
        self._controller._stop_deferred = defer.Deferred()
        return await self._controller._stop_deferred

    def check_instance(self) -> tuple[bool, str]:
        return (not self._controller.has_crashed, "")
