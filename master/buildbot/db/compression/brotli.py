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
    import brotli

    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False


class BrotliCompressor(CompressorInterface):
    name = "br"
    available = HAS_BROTLI

    @staticmethod
    def dumps(data: bytes) -> bytes:
        return brotli.compress(data, mode=brotli.MODE_TEXT, quality=11)

    @staticmethod
    def read(data: bytes) -> bytes:
        return brotli.decompress(data)
