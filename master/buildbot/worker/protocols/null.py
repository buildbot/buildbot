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
from typing import Callable
from typing import cast

from twisted.internet import defer
from twisted.python import log

from buildbot.util.eventual import fireEventually
from buildbot.warnings import warn_deprecated
from buildbot.worker.protocols import base

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.spread.pb import RemoteReference

    from buildbot_worker.null import LocalWorker


class Listener(base.Listener):
    pass


class ProxyMixin:
    ImplClass: type

    def __init__(self, impl: object) -> None:
        assert isinstance(impl, self.ImplClass)
        self.impl = impl

    def callRemote(self, message: str, *args: Any, **kw: Any) -> Deferred[Any]:
        method = getattr(self.impl, f"remote_{message}", None)
        if method is None:
            raise AttributeError(f"No such method: remote_{message}")
        try:
            state = method(*args, **kw)
        except TypeError:
            log.msg(f"{method} didn't accept {args} and {kw}")
            raise
        # break callback recursion for large transfers by using fireEventually
        return fireEventually(state)

    def notifyOnDisconnect(self, cb: Callable) -> None:
        pass

    def dontNotifyOnDisconnect(self, cb: Callable) -> None:
        pass


# just add ProxyMixin capability to the RemoteCommandProxy
# so that callers of callRemote actually directly call the proper method
class RemoteCommandProxy(ProxyMixin):
    ImplClass = base.RemoteCommandImpl


class FileReaderProxy(ProxyMixin):
    ImplClass = base.FileReaderImpl


class FileWriterProxy(ProxyMixin):
    ImplClass = base.FileWriterImpl


class Connection(base.Connection):
    proxies: dict[type, type[ProxyMixin]] = {
        base.FileWriterImpl: FileWriterProxy,
        base.FileReaderImpl: FileReaderProxy,
    }

    def __init__(self, master_or_worker: LocalWorker, worker: LocalWorker | None = None) -> None:
        # All the existing code passes just the name to the Connection, however we'll need to
        # support an older versions of buildbot-worker using two parameter signature for some time.
        if worker is None:
            worker = master_or_worker
        else:
            warn_deprecated(
                '3.2.0',
                'LocalWorker: Using different version of buildbot-worker '
                + 'than buildbot is not supported',
            )

        assert worker.workername is not None
        super().__init__(worker.workername)
        self.worker = worker

    def loseConnection(self) -> None:
        self.notifyDisconnected()

    def remotePrint(self, message: str) -> Deferred[None]:
        return defer.maybeDeferred(self.worker.bot.remote_print, message)

    def remoteGetWorkerInfo(self) -> Deferred[dict[str, Any]]:
        return defer.maybeDeferred(self.worker.bot.remote_getWorkerInfo)

    def remoteSetBuilderList(
        self,
        builders: list[tuple[str, str]],
    ) -> Deferred[list[str]]:
        return defer.maybeDeferred(
            self.worker.bot.remote_setBuilderList,
            builders,
        )

    def remoteStartCommand(
        self,
        remoteCommand: base.RemoteCommandImpl,
        builderName: str,
        commandId: str,
        commandName: str,
        args: dict[str, Any],
    ) -> Deferred:
        args = self.createArgsProxies(args)
        workerforbuilder = self.worker.bot.builders[builderName]
        return defer.maybeDeferred(
            workerforbuilder.remote_startCommand,
            cast("RemoteReference", RemoteCommandProxy(remoteCommand)),
            commandId,
            commandName,
            args,
        )

    def remoteShutdown(self) -> Deferred[None]:
        return defer.maybeDeferred(self.worker.stopService)

    def remoteStartBuild(self, builderName: str) -> Deferred[None]:
        self.worker.bot.builders[builderName].remote_startBuild()
        return defer.succeed(None)

    def remoteInterruptCommand(self, builderName: str, commandId: str, why: str) -> Deferred:
        workerforbuilder = self.worker.bot.builders[builderName]
        return defer.maybeDeferred(
            workerforbuilder.remote_interruptCommand,
            commandId,
            why,
        )

    def get_peer(self) -> str:
        return "local"
