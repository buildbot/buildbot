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

from buildbot import util


class ComparableMixin(unittest.TestCase):

    class Foo(util.ComparableMixin):
        compare_attrs = ("a", "b")

        def __init__(self, a, b, c):
            self.a, self.b, self.c = a, b, c

    class Bar(Foo, util.ComparableMixin):
        compare_attrs = ("b", "c")

    def setUp(self):
        self.f123 = self.Foo(1, 2, 3)
        self.f124 = self.Foo(1, 2, 4)
        self.f134 = self.Foo(1, 3, 4)
        self.b123 = self.Bar(1, 2, 3)
        self.b223 = self.Bar(2, 2, 3)
        self.b213 = self.Bar(2, 1, 3)

    def test_equality_identity(self):
        self.assertEqual(self.f123, self.f123)

    def test_equality_same(self):
        another_f123 = self.Foo(1, 2, 3)
        self.assertEqual(self.f123, another_f123)

    def test_equality_unimportantDifferences(self):
        self.assertEqual(self.f123, self.f124)

    def test_inequality_unimportantDifferences_subclass(self):
        # verify that the parent class's compare_attrs does
        # affect the subclass
        self.assertNotEqual(self.b123, self.b223)

    def test_inequality_importantDifferences(self):
        self.assertNotEqual(self.f123, self.f134)

    def test_inequality_importantDifferences_subclass(self):
        self.assertNotEqual(self.b123, self.b213)

    def test_inequality_differentClasses(self):
        self.assertNotEqual(self.f123, self.b123)

    def test_instance_attribute_not_used(self):
        # setting compare_attrs as an instance method doesn't
        # affect the outcome of the comparison
        another_f123 = self.Foo(1, 2, 3)
        another_f123.compare_attrs = ("b", "a")
        self.assertEqual(self.f123, another_f123)

    def test_ne_importantDifferences(self):
        self.assertNotEqual(self.f123, self.f134)

    def test_ne_differentClasses(self):
        self.assertNotEqual(self.f123, self.b123)

    def test_compare(self):
        self.assertEqual(self.f123, self.f123)
        self.assertNotEqual(self.b223, self.b213)
        self.assertGreater(self.b223, self.b213)

        # Different classes
        self.assertFalse(self.b223 > self.f123)

        self.assertGreaterEqual(self.b223, self.b213)
        self.assertGreaterEqual(self.b223, self.b223)

        # Different classes
        self.assertFalse(self.f123 >= self.b123)

        self.assertLess(self.b213, self.b223)
        self.assertLessEqual(self.b213, self.b223)
        self.assertLessEqual(self.b213, self.b213)

        # Different classes
        self.assertFalse(self.f123 <= self.b123)
