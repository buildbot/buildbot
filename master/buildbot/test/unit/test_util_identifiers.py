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

import locale

from twisted.python import log
from twisted.trial import unittest

from buildbot.util import identifiers


class Tests(unittest.TestCase):

    def test_isIdentifier(self):
        os_encoding = locale.getpreferredencoding()
        try:
            '\N{SNOWMAN}'.encode(os_encoding)
        except UnicodeEncodeError:
            # Default encoding of Windows console is 'cp1252'
            # which cannot encode the snowman.
            raise(unittest.SkipTest("Cannot encode weird unicode "
                "on this platform with {}".format(os_encoding)))

        good = [
            "linux", "Linux", "abc123", "a" * 50, '\N{SNOWMAN}'
        ]
        for g in good:
            log.msg('expect %r to be good' % (g,))
            self.assertTrue(identifiers.isIdentifier(50, g))
        bad = [
            None, '', b'linux', 'a/b', "a.b.c.d",
            "a-b_c.d9", 'spaces not allowed', "a" * 51,
            "123 no initial digits", '\N{SNOWMAN}.\N{SNOWMAN}',
        ]
        for b in bad:
            log.msg('expect %r to be bad' % (b,))
            self.assertFalse(identifiers.isIdentifier(50, b))

    def assertEqualUnicode(self, got, exp):
        self.assertTrue(isinstance(exp, str))
        self.assertEqual(got, exp)

    def test_forceIdentifier_already_is(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(10, 'abc'),
            'abc')

    def test_forceIdentifier_ascii(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(10, 'abc'),
            'abc')

    def test_forceIdentifier_too_long(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(10, 'abcdefghijKL'),
            'abcdefghij')

    def test_forceIdentifier_invalid_chars(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(100, 'my log.html'),
            'my_log_html')

    def test_forceIdentifier_leading_digit(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(100, '9 pictures of cats.html'),
            '__pictures_of_cats_html')

    def test_forceIdentifier_digits(self):
        self.assertEqualUnicode(
            identifiers.forceIdentifier(100, 'warnings(2000)'),
            'warnings_2000_')

    def test_incrementIdentifier_simple(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(100, 'aaa'),
            'aaa_2')

    def test_incrementIdentifier_simple_way_too_long(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(3, 'aaa'),
            'a_2')

    def test_incrementIdentifier_simple_too_long(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(4, 'aaa'),
            'aa_2')

    def test_incrementIdentifier_single_digit(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(100, 'aaa_2'),
            'aaa_3')

    def test_incrementIdentifier_add_digits(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(100, 'aaa_99'),
            'aaa_100')

    def test_incrementIdentifier_add_digits_too_long(self):
        self.assertEqualUnicode(
            identifiers.incrementIdentifier(6, 'aaa_99'),
            'aa_100')

    def test_incrementIdentifier_add_digits_out_of_space(self):
        with self.assertRaises(ValueError):
            identifiers.incrementIdentifier(6, '_99999')
