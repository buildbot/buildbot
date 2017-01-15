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

from twisted.protocols import basic
from twisted.trial import unittest

from buildbot.util import netstrings


class NetstringParser(unittest.TestCase):

    def test_valid_netstrings(self):
        p = netstrings.NetstringParser()
        p.feed("5:hello,5:world,")
        self.assertEqual(p.strings, [b'hello', b'world'])

    def test_valid_netstrings_byte_by_byte(self):
        # (this is really testing twisted's support, but oh well)
        p = netstrings.NetstringParser()
        [p.feed(c) for c in "5:hello,5:world,"]
        self.assertEqual(p.strings, [b'hello', b'world'])

    def test_invalid_netstring(self):
        p = netstrings.NetstringParser()
        self.assertRaises(basic.NetstringParseError,
                          lambda: p.feed("5-hello!"))

    def test_incomplete_netstring(self):
        p = netstrings.NetstringParser()
        p.feed("11:hello world,6:foob")
        # note that the incomplete 'foobar' does not appear here
        self.assertEqual(p.strings, [b'hello world'])
