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

from buildbot.db.compression.protocol import CompressObjInterface
from buildbot.db.compression.protocol import CompressorInterface

try:
    import lz4.block

    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False


class LZ4Compressor(CompressorInterface):
    name = "lz4"
    available = HAS_LZ4

    @staticmethod
    def dumps(data: bytes) -> bytes:
        return lz4.block.compress(data)

    @staticmethod
    def read(data: bytes) -> bytes:
        return lz4.block.decompress(data)

    # LZ4.block does not have a compress object,
    # still implement the interface for compatibility
    class CompressObj(CompressObjInterface):
        def __init__(self) -> None:
            self._buffer: list[bytes] = []

        def compress(self, data: bytes) -> bytes:
            self._buffer.append(data)
            return b''

        def flush(self) -> bytes:
            compressed_buffer = LZ4Compressor.dumps(b''.join(self._buffer))
            self._buffer = []
            return compressed_buffer
