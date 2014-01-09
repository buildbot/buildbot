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

from buildbot.util import identifiers
from twisted.python import log
from twisted.trial import unittest


class Tests(unittest.TestCase):

    def test_isIdentifier(self):
        good = [
            u"linux", u"Linux", u"abc123", u"a" * 50,
        ]
        for g in good:
            log.msg('expect %r to be good' % (g,))
            self.assertTrue(identifiers.isIdentifier(50, g))
        bad = [
            None, u'', 'linux', u'a/b', u'\N{SNOWMAN}', u"a.b.c.d",
            u"a-b_c.d9", 'spaces not allowed', u"a" * 51,
            u"123 no initial digits",
        ]
        for b in bad:
            log.msg('expect %r to be bad' % (b,))
            self.assertFalse(identifiers.isIdentifier(50, b))

    def assertEqualUnicode(self, got, exp):
        self.failUnless(isinstance(exp, unicode))
        self.assertEqual(got, exp)

    def test_forceIdentifier_already_is(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(10, u'abc'),
            u'abc')

    def test_forceIdentifier_ascii(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(10, 'abc'),
            u'abc')

    def test_forceIdentifier_too_long(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(10, 'abcdefghijKL'),
            u'abcdefghij')

    def test_forceIdentifier_invalid_chars(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(100, 'my log.html'),
            u'my_log_html')

    def test_forceIdentifier_leading_digit(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(100, '9 pictures of cats.html'),
            u'__pictures_of_cats_html')

    def test_incrementIdentifier_simple(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(100, u'aaa'),
            u'aaa_2')

    def test_incrementIdentifier_simple_way_too_long(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(3, u'aaa'),
            u'a_2')

    def test_incrementIdentifier_simple_too_long(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(4, u'aaa'),
            u'aa_2')

    def test_incrementIdentifier_single_digit(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(100, u'aaa_2'),
            u'aaa_3')

    def test_incrementIdentifier_add_digits(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(100, u'aaa_99'),
            u'aaa_100')

    def test_incrementIdentifier_add_digits_too_long(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(6, u'aaa_99'),
            u'aa_100')

    def test_incrementIdentifier_add_digits_out_of_space(self):
        self.assertRaises(ValueError, lambda:
                          identifiers.incrementIdentifier(6, u'_99999'))
