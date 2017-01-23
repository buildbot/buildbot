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

from __future__ import absolute_import
from __future__ import print_function

from twisted.trial import unittest

from buildbot.test.util import interfaces


class TestAssertArgSpecMatches(interfaces.InterfaceTests, unittest.TestCase):

    def test_simple_decorator(self):
        def myfunc(x, y=2, *args):
            pass

        @self.assertArgSpecMatches(myfunc)
        def myfunc2(x, y=2, *args):
            pass

        try:
            @self.assertArgSpecMatches(myfunc)
            def myfunc3(x, y=3, *args):
                pass
        except Exception as e:
            error = e
        else:
            error = None

        self.assertIdentical(type(error), unittest.FailTest)
        self.assertEqual(
            error.args, ('Expected: (x, y=3, *args); got: (x, y=2, *args)',))

    def test_double_decorator(self):
        def myfunc(x, y):
            pass

        def myfunc2(x, y):
            pass

        def myfunc3(x, yy):
            pass

        @self.assertArgSpecMatches(myfunc, myfunc2)
        def myfunc4(x, y):
            pass

        try:
            @self.assertArgSpecMatches(myfunc, myfunc3)
            def myfunc5(x, y):
                pass
        except Exception as e:
            error = e
        else:
            error = None

        self.assertIdentical(type(error), unittest.FailTest)
        self.assertEqual(error.args, ('Expected: (x, y); got: (x, yy)',))

        try:
            @self.assertArgSpecMatches(myfunc, myfunc3)
            def myfunc6(xx, yy):
                pass
        except Exception as e:
            error = e
        else:
            error = None

        self.assertIdentical(type(error), unittest.FailTest)
        self.assertEqual(error.args, ('Expected: (x, y); got: (x, yy)',))

    def test_function_style(self):
        def myfunc(x, y=2, *args):
            pass

        def myfunc2(x, y=2, *args):
            pass

        def myfunc3(x, y=3, *args):
            pass

        self.assertArgSpecMatches(myfunc, myfunc2)

        try:
            self.assertArgSpecMatches(myfunc, myfunc3)
        except Exception as e:
            error = e
        else:
            error = None

        self.assertIdentical(type(error), unittest.FailTest)
        self.assertEqual(
            error.args, ('Expected: (x, y=2, *args); got: (x, y=3, *args)',))
