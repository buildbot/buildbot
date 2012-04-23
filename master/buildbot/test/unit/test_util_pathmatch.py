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

from twisted.trial import unittest
from buildbot.util import pathmatch

class Matcher(unittest.TestCase):

    def setUp(self):
        self.m = pathmatch.Matcher()

    def test_dupe_path(self):
        def set():
            self.m[('abc,')] = 1
        set()
        self.assertRaises(AssertionError, set)

    def test_empty(self):
        self.assertRaises(KeyError, lambda : self.m[('abc',)])

    def test_diff_length(self):
        self.m[('abc', 'def')] = 2
        self.m[('ab', 'cd', 'ef')] = 3
        self.assertEqual(self.m[('abc', 'def')], (2, {}))

    def test_same_length(self):
        self.m[('abc', 'def')] = 2
        self.m[('abc', 'efg')] = 3
        self.assertEqual(self.m[('abc', 'efg')], (3, {}))

    def test_pattern_variables(self):
        self.m[('A', ':a', 'B', ':b')] = 'AB'
        self.assertEqual(self.m[('A', 'a', 'B', 'b')],
                ('AB', dict(a='a', b='b')))

    def test_pattern_variables_int(self):
        self.m[('A', 'i:a', 'B', 'i:b')] = 'AB'
        self.assertEqual(self.m[('A', '10', 'B', '-20')],
                ('AB', dict(a=10, b=-20)))

    def test_pattern_variables_int_invalid(self):
        self.m[('A', 'i:a')] = 'AB'
        self.assertRaises(KeyError, lambda : self.m[('A', '1x0')])

    def test_prefix_matching(self):
        self.m[('A', ':a')] = 'A'
        self.m[('A', ':a', 'B', ':b')] = 'AB'
        self.assertEqual(
           (self.m[('A', 'a1', 'B', 'b')], self.m['A', 'a2']),
           (('AB', dict(a='a1', b='b')), ('A', dict(a='a2'))))

    def test_dirty_again(self):
        self.m[('abc', 'def')] = 2
        self.assertEqual(self.m[('abc', 'def')], (2, {}))
        self.m[('abc', 'efg')] = 3
        self.assertEqual(self.m[('abc', 'def')], (2, {}))
        self.assertEqual(self.m[('abc', 'efg')], (3, {}))
