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

from buildbot.util.indent import indent


class IndentTest(unittest.TestCase):

    def test_basic(self):
        # Add prefix to all strings.
        self.assertEqual(indent("abc\ndef", "->"), "->abc\n->def")
        self.assertEqual(indent("abc\ndef\n", "->"), "->abc\n->def\n")
        # Empty lines and lines solely consisting of spaces are not indented.
        self.assertEqual(indent("abc\n\ndef", "->"), "->abc\n\n->def")
        self.assertEqual(indent("abc\n   \ndef", "->"), "->abc\n   \n->def")
        # Custom predicate for selecting which lines to indent.
        self.assertEqual(
            indent("abc\n***\ndef", "->", lambda s: not s.startswith("*")),
            "->abc\n***\n->def")
