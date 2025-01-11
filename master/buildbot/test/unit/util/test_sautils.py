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

import hashlib

from twisted.trial import unittest

from buildbot.util import sautils


class TestSaUtils(unittest.TestCase):
    def _sha1(self, s: bytes) -> str:
        return hashlib.sha1(s).hexdigest()

    def test_hash_columns_single(self) -> None:
        self.assertEqual(sautils.hash_columns('master'), self._sha1(b'master'))

    def test_hash_columns_multiple(self) -> None:
        self.assertEqual(sautils.hash_columns('a', None, 'b', 1), self._sha1(b'a\0\xf5\x00b\x001'))

    def test_hash_columns_None(self) -> None:
        self.assertEqual(sautils.hash_columns(None), self._sha1(b'\xf5'))

    def test_hash_columns_integer(self) -> None:
        self.assertEqual(sautils.hash_columns(11), self._sha1(b'11'))
