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

from twisted.internet import defer

from buildbot.db.masters import MasterModel
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.util import epoch2datetime


class Master(Row):
    table = "masters"

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]

    def __init__(self, id=None, name='some:master', name_hash=None, active=1, last_active=9998999):
        super().__init__(
            id=id, name=name, name_hash=name_hash, active=active, last_active=last_active
        )


class FakeMastersComponent(FakeDBComponent):
    data2db = {"masterid": "id", "link": "id"}

    def setUp(self):
        self.masters = {}

    def insert_test_data(self, rows):
        for row in rows:
            if isinstance(row, Master):
                self.masters[row.id] = MasterModel(
                    id=row.id,
                    name=row.name,
                    active=bool(row.active),
                    last_active=epoch2datetime(row.last_active),
                )

    def findMasterId(self, name: str) -> defer.Deferred[int]:
        for m in self.masters.values():
            if m.name == name:
                return defer.succeed(m.id)
        id = len(self.masters) + 1
        self.masters[id] = MasterModel(
            id=id,
            name=name,
            active=False,
            last_active=epoch2datetime(self.reactor.seconds()),
        )
        return defer.succeed(id)

    def setMasterState(self, masterid: int, active: bool) -> defer.Deferred[bool]:
        if masterid in self.masters:
            was_active = self.masters[masterid].active
            self.masters[masterid].active = active
            if active:
                self.masters[masterid].last_active = epoch2datetime(self.reactor.seconds())
            return defer.succeed(bool(was_active) != bool(active))
        else:
            return defer.succeed(False)

    def getMaster(self, masterid: int) -> defer.Deferred[MasterModel | None]:
        if masterid in self.masters:
            return defer.succeed(self.masters[masterid])
        return defer.succeed(None)

    def getMasters(self) -> defer.Deferred[list[MasterModel]]:
        return defer.succeed(sorted(self.masters.values(), key=lambda x: x.id))

    # test helpers

    def markMasterInactive(self, masterid: int) -> defer.Deferred[None]:
        if masterid in self.masters:
            self.masters[masterid].active = False
        return defer.succeed(None)
