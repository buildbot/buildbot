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
from unittest import mock

from twisted.internet import defer

if TYPE_CHECKING:
    from twisted.trial import unittest

    _PBManagerMixinBase = unittest.TestCase
else:
    _PBManagerMixinBase = object


class PBManagerMixin(_PBManagerMixinBase):
    def setUpPBChangeSource(self) -> None:
        "Set up a fake self.pbmanager."
        self.registrations: list[tuple[str, str, str]] = []
        self.unregistrations: list[tuple[str, str, str]] = []
        pbm = self.pbmanager = mock.Mock()
        pbm.register = self._fake_register

    def _fake_register(self, portstr: str, username: str, password: str, factory: Any) -> mock.Mock:
        reg = mock.Mock()

        def unregister() -> defer.Deferred[None]:
            self.unregistrations.append((portstr, username, password))
            return defer.succeed(None)

        reg.unregister = unregister
        self.registrations.append((portstr, username, password))
        return reg

    def assertNotRegistered(self) -> None:
        self.assertEqual(self.registrations, [])

    def assertNotUnregistered(self) -> None:
        self.assertEqual(self.unregistrations, [])

    def assertRegistered(self, portstr: str, username: str, password: str) -> None:
        for ps, un, pw in self.registrations:
            if ps == portstr and username == un and pw == password:
                return
        self.fail(f"not registered: {(portstr, username, password)!r} not in {self.registrations}")

    def assertUnregistered(self, portstr: str, username: str, password: str) -> None:
        for ps, un, pw in self.unregistrations:
            if ps == portstr and username == un and pw == password:
                return
        self.fail("still registered")
