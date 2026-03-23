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

from twisted.trial import unittest

from buildbot.test.util import interfaces


class TestAssertArgSpecMatches(interfaces.InterfaceTests, unittest.TestCase):
    def test_simple_decorator(self) -> None:
        def myfunc(x: object, y: int = 2, *args: object) -> None:
            pass

        @self.assertArgSpecMatches(myfunc)
        def myfunc2(x: object, y: int = 2, *args: object) -> None:
            pass

        error: Exception | None
        try:

            @self.assertArgSpecMatches(myfunc)
            def myfunc3(x: object, y: int = 3, *args: object) -> None:
                pass

        except Exception as e:
            error = e
        else:
            error = None

        self.assertIdentical(type(error), unittest.FailTest)
        self.assertEqual(error.args, ('Expected: (x, y=3, *args); got: (x, y=2, *args)',))  # type: ignore[union-attr]

    def test_double_decorator(self) -> None:
        def myfunc(x: object, y: object) -> None:
            pass

        def myfunc2(x: object, y: object) -> None:
            pass

        def myfunc3(x: object, yy: object) -> None:
            pass

        @self.assertArgSpecMatches(myfunc, myfunc2)
        def myfunc4(x: object, y: object) -> None:
            pass

        error: Exception | None
        try:

            @self.assertArgSpecMatches(myfunc, myfunc3)
            def myfunc5(x: object, y: object) -> None:
                pass

        except Exception as e:
            error = e
        else:
            error = None

        self.assertIdentical(type(error), unittest.FailTest)
        self.assertEqual(error.args, ('Expected: (x, y); got: (x, yy)',))  # type: ignore[union-attr]

        error = None
        try:

            @self.assertArgSpecMatches(myfunc, myfunc3)
            def myfunc6(xx: object, yy: object) -> None:
                pass

        except Exception as e:
            error = e
        else:
            error = None

        self.assertIdentical(type(error), unittest.FailTest)
        self.assertEqual(error.args, ('Expected: (x, y); got: (x, yy)',))  # type: ignore[union-attr]

    def test_function_style(self) -> None:
        def myfunc(x: object, y: int = 2, *args: object) -> None:
            pass

        def myfunc2(x: object, y: int = 2, *args: object) -> None:
            pass

        def myfunc3(x: object, y: int = 3, *args: object) -> None:
            pass

        self.assertArgSpecMatches(myfunc, myfunc2)

        error: Exception | None
        try:
            self.assertArgSpecMatches(myfunc, myfunc3)
        except Exception as e:
            error = e
        else:
            error = None

        self.assertIdentical(type(error), unittest.FailTest)
        self.assertEqual(error.args, ('Expected: (x, y=2, *args); got: (x, y=3, *args)',))  # type: ignore[union-attr]
