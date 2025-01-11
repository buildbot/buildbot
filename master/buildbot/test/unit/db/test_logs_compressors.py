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

from typing import TYPE_CHECKING

from twisted.trial import unittest

from buildbot.db import compression
from buildbot.db.logs import RawCompressor

if TYPE_CHECKING:
    from typing import ClassVar

    from buildbot.db.compression.protocol import CompressorInterface


class TestRawCompressor(unittest.TestCase):
    # default no-op compressor
    CompressorCls: ClassVar[type[CompressorInterface]] = RawCompressor

    def test_dumps_read(self) -> None:
        if not self.CompressorCls.available:
            raise unittest.SkipTest(f"Compressor '{self.CompressorCls.name}' is unavailable")

        data = b'xy' * 10000
        compressed_data = self.CompressorCls.dumps(data)
        self.assertEqual(data, self.CompressorCls.read(compressed_data))

    def test_compressobj_read(self) -> None:
        if not self.CompressorCls.available:
            raise unittest.SkipTest(f"Compressor '{self.CompressorCls.name}' is unavailable")

        input_buffer = [f'xy{idx}'.encode() * 10000 for idx in range(10)]

        compress_obj = self.CompressorCls.CompressObj()

        def _test() -> None:
            result_buffer = [compress_obj.compress(e) for e in input_buffer]
            result_buffer.append(compress_obj.flush())

            self.assertEqual(
                b''.join(input_buffer), self.CompressorCls.read(b''.join(result_buffer))
            )

        _test()

        # make sure re-using the same compress obj works
        _test()


class TestGZipCompressor(TestRawCompressor):
    CompressorCls = compression.GZipCompressor


class TestBZipCompressor(TestRawCompressor):
    CompressorCls = compression.BZipCompressor


class TestLZ4Compressor(TestRawCompressor):
    CompressorCls = compression.LZ4Compressor


class TestBrotliCompressor(TestRawCompressor):
    CompressorCls = compression.BrotliCompressor


class TestZStdCompressor(TestRawCompressor):
    CompressorCls = compression.ZStdCompressor
