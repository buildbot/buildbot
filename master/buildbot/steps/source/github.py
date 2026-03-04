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

from buildbot.steps.source.git import Git

if TYPE_CHECKING:
    from twisted.internet import defer


class GitHub(Git):
    def run_vc(self, branch: str | None, revision: str | None, patch: Any) -> defer.Deferred[int]:
        # ignore the revision if the branch ends with /merge
        if branch.endswith("/merge"):  # type: ignore[union-attr]
            revision = None
        return super().run_vc(branch, revision, patch)
