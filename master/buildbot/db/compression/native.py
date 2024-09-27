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

import bz2
import zlib

from buildbot.db.compression.protocol import CompressorInterface


class GZipCompressor(CompressorInterface):
    name = "gz"

    @staticmethod
    def dumps(data: bytes) -> bytes:
        return zlib.compress(data, 9)

    @staticmethod
    def read(data: bytes) -> bytes:
        return zlib.decompress(data)


class BZipCompressor(CompressorInterface):
    name = "bz2"

    @staticmethod
    def dumps(data: bytes) -> bytes:
        return bz2.compress(data, 9)

    @staticmethod
    def read(data: bytes) -> bytes:
        return bz2.decompress(data)
