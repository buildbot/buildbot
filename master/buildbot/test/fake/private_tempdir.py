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

import os
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from types import TracebackType


class FakePrivateTemporaryDirectory:
    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
        mode: int = 0o700,
    ) -> None:
        dir = dir or '/'
        prefix = prefix or ''
        suffix = suffix or ''

        self.name = os.path.join(dir, prefix + '@@@' + suffix)
        self.mode = mode

    def __enter__(self) -> str:
        return self.name

    def __exit__(
        self,
        exc: type[BaseException] | None,
        value: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass

    def cleanup(self) -> None:
        pass


class MockPrivateTemporaryDirectory:
    def __init__(self) -> None:
        self.dirs: list[tuple[str, int]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> FakePrivateTemporaryDirectory:
        ret = FakePrivateTemporaryDirectory(*args, **kwargs)
        self.dirs.append((ret.name, ret.mode))
        return ret
