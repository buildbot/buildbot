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


class BuildslavesConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def findBuildslaveId(self, name):
        tbl = self.db.model.buildslaves
        # callers should verify this and give good user error messages
        assert identifiers.isIdentifier(50, name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name == name),
            insert_values=dict(
                name=name,
                info={},
            ))

    def deconfigureAllBuidslavesForMaster(self, masterid):
        def thd(conn):
            # first remove the old configured buildermasterids for this master and slave
            # as sqlalchemy does not support delete with join, we need to do that in 2 queries
            cfg_tbl = self.db.model.configured_buildslaves
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

    def buildslaveConfigured(self, buildslaveid, masterid, builderids):

        def thd(conn):

            cfg_tbl = self.db.model.configured_buildslaves
            bm_tbl = self.db.model.builder_masters

            # get the buildermasterids that are configured
            if builderids:
                q = sa.select([bm_tbl.c.id], from_obj=[bm_tbl])
                q = q.where(bm_tbl.c.masterid == masterid)
                q = q.where(bm_tbl.c.builderid.in_(builderids))
                buildermasterids = set([row['id'] for row in conn.execute(q)])
            else:
                buildermasterids = set([])

            j = cfg_tbl
            j = j.outerjoin(bm_tbl)
            q = sa.select([cfg_tbl.c.buildermasterid], from_obj=[j])
            q = q.where(bm_tbl.c.masterid == masterid)
            q = q.where(cfg_tbl.c.buildslaveid == buildslaveid)
            oldbuildermasterids = set([row['buildermasterid'] for row in conn.execute(q)])

            todeletebuildermasterids = oldbuildermasterids - buildermasterids
            toinsertbuildermasterids = buildermasterids - oldbuildermasterids
            transaction = conn.begin()
            if todeletebuildermasterids:
                # delete the buildermasterids that were configured previously, but not configured now
                q = cfg_tbl.delete()
                q = q.where(cfg_tbl.c.buildermasterid.in_(list(todeletebuildermasterids)))
                conn.execute(q)

            # and insert the new ones
            if toinsertbuildermasterids:
                q = cfg_tbl.insert()
                conn.execute(q,
                             [{'buildslaveid': buildslaveid, 'buildermasterid': buildermasterid}
                              for buildermasterid in toinsertbuildermasterids])

            transaction.commit()

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getBuildslave(self, buildslaveid=None, name=None, masterid=None,
                      builderid=None):
        if buildslaveid is None and name is None:
            defer.returnValue(None)
        bslaves = yield self.getBuildslaves(_buildslaveid=buildslaveid,
                                            _name=name, masterid=masterid, builderid=builderid)
        if bslaves:
            defer.returnValue(bslaves[0])

    def getBuildslaves(self, _buildslaveid=None, _name=None, masterid=None,
                       builderid=None):
        def thd(conn):
            bslave_tbl = self.db.model.buildslaves
            conn_tbl = self.db.model.connected_buildslaves
            cfg_tbl = self.db.model.configured_buildslaves
            bm_tbl = self.db.model.builder_masters

            def selectSlave(q):
                return q

            # first, get the buildslave itself and the configured_on info
            j = bslave_tbl
            j = j.outerjoin(cfg_tbl)
            j = j.outerjoin(bm_tbl)
            q = sa.select(
                [bslave_tbl.c.id, bslave_tbl.c.name, bslave_tbl.c.info,
                 bm_tbl.c.builderid, bm_tbl.c.masterid],
                from_obj=[j],
                order_by=[bslave_tbl.c.id])

            if _buildslaveid is not None:
                q = q.where(bslave_tbl.c.id == _buildslaveid)
            if _name is not None:
                q = q.where(bslave_tbl.c.name == _name)
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
                        'slaveinfo': row.info}
                    rv[lastId] = res
                if row.builderid and row.masterid:
                    cfgs.append({'builderid': row.builderid,
                                 'masterid': row.masterid})

            # now go back and get the connection info for the same set of
            # buildslaves
            j = conn_tbl
            if _name is not None:
                # note this is not an outer join; if there are unconnected
                # buildslaves, they were captured in rv above
                j = j.join(bslave_tbl)
            q = sa.select(
                [conn_tbl.c.buildslaveid, conn_tbl.c.masterid],
                from_obj=[j],
                order_by=[conn_tbl.c.buildslaveid])

            if _buildslaveid is not None:
                q = q.where(conn_tbl.c.buildslaveid == _buildslaveid)
            if _name is not None:
                q = q.where(bslave_tbl.c.name == _name)
            if masterid is not None:
                q = q.where(conn_tbl.c.masterid == masterid)

            for row in conn.execute(q):
                id = row.buildslaveid
                if id not in rv:
                    continue
                rv[row.buildslaveid]['connected_to'].append(row.masterid)

            return list(itervalues(rv))
        return self.db.pool.do(thd)

    def buildslaveConnected(self, buildslaveid, masterid, slaveinfo):
        def thd(conn):
            conn_tbl = self.db.model.connected_buildslaves
            q = conn_tbl.insert()
            try:
                conn.execute(q,
                             {'buildslaveid': buildslaveid, 'masterid': masterid})
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                # if the row is already present, silently fail..
                pass

            bs_tbl = self.db.model.buildslaves
            q = bs_tbl.update(whereclause=(bs_tbl.c.id == buildslaveid))
            conn.execute(q, info=slaveinfo)
        return self.db.pool.do(thd)

    def buildslaveDisconnected(self, buildslaveid, masterid):
        def thd(conn):
            tbl = self.db.model.connected_buildslaves
            q = tbl.delete(whereclause=(
                tbl.c.buildslaveid == buildslaveid) &
                (tbl.c.masterid == masterid))
            conn.execute(q)
        return self.db.pool.do(thd)
