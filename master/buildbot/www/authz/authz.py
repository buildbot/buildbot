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

import fnmatch
import re
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import cast

from twisted.internet import defer
from twisted.web.error import Error
from zope.interface import implementer

from buildbot.interfaces import IConfigured
from buildbot.util import unicode2bytes
from buildbot.www.authz.roles import RolesFromOwner

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class Forbidden(Error):
    def __init__(self, msg: bytes) -> None:
        super().__init__(403, msg)


# fnmatch and re.match are reversed API, we cannot just rename them
def fnmatchStrMatcher(value: str, match: str) -> bool:
    return fnmatch.fnmatch(value, match)


def reStrMatcher(value: str, match: str) -> bool:
    return cast(bool, re.match(match, value))


@implementer(IConfigured)
class Authz:
    def getConfigDict(self) -> dict:
        return {}

    def __init__(
        self,
        allowRules: list[Any] | None = None,
        roleMatchers: list[Any] | None = None,
        stringsMatcher: Callable[[str, str], bool] = fnmatchStrMatcher,
    ) -> None:
        self.match = stringsMatcher
        if allowRules is None:
            allowRules = []
        if roleMatchers is None:
            roleMatchers = []
        self.allowRules = allowRules
        self.roleMatchers = [r for r in roleMatchers if not isinstance(r, RolesFromOwner)]
        self.ownerRoleMatchers = [r for r in roleMatchers if isinstance(r, RolesFromOwner)]

    def setMaster(self, master: Any) -> None:
        self.master = master
        for r in self.roleMatchers + self.ownerRoleMatchers + self.allowRules:
            r.setAuthz(self)

    def getRolesFromUser(self, userDetails: dict[str, Any]) -> set[str]:
        roles = set()
        for roleMatcher in self.roleMatchers:
            roles.update(set(roleMatcher.getRolesFromUser(userDetails)))
        return roles

    def getOwnerRolesFromUser(self, userDetails: dict[str, Any], owner: str | None) -> set[str]:
        roles = set()
        for roleMatcher in self.ownerRoleMatchers:
            roles.update(set(roleMatcher.getRolesFromUser(userDetails, owner)))
        return roles

    @defer.inlineCallbacks
    def assertUserAllowed(
        self, ep: str, action: str, options: dict[str, Any], userDetails: dict[str, Any]
    ) -> InlineCallbacksType[None]:
        roles = self.getRolesFromUser(userDetails)
        for rule in self.allowRules:
            match = yield rule.match(ep, action, options)
            if match is not None:
                # only try to get owner if there are owner Matchers
                if self.ownerRoleMatchers:
                    owner = yield match.getOwner()
                    if owner is not None:
                        roles.update(self.getOwnerRolesFromUser(userDetails, owner))
                for role in roles:
                    if self.match(role, rule.role):
                        return None

                if not rule.defaultDeny:
                    continue  # check next suitable rule if not denied

                error_msg = unicode2bytes(f"you need to have role '{rule.role}'")
                raise Forbidden(error_msg)
        return None
