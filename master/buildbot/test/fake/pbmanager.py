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

from twisted.internet import defer

from buildbot.util import service


class FakePBManager(service.AsyncMultiService):
    def __init__(self) -> None:
        super().__init__()
        self.setName("fake-pbmanager")
        self._registrations: list[tuple[str, str, str]] = []
        self._unregistrations: list[tuple[str, str]] = []

    def register(
        self, portstr: str, username: str, password: str, pfactory: Any
    ) -> defer.Deferred[FakeRegistration]:
        if (portstr, username) not in self._registrations:
            reg = FakeRegistration(self, portstr, username)
            self._registrations.append((portstr, username, password))
            return defer.succeed(reg)
        else:
            raise KeyError(f"username '{username}' is already registered on port {portstr}")

    def _unregister(self, portstr: str, username: str) -> defer.Deferred[None]:
        self._unregistrations.append((portstr, username))
        return defer.succeed(None)


class FakeRegistration:
    def __init__(self, pbmanager: FakePBManager, portstr: str, username: str) -> None:
        self._portstr = portstr
        self._username = username
        self._pbmanager = pbmanager

    def unregister(self) -> defer.Deferred[None]:
        return self._pbmanager._unregister(self._portstr, self._username)
