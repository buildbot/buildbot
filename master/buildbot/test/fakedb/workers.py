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

from buildbot.test.fakedb.row import Row


class Worker(Row):
    table = "workers"

    id_column = 'id'

    def __init__(
        self, id=None, name='some:worker', info=None, paused=0, pause_reason=None, graceful=0
    ):
        if info is None:
            info = {"a": "b"}
        super().__init__(
            id=id, name=name, info=info, paused=paused, pause_reason=pause_reason, graceful=graceful
        )


class ConnectedWorker(Row):
    table = "connected_workers"

    id_column = 'id'

    def __init__(self, id=None, masterid=None, workerid=None):
        super().__init__(id=id, masterid=masterid, workerid=workerid)


class ConfiguredWorker(Row):
    table = "configured_workers"

    id_column = 'id'

    def __init__(self, id=None, buildermasterid=None, workerid=None):
        super().__init__(id=id, buildermasterid=buildermasterid, workerid=workerid)
