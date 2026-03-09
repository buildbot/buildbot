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
    from buildbot.util.twisted import InlineCallbacksType


class StateMixin:
    # state management

    name: str | None
    _objectid: int | None = None

    @defer.inlineCallbacks
    def getState(self, *args: Any, **kwargs: Any) -> InlineCallbacksType[Any]:
        # get the objectid, if not known
        if self._objectid is None:
            self._objectid = yield self.master.db.state.getObjectId(  # type: ignore[attr-defined]
                self.name,
                self.__class__.__name__,
            )

        rv = yield self.master.db.state.getState(self._objectid, *args, **kwargs)  # type: ignore[attr-defined]
        return rv

    @defer.inlineCallbacks
    def setState(self, key: str, value: Any) -> InlineCallbacksType[None]:
        # get the objectid, if not known
        if self._objectid is None:
            self._objectid = yield self.master.db.state.getObjectId(  # type: ignore[attr-defined]
                self.name,
                self.__class__.__name__,
            )

        yield self.master.db.state.setState(self._objectid, key, value)  # type: ignore[attr-defined]
