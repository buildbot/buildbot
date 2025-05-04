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

# this is a copy of buildbot.util.Notifier
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import overload

from twisted.internet import defer
from twisted.python import failure
from twisted.python import log

from buildbot_worker.util import Notifier

if TYPE_CHECKING:
    from typing import Any
    from typing import TypeVar

    from buildbot_worker.util.twisted import InlineCallbacksType

    _T = TypeVar('_T')


class DeferWaiter:
    """This class manages a set of Deferred objects and allows waiting for their completion"""

    def __init__(self) -> None:
        self._waited: dict[int, defer.Deferred] = {}
        self._finish_notifier: Notifier[None] = Notifier()

    def _finished(self, result: _T, d: defer.Deferred) -> _T:
        # most likely nothing is consuming the errors, so do it here
        if isinstance(result, failure.Failure):
            log.err(result)

        self._waited.pop(id(d))
        if not self._waited:
            self._finish_notifier.notify(None)
        return result

    @overload
    def add(self, d: defer.Deferred[_T]) -> defer.Deferred[_T]: ...

    @overload
    def add(self, d: Any) -> None: ...

    def add(self, d: defer.Deferred[_T] | Any) -> defer.Deferred[_T] | None:
        if not isinstance(d, defer.Deferred):
            return None

        self._waited[id(d)] = d
        d.addBoth(self._finished, d)
        return d

    def cancel(self) -> None:
        for d in list(self._waited.values()):
            d.cancel()
        self._waited.clear()

    def has_waited(self) -> bool:
        return bool(self._waited)

    @defer.inlineCallbacks
    def wait(self) -> InlineCallbacksType[None]:
        if not self._waited:
            return
        yield self._finish_notifier.wait()
