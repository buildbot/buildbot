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
    import brotli

    MODE_TEXT = brotli.MODE_TEXT

    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False
    MODE_TEXT = None


class BrotliCompressor(CompressorInterface):
    name = "br"
    available = HAS_BROTLI

    COMPRESS_QUALITY = 11
    MODE = MODE_TEXT

    @staticmethod
    def dumps(data: bytes) -> bytes:
        return brotli.compress(
            data,
            mode=BrotliCompressor.MODE,
            quality=BrotliCompressor.COMPRESS_QUALITY,
        )

    @staticmethod
    def read(data: bytes) -> bytes:
        return brotli.decompress(data)

    class CompressObj(CompressObjInterface):
        def __init__(self) -> None:
            self._create_compressobj()

        def _create_compressobj(self) -> None:
            self._compressobj = brotli.Compressor(
                mode=BrotliCompressor.MODE,
                quality=BrotliCompressor.COMPRESS_QUALITY,
            )

        def compress(self, data: bytes) -> bytes:
            return self._compressobj.process(data)

        def flush(self) -> bytes:
            try:
                return self._compressobj.finish()
            finally:
                # recreate compressobj so this instance can be re-used
                self._create_compressobj()
