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

from buildbot_worker.base import ProtocolCommandBase


class FakeProtocolCommand(ProtocolCommandBase):
    def __init__(self, builder):
        self.builder = builder
        self.unicode_encoding = builder.unicode_encoding
        self.basedir = builder.basedir

    def send_update(self, status):
        self.builder.sendUpdate(status)

    def protocol_update_upload_file_close(self, writer):
        return self.builder.protocol_update_upload_file_close(writer)

    def protocol_update_upload_file_utime(self, writer, access_time, modified_time):
        return self.builder.protocol_update_upload_file_utime(writer, access_time, modified_time)

    def protocol_update_upload_file_write(self, writer, data):
        return self.builder.protocol_update_upload_file_write(writer, data)

    def protocol_update_upload_directory(self, writer):
        return self.builder.protocol_update_upload_directory(writer)

    def protocol_update_upload_directory_write(self, writer, data):
        return self.builder.protocol_update_upload_directory_write(writer, data)

    def protocol_update_read_file_close(self, reader):
        return self.builder.protocol_update_read_file_close(reader)

    def protocol_update_read_file(self, reader, length):
        return self.builder.protocol_update_read_file(reader, length)
