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

import re

from twisted.web import iweb
from zope.interface import implementer

try:
    import brotli
except ImportError:
    brotli = None

try:
    import zstandard
except ImportError:
    zstandard = None  # type: ignore[assignment]


@implementer(iweb._IRequestEncoderFactory)
class _EncoderFactoryBase:
    def __init__(
        self, encoding_type: bytes, encoder_class: type[iweb._IRequestEncoder] | None
    ) -> None:
        self.encoding_type = encoding_type
        self.encoder_class = encoder_class
        self.check_regex = re.compile(rb"(:?^|[\s,])" + encoding_type + rb"(:?$|[\s,])")

    def encoderForRequest(self, request):
        """
        Check the headers if the client accepts encoding, and encodes the
        request if so.
        """
        if self.encoder_class is None:
            return None

        acceptHeaders = b",".join(request.requestHeaders.getRawHeaders(b"accept-encoding", []))
        if self.check_regex.search(acceptHeaders):
            encoding = request.responseHeaders.getRawHeaders(b"content-encoding")
            if encoding:
                encoding = b",".join([*encoding, self.encoding_type])
            else:
                encoding = self.encoding_type

            request.responseHeaders.setRawHeaders(b"content-encoding", [encoding])
            return self.encoder_class(request)
        return None


class BrotliEncoderFactory(_EncoderFactoryBase):
    def __init__(self) -> None:
        super().__init__(b'br', _BrotliEncoder if brotli is not None else None)


class ZstandardEncoderFactory(_EncoderFactoryBase):
    def __init__(self) -> None:
        super().__init__(b'zstd', _ZstdEncoder if zstandard is not None else None)


@implementer(iweb._IRequestEncoder)
class _EncoderBase:
    def __init__(self, request) -> None:
        self._request = request

    def _compress(self, data: bytes) -> bytes:
        return data

    def _flush(self) -> bytes:
        return b''

    def encode(self, data):
        """
        Write to the request, automatically compressing data on the fly.
        """
        if not self._request.startedWriting:
            # Remove the content-length header, we can't honor it
            # because we compress on the fly.
            self._request.responseHeaders.removeHeader(b"content-length")
        return self._compress(data)

    def finish(self):
        """
        Finish handling the request request, flushing any data from the buffer.
        """
        return self._flush()


class _BrotliEncoder(_EncoderBase):
    def __init__(self, request):
        super().__init__(request)
        self._compressor = brotli.Compressor() if brotli is not None else None

    def _compress(self, data: bytes) -> bytes:
        if self._compressor is not None:
            return self._compressor.process(data)
        return data

    def _flush(self) -> bytes:
        if self._compressor is not None:
            data = self._compressor.finish()
            self._compressor = None
            return data
        return b''


class _ZstdEncoder(_EncoderBase):
    def __init__(self, request):
        super().__init__(request)
        self._compressor = (
            zstandard.ZstdCompressor(write_content_size=True) if zstandard is not None else None
        )
        self._compressobj = self._compressor.compressobj() if zstandard is not None else None

    def _compress(self, data: bytes) -> bytes:
        if self._compressor is not None:
            return self._compressobj.compress(data)
        return data

    def _flush(self) -> bytes:
        if self._compressor is not None:
            c_data = self._compressobj.flush()
            self._compressor = None
            self._compressobj = None
            return c_data
        return b''
