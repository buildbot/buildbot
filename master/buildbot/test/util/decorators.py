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
"""
Various decorators for test cases
"""

from __future__ import annotations

import os
import sys
from typing import Any
from typing import Callable
from typing import TypeVar

from twisted.python import runtime

_FLAKY_ENV_VAR = 'RUN_FLAKY_TESTS'
_F = TypeVar('_F', bound=Callable[..., Any])


def todo(message: str) -> Callable[[_F], _F]:
    """
    decorator to mark a todo test
    """

    def wrap(func: _F) -> _F:
        """
        just mark the test
        """
        func.todo = message  # type: ignore[attr-defined]
        return func

    return wrap


def flaky(
    bugNumber: int | None = None, issueNumber: int | None = None, onPlatform: str | None = None
) -> Callable[[_F], _F]:
    def wrap(fn: _F) -> _F:
        if onPlatform is not None and sys.platform != onPlatform:
            return fn

        if os.environ.get(_FLAKY_ENV_VAR):
            return fn

        if bugNumber is not None:
            fn.skip = (  # type: ignore[attr-defined]
                f"Flaky test (http://trac.buildbot.net/ticket/{bugNumber}) "
                f"- set ${_FLAKY_ENV_VAR} to run anyway"
            )
        if issueNumber is not None:
            fn.skip = (  # type: ignore[attr-defined]
                f"Flaky test (https://github.com/buildbot/buildbot/issues/{issueNumber}) "
                f"- set ${_FLAKY_ENV_VAR} to run anyway"
            )
        return fn

    return wrap


def skipUnlessPlatformIs(platform: str) -> Callable[[_F], _F]:
    def closure(test: _F) -> _F:
        if runtime.platformType != platform:
            test.skip = f"not a {platform} platform"  # type: ignore[attr-defined]
        return test

    return closure


def skipIfPythonVersionIsLess(min_version_info: tuple[int, ...]) -> Callable[[_F], _F]:
    assert isinstance(min_version_info, tuple)

    def closure(test: _F) -> _F:
        if sys.version_info < min_version_info:
            test.skip = f"requires Python >= {min_version_info}"  # type: ignore[attr-defined]
        return test

    return closure
