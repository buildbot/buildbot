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

from buildbot.db.compression.protocol import CompressorInterface

try:
    import zstandard

    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False


class ZStdCompressor(CompressorInterface):
    name = "zstd"
    available = HAS_ZSTD

    @staticmethod
    def dumps(data: bytes) -> bytes:
        return zstandard.compress(data, level=9)

    @staticmethod
    def read(data: bytes) -> bytes:
        return zstandard.decompress(data)
