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

import contextlib
import os
from threading import Lock
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

from buildbot.db.compression.protocol import CompressObjInterface
from buildbot.db.compression.protocol import CompressorInterface

if TYPE_CHECKING:
    from typing import Callable
    from typing import ClassVar
    from typing import Generator


_T = TypeVar('_T')

try:
    import zstandard

    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False


class _Pool(Generic[_T]):
    """zstandard ZstdCompressor/ZstdDecompressor are provide better performance when re-used, but are not thread-safe"""

    def __init__(self, item_ctor: Callable[[], _T], max_size: int | None = None) -> None:
        if max_size is None:
            max_size = 1
            if cpu_count := os.cpu_count():
                max_size = max(cpu_count, max_size)

        self._item_ctor = item_ctor
        self._pool: list[_T] = []
        self._lock = Lock()
        self.max_size = max_size

    def acquire(self) -> _T:
        with self._lock:
            if self._pool:
                return self._pool.pop(-1)
            # pool is empty, create a new object
            return self._item_ctor()

    def release(self, item: _T) -> None:
        with self._lock:
            if len(self._pool) < self.max_size:
                self._pool.append(item)

    @contextlib.contextmanager
    def item(self) -> Generator[_T, None, None]:
        item = self.acquire()
        try:
            yield item
        finally:
            self.release(item)

    def set_max_size(self, new_size: int) -> None:
        with self._lock:
            if len(self._pool) > new_size:
                self._pool = self._pool[:new_size]
            self.max_size = new_size


class ZStdCompressor(CompressorInterface):
    name = "zstd"
    available = HAS_ZSTD

    COMPRESS_LEVEL = 9

    if HAS_ZSTD:
        _compressor_pool: ClassVar[_Pool[zstandard.ZstdCompressor]] = _Pool(
            lambda: zstandard.ZstdCompressor(level=ZStdCompressor.COMPRESS_LEVEL)
        )
        _decompressor_pool: ClassVar[_Pool[zstandard.ZstdDecompressor]] = _Pool(
            zstandard.ZstdDecompressor
        )

    @classmethod
    def set_pools_max_size(cls, new_size: int) -> None:
        cls._compressor_pool.set_max_size(new_size)
        cls._decompressor_pool.set_max_size(new_size)

    @classmethod
    def dumps(cls, data: bytes) -> bytes:
        with cls._compressor_pool.item() as compressor:
            return compressor.compress(data)

    @classmethod
    def read(cls, data: bytes) -> bytes:
        # data compressed with streaming APIs will not
        # contains the content size in it's frame header
        # which is expected by ZstdDecompressor.decompress
        # use ZstdDecompressionObj instead
        # see: https://github.com/indygreg/python-zstandard/issues/150
        with cls._decompressor_pool.item() as decompressor:
            decompress_obj = decompressor.decompressobj()
            return decompress_obj.decompress(data) + decompress_obj.flush()

    class CompressObj(CompressObjInterface):
        def __init__(self) -> None:
            # zstd compressor is safe to re-use
            # Note that it's not thread safe
            self._compressor: zstandard.ZstdCompressor | None = None
            self._compressobj: zstandard.ZstdCompressionObj | None = None

        def compress(self, data: bytes) -> bytes:
            if self._compressor is None:
                self._compressor = ZStdCompressor._compressor_pool.acquire()
                self._compressobj = self._compressor.compressobj()
            else:
                assert self._compressobj is not None, (
                    "Programming error: _compressobj is None when _compressor is not"
                )

            return self._compressobj.compress(data)

        def flush(self) -> bytes:
            assert self._compressor is not None, (
                "Programming error: Flush called without previous compress"
            )
            assert self._compressobj is not None, (
                "Programming error: _compressobj is None when _compressor is not"
            )

            try:
                return self._compressobj.flush(flush_mode=zstandard.COMPRESSOBJ_FLUSH_FINISH)
            finally:
                # release _compressobj as it's not re-usable
                self._compressobj = None
                # return instance of compressor to pool
                compressor = self._compressor
                self._compressor = None
                ZStdCompressor._compressor_pool.release(compressor)
