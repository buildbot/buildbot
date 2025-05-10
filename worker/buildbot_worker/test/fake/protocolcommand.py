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

import pprint
from typing import TYPE_CHECKING

from buildbot_worker.base import ProtocolCommandBase

if TYPE_CHECKING:
    from typing import Any
    from typing import Iterable

    from twisted.internet.defer import Deferred

    from buildbot_worker.test.fake.remote import FakeRemote


class FakeProtocolCommand(ProtocolCommandBase):
    debug = False

    def __init__(self, basedir: str) -> None:
        self.unicode_encoding = 'utf-8'
        self.updates: list[tuple[str, Any] | str] = []
        self.worker_basedir = basedir
        self.basedir = basedir

    def show(self) -> str:
        return pprint.pformat(self.updates)

    def send_update(self, status: Iterable[tuple[str, Any]]) -> None:
        if self.debug:
            print("FakeWorkerForBuilder.sendUpdate", status)
        for st in status:
            self.updates.append(st)

    def protocol_update_upload_file_close(self, writer: FakeRemote) -> Deferred[None]:
        return writer.callRemote("close")

    def protocol_update_upload_file_utime(
        self,
        writer: FakeRemote,
        access_time: float,
        modified_time: float,
    ) -> Deferred[None]:
        return writer.callRemote("utime", (access_time, modified_time))

    def protocol_update_upload_file_write(
        self,
        writer: FakeRemote,
        data: str | bytes,
    ) -> Deferred[None]:
        return writer.callRemote('write', data)

    def protocol_update_upload_directory(self, writer: FakeRemote) -> Deferred[None]:
        return writer.callRemote("unpack")

    def protocol_update_upload_directory_write(
        self,
        writer: FakeRemote,
        data: str | bytes,
    ) -> Deferred[None]:
        return writer.callRemote('write', data)

    def protocol_update_read_file_close(self, reader: FakeRemote) -> Deferred[None]:
        return reader.callRemote('close')

    def protocol_update_read_file(self, reader: FakeRemote, length: int) -> Deferred[None]:
        return reader.callRemote('read', length)
