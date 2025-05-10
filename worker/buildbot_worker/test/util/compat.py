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

# This module is left for backward compatibility of old-named worker API.
# It should never be imported by Buildbot.
from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.python import runtime

if TYPE_CHECKING:
    from typing import Callable
    from typing import Literal
    from typing import TypeVar

    _T = TypeVar('_T')


def skipUnlessPlatformIs(platform: Literal["posix", "win32"]) -> Callable[[_T], _T]:
    def closure(test: _T) -> _T:
        if runtime.platformType != platform:
            test.skip = f"not a {platform} platform"  # type: ignore[attr-defined]
        return test

    return closure
