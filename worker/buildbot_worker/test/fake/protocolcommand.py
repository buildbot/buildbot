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

import pprint

from buildbot_worker.base import ProtocolCommandBase


class FakeProtocolCommand(ProtocolCommandBase):
    debug = False

    def __init__(self, basedir):
        self.unicode_encoding = 'utf-8'
        self.updates = []
        self.worker_basedir = basedir
        self.basedir = basedir

    def show(self):
        return pprint.pformat(self.updates)

    def send_update(self, status):
        if self.debug:
            print("FakeWorkerForBuilder.sendUpdate", status)
        for st in status:
            self.updates.append(st)

    # Returns a Deferred
    def protocol_update_upload_file_close(self, writer):
        return writer.callRemote("close")

    # Returns a Deferred
    def protocol_update_upload_file_utime(self, writer, access_time, modified_time):
        return writer.callRemote("utime", (access_time, modified_time))

    # Returns a Deferred
    def protocol_update_upload_file_write(self, writer, data):
        return writer.callRemote('write', data)

    # Returns a Deferred
    def protocol_update_upload_directory(self, writer):
        return writer.callRemote("unpack")

    # Returns a Deferred
    def protocol_update_upload_directory_write(self, writer, data):
        return writer.callRemote('write', data)

    # Returns a Deferred
    def protocol_update_read_file_close(self, reader):
        return reader.callRemote('close')

    # Returns a Deferred
    def protocol_update_read_file(self, reader, length):
        return reader.callRemote('read', length)
