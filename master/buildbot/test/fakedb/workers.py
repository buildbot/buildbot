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


import json

from twisted.internet import defer

from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.test.util import validation


class Worker(Row):
    table = "workers"

    id_column = 'id'
    required_columns = ('name', )

    def __init__(self, id=None, name='some:worker', info=None, paused=0, graceful=0):
        if info is None:
            info = {"a": "b"}
        super().__init__(id=id, name=name, info=info, paused=paused, graceful=graceful)


class ConnectedWorker(Row):
    table = "connected_workers"

    id_column = 'id'
    required_columns = ('masterid', 'workerid')

    def __init__(self, id=None, masterid=None, workerid=None):
        super().__init__(id=id, masterid=masterid, workerid=workerid)


class ConfiguredWorker(Row):
    table = "configured_workers"

    id_column = 'id'
    required_columns = ('buildermasterid', 'workerid')

    def __init__(self, id=None, buildermasterid=None, workerid=None):
        super().__init__(id=id, buildermasterid=buildermasterid, workerid=workerid)


class FakeWorkersComponent(FakeDBComponent):

    def setUp(self):
        self.workers = {}
        self.configured = {}
        self.connected = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Worker):
                self.workers[row.id] = dict(
                    id=row.id,
                    name=row.name,
                    paused=row.paused,
                    graceful=row.graceful,
                    info=row.info)
            elif isinstance(row, ConfiguredWorker):
                row.id = row.buildermasterid * 10000 + row.workerid
                self.configured[row.id] = dict(
                    buildermasterid=row.buildermasterid,
                    workerid=row.workerid)
            elif isinstance(row, ConnectedWorker):
                self.connected[row.id] = dict(
                    masterid=row.masterid,
                    workerid=row.workerid)

    def findWorkerId(self, name):
        validation.verifyType(self.t, 'name', name,
                              validation.IdentifierValidator(50))
        for m in self.workers.values():
            if m['name'] == name:
                return defer.succeed(m['id'])
        id = len(self.workers) + 1
        self.workers[id] = dict(
            id=id,
            name=name,
            info={})
        return defer.succeed(id)

    def _getWorkerByName(self, name):
        for worker in self.workers.values():
            if worker['name'] == name:
                return worker
        return None

    def getWorker(self, workerid=None, name=None, masterid=None, builderid=None):
        # get the id and the worker
        if workerid is None:
            for worker in self.workers.values():
                if worker['name'] == name:
                    workerid = worker['id']
                    break
            else:
                worker = None
        else:
            worker = self.workers.get(workerid)

        if not worker:
            return defer.succeed(None)

        # now get the connection status per builder_master, filtered
        # by builderid and masterid
        return defer.succeed(self._mkdict(worker, builderid, masterid))

    def getWorkers(self, masterid=None, builderid=None, paused=None, graceful=None):
        if masterid is not None or builderid is not None:
            builder_masters = self.db.builders.builder_masters
            workers = []
            for worker in self.workers.values():
                configured = [cfg for cfg in self.configured.values()
                              if cfg['workerid'] == worker['id']]
                pairs = [builder_masters[cfg['buildermasterid']]
                         for cfg in configured]
                if builderid is not None and masterid is not None:
                    if (builderid, masterid) not in pairs:
                        continue
                if builderid is not None:
                    if not any(builderid == p[0] for p in pairs):
                        continue
                if masterid is not None:
                    if not any((masterid == p[1]) for p in pairs):
                        continue
                workers.append(worker)
        else:
            workers = list(self.workers.values())

        if paused is not None:
            workers = [w for w in workers if w['paused'] == paused]
        if graceful is not None:
            workers = [w for w in workers if w['graceful'] == graceful]

        return defer.succeed([
            self._mkdict(worker, builderid, masterid)
            for worker in workers])

    def workerConnected(self, workerid, masterid, workerinfo):
        worker = self.workers.get(workerid)
        # test serialization
        json.dumps(workerinfo)
        if worker is not None:
            worker['info'] = workerinfo
        new_conn = dict(masterid=masterid, workerid=workerid)
        if new_conn not in self.connected.values():
            conn_id = max([0] + list(self.connected)) + 1
            self.connected[conn_id] = new_conn
        return defer.succeed(None)

    def deconfigureAllWorkersForMaster(self, masterid):
        buildermasterids = [_id for _id, (builderid, mid) in
                            self.db.builders.builder_masters.items() if mid == masterid]
        for k, v in list(self.configured.items()):
            if v['buildermasterid'] in buildermasterids:
                del self.configured[k]

    def workerConfigured(self, workerid, masterid, builderids):

        buildermasterids = [_id for _id, (builderid, mid) in
                            self.db.builders.builder_masters.items()
                            if mid == masterid and builderid in builderids]
        if len(buildermasterids) != len(builderids):
            raise ValueError(f"Some builders are not configured for this master: "
                             f"builders: {builderids}, master: {masterid} "
                             f"buildermaster:{self.db.builders.builder_masters}"
                             )

        allbuildermasterids = [_id for _id, (builderid, mid) in
                               self.db.builders.builder_masters.items() if mid == masterid]
        for k, v in list(self.configured.items()):
            if v['buildermasterid'] in allbuildermasterids and v['workerid'] == workerid:
                del self.configured[k]
        self.insertTestData([ConfiguredWorker(workerid=workerid,
                                              buildermasterid=buildermasterid)
                             for buildermasterid in buildermasterids])
        return defer.succeed(None)

    def workerDisconnected(self, workerid, masterid):
        del_conn = dict(masterid=masterid, workerid=workerid)
        for id, conn in self.connected.items():
            if conn == del_conn:
                del self.connected[id]  # noqa pylint: disable=unnecessary-dict-index-lookup
                break
        return defer.succeed(None)

    def setWorkerState(self, workerid, paused, graceful):
        worker = self.workers.get(workerid)
        if worker is not None:
            worker['paused'] = int(paused)
            worker['graceful'] = int(graceful)

    def _configuredOn(self, workerid, builderid=None, masterid=None):
        cfg = []
        for cs in self.configured.values():
            if cs['workerid'] != workerid:
                continue
            bid, mid = self.db.builders.builder_masters[cs['buildermasterid']]
            if builderid is not None and bid != builderid:
                continue
            if masterid is not None and mid != masterid:
                continue
            cfg.append({'builderid': bid, 'masterid': mid})
        return cfg

    def _connectedTo(self, workerid, masterid=None):
        conns = []
        for cs in self.connected.values():
            if cs['workerid'] != workerid:
                continue
            if masterid is not None and cs['masterid'] != masterid:
                continue
            conns.append(cs['masterid'])
        return conns

    def _mkdict(self, w, builderid, masterid):
        return {
            'id': w['id'],
            'workerinfo': w['info'],
            'name': w['name'],
            'paused': bool(w.get('paused')),
            'graceful': bool(w.get('graceful')),
            'configured_on': self._configuredOn(w['id'], builderid, masterid),
            'connected_to': self._connectedTo(w['id'], masterid),
        }
