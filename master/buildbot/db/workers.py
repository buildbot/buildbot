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
from future.utils import itervalues

import sqlalchemy as sa

from twisted.internet import defer

from buildbot.db import base
from buildbot.util import identifiers
from buildbot.worker_transition import deprecatedWorkerClassMethod


class WorkersConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def findWorkerId(self, name):
        tbl = self.db.model.workers
        # callers should verify this and give good user error messages
        assert identifiers.isIdentifier(50, name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name == name),
            insert_values=dict(
                name=name,
                info={},
            ))

    def _deleteFromConfiguredWorkers_thd(self, conn, buildermasterids):
        cfg_tbl = self.db.model.configured_workers
        # batch deletes to avoid using too many variables
        for batch in self.doBatch(buildermasterids, 100):
            q = cfg_tbl.delete()
            q = q.where(cfg_tbl.c.buildermasterid.in_(batch))
            conn.execute(q).close()

    def deconfigureAllWorkersForMaster(self, masterid):
        def thd(conn):
            # first remove the old configured buildermasterids for this master and worker
            # as sqlalchemy does not support delete with join, we need to do
            # that in 2 queries
            cfg_tbl = self.db.model.configured_workers
            bm_tbl = self.db.model.builder_masters
            j = cfg_tbl
            j = j.outerjoin(bm_tbl)
            q = sa.select(
                [cfg_tbl.c.buildermasterid], from_obj=[j], distinct=True)
            q = q.where(bm_tbl.c.masterid == masterid)
            res = conn.execute(q)
            buildermasterids = [row['buildermasterid']
                                for row in res]
            res.close()
            self._deleteFromConfiguredWorkers_thd(conn, buildermasterids)

        return self.db.pool.do(thd)

    def workerConfigured(self, workerid, masterid, builderids):

        def thd(conn):

            cfg_tbl = self.db.model.configured_workers
            bm_tbl = self.db.model.builder_masters

            # get the buildermasterids that are configured
            if builderids:
                q = sa.select([bm_tbl.c.id], from_obj=[bm_tbl])
                q = q.where(bm_tbl.c.masterid == masterid)
                q = q.where(bm_tbl.c.builderid.in_(builderids))
                res = conn.execute(q)
                buildermasterids = set([row['id'] for row in res])
                res.close()
            else:
                buildermasterids = set([])

            j = cfg_tbl
            j = j.outerjoin(bm_tbl)
            q = sa.select(
                [cfg_tbl.c.buildermasterid], from_obj=[j], distinct=True)
            q = q.where(bm_tbl.c.masterid == masterid)
            q = q.where(cfg_tbl.c.workerid == workerid)
            res = conn.execute(q)
            oldbuildermasterids = set(
                [row['buildermasterid'] for row in res])
            res.close()

            todeletebuildermasterids = oldbuildermasterids - buildermasterids
            toinsertbuildermasterids = buildermasterids - oldbuildermasterids
            transaction = conn.begin()
            self._deleteFromConfiguredWorkers_thd(
                conn, todeletebuildermasterids)

            # and insert the new ones
            if toinsertbuildermasterids:
                q = cfg_tbl.insert()
                conn.execute(q,
                             [{'workerid': workerid, 'buildermasterid': buildermasterid}
                              for buildermasterid in toinsertbuildermasterids]).close()

            transaction.commit()

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getWorker(self, workerid=None, name=None, masterid=None,
                  builderid=None):
        if workerid is None and name is None:
            defer.returnValue(None)
        workers = yield self.getWorkers(_workerid=workerid,
                                        _name=name, masterid=masterid, builderid=builderid)
        if workers:
            defer.returnValue(workers[0])

    def getWorkers(self, _workerid=None, _name=None, masterid=None,
                   builderid=None):
        def thd(conn):
            workers_tbl = self.db.model.workers
            conn_tbl = self.db.model.connected_workers
            cfg_tbl = self.db.model.configured_workers
            bm_tbl = self.db.model.builder_masters

            def selectWorker(q):
                return q

            # first, get the worker itself and the configured_on info
            j = workers_tbl
            j = j.outerjoin(cfg_tbl)
            j = j.outerjoin(bm_tbl)
            q = sa.select(
                [workers_tbl.c.id, workers_tbl.c.name, workers_tbl.c.info,
                 bm_tbl.c.builderid, bm_tbl.c.masterid],
                from_obj=[j],
                order_by=[workers_tbl.c.id])

            if _workerid is not None:
                q = q.where(workers_tbl.c.id == _workerid)
            if _name is not None:
                q = q.where(workers_tbl.c.name == _name)
            if masterid is not None:
                q = q.where(bm_tbl.c.masterid == masterid)
            if builderid is not None:
                q = q.where(bm_tbl.c.builderid == builderid)

            rv = {}
            res = None
            lastId = None
            cfgs = None
            for row in conn.execute(q):
                if row.id != lastId:
                    lastId = row.id
                    cfgs = []
                    res = {
                        'id': lastId,
                        'name': row.name,
                        'configured_on': cfgs,
                        'connected_to': [],
                        'workerinfo': row.info}
                    rv[lastId] = res
                if row.builderid and row.masterid:
                    cfgs.append({'builderid': row.builderid,
                                 'masterid': row.masterid})

            # now go back and get the connection info for the same set of
            # workers
            j = conn_tbl
            if _name is not None:
                # note this is not an outer join; if there are unconnected
                # workers, they were captured in rv above
                j = j.join(workers_tbl)
            q = sa.select(
                [conn_tbl.c.workerid, conn_tbl.c.masterid],
                from_obj=[j],
                order_by=[conn_tbl.c.workerid])

            if _workerid is not None:
                q = q.where(conn_tbl.c.workerid == _workerid)
            if _name is not None:
                q = q.where(workers_tbl.c.name == _name)
            if masterid is not None:
                q = q.where(conn_tbl.c.masterid == masterid)

            for row in conn.execute(q):
                id = row.workerid
                if id not in rv:
                    continue
                rv[row.workerid]['connected_to'].append(row.masterid)

            return list(itervalues(rv))
        return self.db.pool.do(thd)
    deprecatedWorkerClassMethod(
        locals(), getWorkers, compat_name="getBuildslaves")

    def workerConnected(self, workerid, masterid, workerinfo):
        def thd(conn):
            conn_tbl = self.db.model.connected_workers
            q = conn_tbl.insert()
            try:
                conn.execute(q,
                             {'workerid': workerid, 'masterid': masterid})
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                # if the row is already present, silently fail..
                pass

            bs_tbl = self.db.model.workers
            q = bs_tbl.update(whereclause=(bs_tbl.c.id == workerid))
            conn.execute(q, info=workerinfo)
        return self.db.pool.do(thd)

    def workerDisconnected(self, workerid, masterid):
        def thd(conn):
            tbl = self.db.model.connected_workers
            q = tbl.delete(whereclause=(tbl.c.workerid == workerid) &
                                       (tbl.c.masterid == masterid))
            conn.execute(q)
        return self.db.pool.do(thd)
