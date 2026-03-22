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

if TYPE_CHECKING:
    from buildbot.locks import BaseLock
    from buildbot.process.build import Build
    from buildbot.process.builder import Builder
    from buildbot.process.workerforbuilder import AbstractWorkerForBuilder
    from buildbot.util.twisted import InlineCallbacksType


@defer.inlineCallbacks
def get_real_locks_from_accesses_raw(
    locks: Any,
    props: Any,
    builder: Builder,
    workerforbuilder: AbstractWorkerForBuilder,
    config_version: int | None,
) -> InlineCallbacksType[list[tuple[BaseLock, Any]]]:
    workername = workerforbuilder.worker.workername  # type: ignore[union-attr]

    if props is not None:
        locks = yield props.render(locks)

    if not locks:
        return []

    locks = yield builder.botmaster.getLockFromLockAccesses(locks, config_version)  # type: ignore[union-attr, arg-type]
    return [(l.getLockForWorker(workername), a) for l, a in locks]


def get_real_locks_from_accesses(
    locks: Any, build: Build
) -> defer.Deferred[list[tuple[BaseLock, Any]]]:
    return get_real_locks_from_accesses_raw(
        locks,
        build,
        build.builder,
        build.workerforbuilder,  # type: ignore[arg-type]
        build.config_version,
    )
