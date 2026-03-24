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
from typing import overload

from buildbot import config

if TYPE_CHECKING:
    import re
    from types import TracebackType

    from twisted.trial import unittest

    _ConfigErrorsMixinBase = unittest.TestCase
else:
    _ConfigErrorsMixinBase = object


class _AssertRaisesConfigErrorContext:
    def __init__(self, substr_or_re: str | re.Pattern[str], case: Any) -> None:
        self.substr_or_re = substr_or_re
        self.case = case

    def __enter__(self) -> _AssertRaisesConfigErrorContext:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc_type is None:
            self.case.fail("ConfigErrors not raised")

        if not issubclass(exc_type, config.ConfigErrors):  # type: ignore[arg-type]
            self.case.fail(f"ConfigErrors not raised, instead got {exc_type.__name__}")  # type: ignore[union-attr]

        self.case.assertConfigError(exc_value, self.substr_or_re)
        return True


class ConfigErrorsMixin(_ConfigErrorsMixinBase):
    def assertConfigError(
        self, errors: config.ConfigErrors, substr_or_re: str | re.Pattern[str]
    ) -> None:
        if len(errors.errors) > 1:
            self.fail(f"too many errors: {errors.errors}")
        elif not errors.errors:
            self.fail("expected error did not occur")
        else:
            curr_error = errors.errors[0]
            if isinstance(substr_or_re, str):
                if substr_or_re not in curr_error:
                    self.fail(f"non-matching error: {curr_error}, expected: {substr_or_re}")
            else:
                if not substr_or_re.search(curr_error):
                    self.fail(f"non-matching error: {curr_error}")

    @overload
    def assertRaisesConfigError(
        self, substr_or_re: str | re.Pattern[str]
    ) -> _AssertRaisesConfigErrorContext: ...

    @overload
    def assertRaisesConfigError(self, substr_or_re: str | re.Pattern[str], fn: Any) -> None: ...

    def assertRaisesConfigError(
        self, substr_or_re: str | re.Pattern[str], fn: Any = None
    ) -> _AssertRaisesConfigErrorContext | None:
        context = _AssertRaisesConfigErrorContext(substr_or_re, self)
        if fn is None:
            return context
        with context:
            fn()
        return None

    def assertNoConfigErrors(self, errors: config.ConfigErrors) -> None:
        self.assertEqual(errors.errors, [])
