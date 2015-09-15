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
from future.utils import itervalues

import sqlalchemy as sa

from buildbot.db import base
from buildbot.util import identifiers
from twisted.internet import defer


class BuildworkersConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def findBuildworkerId(self, name):
        tbl = self.db.model.buildworkers
        # callers should verify this and give good user error messages
        assert identifiers.isIdentifier(50, name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name == name),
            insert_values=dict(
                name=name,
                info={},
            ))

    def deconfigureAllBuidworkersForMaster(self, masterid):
        def thd(conn):
            # first remove the old configured buildermasterids for this master and worker
            # as sqlalchemy does not support delete with join, we need to do that in 2 queries
            cfg_tbl = self.db.model.configured_buildworkers
            bm_tbl = self.db.model.builder_masters
            j = cfg_tbl
            j = j.outerjoin(bm_tbl)
            q = sa.select([cfg_tbl.c.buildermasterid], from_obj=[j])
            q = q.where(bm_tbl.c.masterid == masterid)
            buildermasterids = [row['buildermasterid'] for row in conn.execute(q)]
            if buildermasterids:
                q = cfg_tbl.delete()
                q = q.where(cfg_tbl.c.buildermasterid.in_(buildermasterids))
                conn.execute(q)

        return self.db.pool.do(thd)

    def buildworkerConfigured(self, buildworkerid, masterid, builderids):
        # nothing to add
        if not builderids:
            return defer.succeed(None)

        def thd(conn):

            # get the buildermasterids that are configured
            cfg_tbl = self.db.model.configured_buildworkers
            bm_tbl = self.db.model.builder_masters
            q = sa.select([bm_tbl.c.id], from_obj=[bm_tbl])
            q = q.where(bm_tbl.c.masterid == masterid)
            q = q.where(bm_tbl.c.builderid.in_(builderids))
            buildermasterids = [row['id'] for row in conn.execute(q)]

            # and insert them
            q = cfg_tbl.insert()
            try:
                conn.execute(q,
                             [{'buildworkerid': buildworkerid, 'buildermasterid': buildermasterid}
                              for buildermasterid in buildermasterids])
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                # if some rows are already present, insert one by one.
                pass
            else:
                return

            for buildermasterid in buildermasterids:
                # insert them one by one
                q = cfg_tbl.insert()
                try:
                    conn.execute(q, {'buildworkerid': buildworkerid, 'buildermasterid': buildermasterid})
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                    # if the row is already present, silently fail..
                    pass

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getBuildworker(self, buildworkerid=None, name=None, masterid=None,
                      builderid=None):
        if buildworkerid is None and name is None:
            defer.returnValue(None)
        bworkers = yield self.getBuildworkers(_buildworkerid=buildworkerid,
                                            _name=name, masterid=masterid, builderid=builderid)
        if bworkers:
            defer.returnValue(bworkers[0])

    def getBuildworkers(self, _buildworkerid=None, _name=None, masterid=None,
                       builderid=None):
        def thd(conn):
            bworker_tbl = self.db.model.buildworkers
            conn_tbl = self.db.model.connected_buildworkers
            cfg_tbl = self.db.model.configured_buildworkers
            bm_tbl = self.db.model.builder_masters

            def selectWorker(q):
                return q

            # first, get the buildworker itself and the configured_on info
            j = bworker_tbl
            j = j.outerjoin(cfg_tbl)
            j = j.outerjoin(bm_tbl)
            q = sa.select(
                [bworker_tbl.c.id, bworker_tbl.c.name, bworker_tbl.c.info,
                 bm_tbl.c.builderid, bm_tbl.c.masterid],
                from_obj=[j],
                order_by=[bworker_tbl.c.id])

            if _buildworkerid is not None:
                q = q.where(bworker_tbl.c.id == _buildworkerid)
            if _name is not None:
                q = q.where(bworker_tbl.c.name == _name)
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
            # buildworkers
            j = conn_tbl
            if _name is not None:
                # note this is not an outer join; if there are unconnected
                # buildworkers, they were captured in rv above
                j = j.join(bworker_tbl)
            q = sa.select(
                [conn_tbl.c.buildworkerid, conn_tbl.c.masterid],
                from_obj=[j],
                order_by=[conn_tbl.c.buildworkerid])

            if _buildworkerid is not None:
                q = q.where(conn_tbl.c.buildworkerid == _buildworkerid)
            if _name is not None:
                q = q.where(bworker_tbl.c.name == _name)
            if masterid is not None:
                q = q.where(conn_tbl.c.masterid == masterid)

            for row in conn.execute(q):
                id = row.buildworkerid
                if id not in rv:
                    continue
                rv[row.buildworkerid]['connected_to'].append(row.masterid)

            return list(itervalues(rv))
        return self.db.pool.do(thd)

    def buildworkerConnected(self, buildworkerid, masterid, workerinfo):
        def thd(conn):
            conn_tbl = self.db.model.connected_buildworkers
            q = conn_tbl.insert()
            try:
                conn.execute(q,
                             {'buildworkerid': buildworkerid, 'masterid': masterid})
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                # if the row is already present, silently fail..
                pass

            bs_tbl = self.db.model.buildworkers
            q = bs_tbl.update(whereclause=(bs_tbl.c.id == buildworkerid))
            conn.execute(q, info=workerinfo)
        return self.db.pool.do(thd)

    def buildworkerDisconnected(self, buildworkerid, masterid):
        def thd(conn):
            tbl = self.db.model.connected_buildworkers
            q = tbl.delete(whereclause=(tbl.c.buildworkerid == buildworkerid)
                           & (tbl.c.masterid == masterid))
            conn.execute(q)
        return self.db.pool.do(thd)
