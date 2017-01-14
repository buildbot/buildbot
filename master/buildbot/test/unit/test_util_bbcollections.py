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

from buildbot.util import bbcollections


class KeyedSets(unittest.TestCase):

    def setUp(self):
        self.ks = bbcollections.KeyedSets()

    def test_getitem_default(self):
        self.assertEqual(self.ks['x'], set())
        # remaining tests effectively cover __getitem__

    def test_add(self):
        self.ks.add('y', 2)
        self.assertEqual(self.ks['y'], set([2]))

    def test_add_twice(self):
        self.ks.add('z', 2)
        self.ks.add('z', 4)
        self.assertEqual(self.ks['z'], set([2, 4]))

    def test_discard_noError(self):
        self.ks.add('full', 12)
        self.ks.discard('empty', 13)  # should not fail
        self.ks.discard('full', 13)  # nor this
        self.assertEqual(self.ks['full'], set([12]))

    def test_discard_existing(self):
        self.ks.add('yarn', 'red')
        self.ks.discard('yarn', 'red')
        self.assertEqual(self.ks['yarn'], set([]))

    def test_contains_true(self):
        self.ks.add('yarn', 'red')
        self.assertTrue('yarn' in self.ks)

    def test_contains_false(self):
        self.assertFalse('yarn' in self.ks)

    def test_contains_setNamesNotContents(self):
        self.ks.add('yarn', 'red')
        self.assertFalse('red' in self.ks)

    def test_pop_exists(self):
        self.ks.add('names', 'pop')
        self.ks.add('names', 'coke')
        self.ks.add('names', 'soda')
        popped = self.ks.pop('names')
        remaining = self.ks['names']
        self.assertEqual((popped, remaining),
                         (set(['pop', 'coke', 'soda']), set()))

    def test_pop_missing(self):
        self.assertEqual(self.ks.pop('flavors'), set())
