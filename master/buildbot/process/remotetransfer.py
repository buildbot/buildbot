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

"""
module for regrouping all FileWriterImpl and FileReaderImpl away from steps
"""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
from codecs import getincrementaldecoder
from io import BytesIO
from typing import IO
from typing import Literal

from buildbot.util import unicode2bytes
from buildbot.worker.protocols import base


class FileWriter(base.FileWriterImpl):
    """
    Helper class that acts as a file-object with write access
    """

    def __init__(self, destfile: str, maxsize: int | None, mode: int | None) -> None:
        # Create missing directories.
        destfile = os.path.abspath(destfile)
        dirname = os.path.dirname(destfile)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        self.destfile = destfile
        self.mode = mode
        fd, self.tmpname = tempfile.mkstemp(dir=dirname, prefix='buildbot-transfer-')
        self.fp: IO[bytes] | None = os.fdopen(fd, 'wb')
        self.remaining = maxsize

    def remote_write(self, data: str | bytes) -> None:  # type: ignore[override]
        """
        Called from remote worker to write L{data} to L{fp} within boundaries
        of L{maxsize}

        @type  data: C{string}
        @param data: String of data to write
        """
        data = unicode2bytes(data)
        if self.remaining is not None:
            if len(data) > self.remaining:
                data = data[: self.remaining]
            self.fp.write(data)  # type: ignore[union-attr]
            self.remaining = self.remaining - len(data)
        else:
            self.fp.write(data)  # type: ignore[union-attr]

    def remote_utime(self, accessed_modified: tuple[float, float]) -> None:  # type: ignore[override]
        os.utime(self.destfile, accessed_modified)

    def remote_close(self) -> None:  # type: ignore[override]
        """
        Called by remote worker to state that no more data will be transferred
        """
        self.fp.close()  # type: ignore[union-attr]
        self.fp = None
        # on windows, os.rename does not automatically unlink, so do it
        # manually
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        os.rename(self.tmpname, self.destfile)
        self.tmpname = None  # type: ignore[assignment]
        if self.mode is not None:
            os.chmod(self.destfile, self.mode)

    def cancel(self) -> None:
        # unclean shutdown, the file is probably truncated, so delete it
        # altogether rather than deliver a corrupted file
        fp = getattr(self, "fp", None)
        if fp:
            fp.close()
            self.purge()

    def purge(self) -> None:
        if self.destfile and os.path.exists(self.destfile):
            os.unlink(self.destfile)
        if self.tmpname and os.path.exists(self.tmpname):
            os.unlink(self.tmpname)


class DirectoryWriter(FileWriter):
    """
    A DirectoryWriter is implemented as a FileWriter, with an added post-processing
    step to unpack the archive, once the transfer has completed.
    """

    def __init__(
        self, destroot: str, maxsize: int | None, compress: str | None, mode: int | None
    ) -> None:
        self.destroot = destroot
        self.compress = compress

        self.fd, self.tarname = tempfile.mkstemp(prefix='buildbot-transfer-')
        os.close(self.fd)

        super().__init__(self.tarname, maxsize, mode)

    def remote_unpack(self) -> None:  # type: ignore[override]
        """
        Called by remote worker to state that no more data will be transferred
        """
        # Make sure remote_close is called, otherwise atomic rename won't happen
        self.remote_close()

        # Map configured compression to a TarFile setting
        tar_mode: Literal['r|bz2', 'r|gz', 'r']
        if self.compress == 'bz2':
            tar_mode = 'r|bz2'
        elif self.compress == 'gz':
            tar_mode = 'r|gz'
        else:
            tar_mode = 'r'

        # Unpack archive and clean up after self
        with tarfile.open(name=self.tarname, mode=tar_mode) as archive:
            if hasattr(tarfile, 'data_filter'):
                archive.extractall(path=self.destroot, filter='data')
            else:
                archive.extractall(path=self.destroot)
        os.remove(self.tarname)

    def purge(self) -> None:
        super().purge()
        if os.path.isdir(self.destroot):
            shutil.rmtree(self.destroot)


class FileReader(base.FileReaderImpl):
    """
    Helper class that acts as a file-object with read access
    """

    def __init__(self, fp: IO[bytes]) -> None:
        self.fp: IO[bytes] | None = fp

    def remote_read(self, maxlength: int) -> bytes | str:  # type: ignore[override]
        """
        Called from remote worker to read at most L{maxlength} bytes of data

        @type  maxlength: C{integer}
        @param maxlength: Maximum number of data bytes that can be returned

        @return: Data read from L{fp}
        @rtype: C{string} of bytes read from file
        """
        if self.fp is None:
            return ''

        data = self.fp.read(maxlength)
        return data

    def remote_close(self) -> None:  # type: ignore[override]
        """
        Called by remote worker to state that no more data will be transferred
        """
        if self.fp is not None:
            self.fp.close()
            self.fp = None


class StringFileWriter(base.FileWriterImpl):
    """
    FileWriter class that just puts received data into a buffer.

    Used to upload a file from worker for inline processing rather than
    writing into a file on master.
    """

    def __init__(self) -> None:
        self.buffer = ""
        # Data arrives in fixed-size chunks (see FileWriterImpl blocksize), so a multi-byte
        # UTF-8 character can be split across two remote_write() calls, or the data may simply
        # not be valid UTF-8 at all (e.g. mixed-encoding log output). Either way, decoding each
        # chunk independently would raise UnicodeDecodeError, which propagates out of a Twisted
        # PB remote-message handler rather than through buildbot's normal command-failure path,
        # hanging the step forever (see issue #3982). An incremental decoder retains the
        # undecoded tail of a chunk and prepends it to the next one, avoiding false positives on
        # split characters; errors='replace' (matching RunProcessPP's stdout/stderr decoding)
        # avoids raising at all, since a days-long hang is worse than a stray U+FFFD.
        self._decoder = getincrementaldecoder('utf-8')(errors='replace')

    def remote_write(self, data: str | bytes) -> None:  # type: ignore[override]
        if isinstance(data, str):
            self.buffer += data
        else:
            self.buffer += self._decoder.decode(data)

    def remote_close(self) -> None:  # type: ignore[override]
        self.buffer += self._decoder.decode(b"", final=True)


class StringFileReader(FileReader):
    """
    FileWriter class that just buid send data from a string.

    Used to download a file to worker from local string rather than first
    writing into a file on master.
    """

    def __init__(self, s: str | bytes) -> None:
        s = unicode2bytes(s)
        super().__init__(BytesIO(s))
