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

from buildbot_worker import monkeypatches

# apply the same patches the worker does when it starts
monkeypatches.patch_all()


def add_debugging_monkeypatches() -> None:
    """
    DO NOT CALL THIS DIRECTLY

    This adds a few "harmless" monkeypatches which make it easier to debug
    failing tests.
    """
    from twisted.application.service import Service

    old_startService = Service.startService
    old_stopService = Service.stopService

    def startService(self: Service) -> None:
        assert not self.running
        return old_startService(self)

    def stopService(self: Service) -> None:
        assert self.running
        return old_stopService(self)

    Service.startService = startService  # type: ignore[method-assign]
    Service.stopService = stopService  # type: ignore[method-assign]


add_debugging_monkeypatches()

__all__: list[Any] = []

# import mock so we bail out early if it's not installed
try:
    from unittest import mock

    _ = mock
except ImportError:
    try:
        from unittest import mock
    except ImportError as e:
        raise ImportError("Buildbot tests require the 'mock' module; try 'pip install mock'") from e
