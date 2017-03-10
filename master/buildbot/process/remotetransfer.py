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

from __future__ import absolute_import
from __future__ import print_function

import os
import tarfile
import tempfile
from io import BytesIO

from buildbot.util import bytes2NativeString
from buildbot.util import unicode2bytes
from buildbot.worker.protocols import base


"""
module for regrouping all FileWriterImpl and FileReaderImpl away from steps
"""


class FileWriter(base.FileWriterImpl):

    """
    Helper class that acts as a file-object with write access
    """

    def __init__(self, destfile, maxsize, mode):
        # Create missing directories.
        destfile = os.path.abspath(destfile)
        dirname = os.path.dirname(destfile)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        self.destfile = destfile
        self.mode = mode
        fd, self.tmpname = tempfile.mkstemp(dir=dirname)
        self.fp = os.fdopen(fd, 'wb')
        self.remaining = maxsize

    def remote_write(self, data):
        """
        Called from remote worker to write L{data} to L{fp} within boundaries
        of L{maxsize}

        @type  data: C{string}
        @param data: String of data to write
        """
        data = unicode2bytes(data)
        if self.remaining is not None:
            if len(data) > self.remaining:
                data = data[:self.remaining]
            self.fp.write(data)
            self.remaining = self.remaining - len(data)
        else:
            self.fp.write(data)

    def remote_utime(self, accessed_modified):
        os.utime(self.destfile, accessed_modified)

    def remote_close(self):
        """
        Called by remote worker to state that no more data will be transferred
        """
        self.fp.close()
        self.fp = None
        # on windows, os.rename does not automatically unlink, so do it
        # manually
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        os.rename(self.tmpname, self.destfile)
        self.tmpname = None
        if self.mode is not None:
            os.chmod(self.destfile, self.mode)

    def cancel(self):
        # unclean shutdown, the file is probably truncated, so delete it
        # altogether rather than deliver a corrupted file
        fp = getattr(self, "fp", None)
        if fp:
            fp.close()
            if self.destfile and os.path.exists(self.destfile):
                os.unlink(self.destfile)
            if self.tmpname and os.path.exists(self.tmpname):
                os.unlink(self.tmpname)


class DirectoryWriter(FileWriter):

    """
    A DirectoryWriter is implemented as a FileWriter, with an added post-processing
    step to unpack the archive, once the transfer has completed.
    """

    def __init__(self, destroot, maxsize, compress, mode):
        self.destroot = destroot
        self.compress = compress

        self.fd, self.tarname = tempfile.mkstemp()
        os.close(self.fd)

        FileWriter.__init__(self, self.tarname, maxsize, mode)

    def remote_unpack(self):
        """
        Called by remote worker to state that no more data will be transferred
        """
        # Make sure remote_close is called, otherwise atomic rename wont happen
        self.remote_close()

        # Map configured compression to a TarFile setting
        if self.compress == 'bz2':
            mode = 'r|bz2'
        elif self.compress == 'gz':
            mode = 'r|gz'
        else:
            mode = 'r'

        # Unpack archive and clean up after self
        archive = tarfile.open(name=self.tarname, mode=mode)
        archive.extractall(path=self.destroot)
        archive.close()
        os.remove(self.tarname)


class FileReader(base.FileReaderImpl):

    """
    Helper class that acts as a file-object with read access
    """

    def __init__(self, fp):
        self.fp = fp

    def remote_read(self, maxlength):
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

    def remote_close(self):
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

    def __init__(self):
        self.buffer = ""

    def remote_write(self, data):
        self.buffer += bytes2NativeString(data)

    def remote_close(self):
        pass


class StringFileReader(FileReader):

    """
    FileWriter class that just buid send data from a string.

    Used to download a file to worker from local string rather than first
    writing into a file on master.
    """

    def __init__(self, s):
        s = unicode2bytes(s)
        FileReader.__init__(self, BytesIO(s))
