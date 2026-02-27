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
from typing import TypedDict

from twisted.internet import defer

from buildbot.util.state import StateMixin

if TYPE_CHECKING:
    from buildbot.changes.changes import Change
    from buildbot.util.twisted import InlineCallbacksType


class AbsoluteSourceStampsMixin:
    class _CodeBase(TypedDict):
        repository: str
        branch: str | None
        revision: str | None
        lastChange: int | None

    # record changes and revisions per codebase

    _lastCodebases: dict[str, _CodeBase] | None = None
    codebases: dict[str, _CodeBase]

    @defer.inlineCallbacks
    def getCodebaseDict(self, codebase: str) -> InlineCallbacksType[_CodeBase]:
        if self._lastCodebases is None:
            assert isinstance(self, StateMixin)
            self._lastCodebases = yield self.getState('lastCodebases', {})

        # may fail with KeyError
        return self._lastCodebases.get(codebase, self.codebases[codebase])

    @defer.inlineCallbacks
    def recordChange(self, change: Change) -> InlineCallbacksType[None]:
        codebase = yield self.getCodebaseDict(change.codebase)
        lastChange = codebase.get('lastChange', -1)

        if change.number > lastChange:
            assert self._lastCodebases is not None
            self._lastCodebases[change.codebase] = {
                'repository': change.repository,
                'branch': change.branch,
                'revision': change.revision,
                'lastChange': change.number,
            }
            assert isinstance(self, StateMixin)
            yield self.setState('lastCodebases', self._lastCodebases)
