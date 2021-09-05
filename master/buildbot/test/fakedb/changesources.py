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


from twisted.internet import defer

from buildbot.db import changesources
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row


class ChangeSource(Row):
    table = "changesources"

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]

    def __init__(self, id=None, name='csname', name_hash=None):
        super().__init__(id=id, name=name, name_hash=name_hash)


class ChangeSourceMaster(Row):
    table = "changesource_masters"

    foreignKeys = ('changesourceid', 'masterid')
    required_columns = ('changesourceid', 'masterid')

    def __init__(self, changesourceid=None, masterid=None):
        super().__init__(changesourceid=changesourceid, masterid=masterid)


class FakeChangeSourcesComponent(FakeDBComponent):

    def setUp(self):
        self.changesources = {}
        self.changesource_masters = {}
        self.states = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, ChangeSource):
                self.changesources[row.id] = row.name
            if isinstance(row, ChangeSourceMaster):
                self.changesource_masters[row.changesourceid] = row.masterid

    # component methods

    def findChangeSourceId(self, name):
        for cs_id, cs_name in self.changesources.items():
            if cs_name == name:
                return defer.succeed(cs_id)
        new_id = (max(self.changesources) + 1) if self.changesources else 1
        self.changesources[new_id] = name
        return defer.succeed(new_id)

    def getChangeSource(self, changesourceid):
        if changesourceid in self.changesources:
            rv = dict(
                id=changesourceid,
                name=self.changesources[changesourceid],
                masterid=None)
            # only set masterid if the relevant changesource master exists and
            # is active
            rv['masterid'] = self.changesource_masters.get(changesourceid)
            return defer.succeed(rv)
        return None

    def getChangeSources(self, active=None, masterid=None):
        d = defer.DeferredList([
            self.getChangeSource(id) for id in self.changesources
        ])

        @d.addCallback
        def filter(results):
            # filter off the DeferredList results (we know it's good)
            results = [r[1] for r in results]
            # filter for masterid
            if masterid is not None:
                results = [r for r in results
                           if r['masterid'] == masterid]
            # filter for active or inactive if necessary
            if active:
                results = [r for r in results
                           if r['masterid'] is not None]
            elif active is not None:
                results = [r for r in results
                           if r['masterid'] is None]
            return results
        return d

    def setChangeSourceMaster(self, changesourceid, masterid):
        current_masterid = self.changesource_masters.get(changesourceid)
        if current_masterid and masterid is not None and current_masterid != masterid:
            return defer.fail(changesources.ChangeSourceAlreadyClaimedError())
        self.changesource_masters[changesourceid] = masterid
        return defer.succeed(None)

    # fake methods

    def fakeChangeSource(self, name, changesourceid):
        self.changesources[changesourceid] = name

    def fakeChangeSourceMaster(self, changesourceid, masterid):
        if masterid is not None:
            self.changesource_masters[changesourceid] = masterid
        else:
            del self.changesource_masters[changesourceid]

    # assertions

    def assertChangeSourceMaster(self, changesourceid, masterid):
        self.t.assertEqual(self.changesource_masters.get(changesourceid),
                           masterid)
