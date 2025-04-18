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

from typing import Any


class RolesFromBase:
    def __init__(self) -> None:
        pass

    def getRolesFromUser(self, userDetails: dict[str, Any]) -> list[str]:
        return []

    def setAuthz(self, authz: Any) -> None:
        self.authz = authz
        self.master = authz.master


class RolesFromGroups(RolesFromBase):
    def __init__(self, groupPrefix: str = "") -> None:
        super().__init__()
        self.groupPrefix = groupPrefix

    def getRolesFromUser(self, userDetails: dict[str, Any]) -> list[str]:
        roles = []
        if 'groups' in userDetails:
            for group in userDetails['groups']:
                if group.startswith(self.groupPrefix):
                    roles.append(group[len(self.groupPrefix) :])
        return roles


class RolesFromEmails(RolesFromBase):
    def __init__(self, **kwargs: list[str]) -> None:
        super().__init__()
        self.roles: dict[str, list[str]] = {}
        for role, emails in kwargs.items():
            for email in emails:
                self.roles.setdefault(email, []).append(role)

    def getRolesFromUser(self, userDetails: dict[str, Any]) -> list[str]:
        if 'email' in userDetails:
            return self.roles.get(userDetails['email'], [])
        return []


class RolesFromDomain(RolesFromEmails):
    def __init__(self, **kwargs: list[str]) -> None:
        super().__init__()

        self.domain_roles: dict[str, list[str]] = {}
        for role, domains in kwargs.items():
            for domain in domains:
                self.domain_roles.setdefault(domain, []).append(role)

    def getRolesFromUser(self, userDetails: dict[str, Any]) -> list[str]:
        if 'email' in userDetails:
            email = userDetails['email']
            edomain = email.split('@')[-1]
            return self.domain_roles.get(edomain, [])
        return []


class RolesFromOwner(RolesFromBase):
    def __init__(self, role: str) -> None:
        super().__init__()
        self.role = role

    def getRolesFromUser(self, userDetails: dict[str, Any], owner: str | None = None) -> list[str]:  # type: ignore[override]
        if 'email' in userDetails:
            if userDetails['email'] == owner and owner is not None:
                return [self.role]
        return []


class RolesFromUsername(RolesFromBase):
    def __init__(self, roles: list[str], usernames: list[str]) -> None:
        self.roles = roles
        if None in usernames:
            from buildbot import config

            config.error('Usernames cannot be None')
        self.usernames = usernames

    def getRolesFromUser(self, userDetails: dict[str, Any]) -> list[str]:
        if userDetails.get('username') in self.usernames:
            return self.roles
        return []
