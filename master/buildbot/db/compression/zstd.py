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
    import zstandard

    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False


class ZStdCompressor(CompressorInterface):
    name = "zstd"
    available = HAS_ZSTD

    COMPRESS_LEVEL = 9

    @staticmethod
    def dumps(data: bytes) -> bytes:
        return zstandard.compress(data, level=ZStdCompressor.COMPRESS_LEVEL)

    @staticmethod
    def read(data: bytes) -> bytes:
        # data compressed with streaming APIs will not
        # contains the content size in it's frame header
        # which is expected by ZstdDecompressor.decompress
        # use ZstdDecompressionObj instead
        # see: https://github.com/indygreg/python-zstandard/issues/150
        decompress_obj = zstandard.ZstdDecompressor().decompressobj()
        return decompress_obj.decompress(data) + decompress_obj.flush()

    class CompressObj(CompressObjInterface):
        def __init__(self) -> None:
            # zstd compressor is safe to re-use
            # Note that it's not thread safe
            self._compressor = zstandard.ZstdCompressor(level=ZStdCompressor.COMPRESS_LEVEL)
            self._create_compressobj()

        def _create_compressobj(self) -> None:
            self._compressobj = self._compressor.compressobj()

        def compress(self, data: bytes) -> bytes:
            return self._compressobj.compress(data)

        def flush(self) -> bytes:
            try:
                return self._compressobj.flush(flush_mode=zstandard.COMPRESSOBJ_FLUSH_FINISH)
            finally:
                # recreate compressobj so this instance can be re-used
                self._create_compressobj()
