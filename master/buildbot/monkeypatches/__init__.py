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
import unittest
from typing import Any
from typing import Callable

from twisted.python import util


def onlyOnce(fn: Callable[..., Any]) -> Callable[..., Any]:
    "Set up FN to only run once within an interpreter instance"

    def wrap(*args: Any, **kwargs: Any) -> Any:
        if hasattr(fn, 'called'):
            return None
        fn.called = 1  # type: ignore[attr-defined]
        return fn(*args, **kwargs)

    util.mergeFunctionMetadata(fn, wrap)
    return wrap


# NOTE: all of these patches test for applicability *before* importing the
# patch module.  This will help cut down on unnecessary imports where the
# patches are not needed, and also avoid problems with patches importing
# private things in external libraries that no longer exist.


@onlyOnce
def patch_testcase_timeout() -> None:
    # any test that should take more than 5 second should be annotated so.
    unittest.TestCase.timeout = 5  # type: ignore[attr-defined]

    # but we know that the DB tests are very slow, so we increase a bit that value for
    # real database tests
    if os.environ.get("BUILDBOT_TEST_DB_URL", None) is not None:
        unittest.TestCase.timeout = 120  # type: ignore[attr-defined]


@onlyOnce
def patch_servicechecks() -> None:
    from buildbot.monkeypatches import servicechecks  # noqa: PLC0415

    servicechecks.patch()


@onlyOnce
def patch_decorators() -> None:
    from buildbot.monkeypatches import decorators  # noqa: PLC0415

    decorators.patch()


@onlyOnce
def patch_config_for_unit_tests() -> None:
    from buildbot.config.master import set_is_in_unit_tests  # noqa: PLC0415

    # by default, buildbot.config warns about not configured buildbotNetUsageData.
    # its important for users to not leak information, but unneeded and painful for tests
    set_is_in_unit_tests(True)


@onlyOnce
def patch_twisted_failure() -> None:
    try:
        from twisted import __version__ as twisted_version  # noqa: PLC0415
        from twisted.python.versions import Version  # noqa: PLC0415

        current_version = Version('twisted', *map(int, twisted_version.split('.')[:3]))
        if current_version <= Version('twisted', 24, 7, 0):
            return

        from twisted.spread.pb import CopiedFailure  # noqa: PLC0415

        original_setCopyableState = CopiedFailure.setCopyableState

        def patched_setCopyableState(self: Any, state: dict[str, Any]) -> Any:
            if 'parents' not in state:
                state['parents'] = []
            return original_setCopyableState(self, state)

        CopiedFailure.setCopyableState = patched_setCopyableState  # type: ignore[method-assign]

    except ImportError:
        pass


def patch_all(for_tests: bool = False) -> None:
    if for_tests:
        patch_testcase_timeout()
        patch_config_for_unit_tests()
    patch_servicechecks()
    patch_decorators()
    patch_twisted_failure()
