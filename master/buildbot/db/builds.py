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

from twisted.internet import reactor
from buildbot.db import base
from buildbot.util import epoch2datetime
import sqlalchemy as sa

class BuildsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def getBuild(self, bid):
        def thd(conn):
            tbl = self.db.model.builds
            res = conn.execute(tbl.select(whereclause=(tbl.c.id == bid)))
            row = res.fetchone()

            rv = None
            if row:
                rv = self._bdictFromRow(row)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def getBuildsAndResultForRequest(self, brid):
        def thd(conn):
            builds_tbl = self.db.model.builds
            buildrequest_tbl = self.db.model.buildrequests
            q = sa.select([builds_tbl.c.id, builds_tbl.c.number, buildrequest_tbl.c.id.label("brid"), builds_tbl.c.start_time,
                                   builds_tbl.c.finish_time, buildrequest_tbl.c.results],
                                  from_obj= buildrequest_tbl.outerjoin(builds_tbl,
                                                        (buildrequest_tbl.c.id == builds_tbl.c.brid)),
                                  whereclause=(buildrequest_tbl.c.id == brid))
            res = conn.execute(q)
            return [ self._bdictFromRow(row)
                     for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def getBuildsForRequest(self, brid):
        def thd(conn):
            tbl = self.db.model.builds
            q = tbl.select(whereclause=(tbl.c.brid == brid))
            res = conn.execute(q)
            return [ self._bdictFromRow(row) for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def addBuild(self, brid, number, _reactor=reactor):
        def thd(conn):
            start_time = _reactor.seconds()
            r = conn.execute(self.db.model.builds.insert(),
                    dict(number=number, brid=brid, start_time=start_time,
                        finish_time=None))
            return r.inserted_primary_key[0]
        return self.db.pool.do(thd)

    def finishBuilds(self, bids, _reactor=reactor):
        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.builds
            now = _reactor.seconds()

            # split the bids into batches, so as not to overflow the parameter
            # lists of the database interface
            remaining = bids
            while remaining:
                batch, remaining = remaining[:100], remaining[100:]
                q = tbl.update(whereclause=(tbl.c.id.in_(batch)))
                conn.execute(q, finish_time=now)

            transaction.commit()
        return self.db.pool.do(thd)

    def finishedMergedBuilds(self, brids, number):
        def thd(conn):
            if len(brids) > 1:
                builds_tbl = self.db.model.builds

                q = sa.select([builds_tbl.c.number, builds_tbl.c.finish_time])\
                    .where(builds_tbl.c.brid == brids[0])\
                    .where(builds_tbl.c.number == number)

                res = conn.execute(q)
                row = res.fetchone()
                if row:
                    stmt = builds_tbl.update()\
                        .where(builds_tbl.c.brid.in_(brids))\
                        .where(builds_tbl.c.number==number)\
                        .where(builds_tbl.c.finish_time == None)\
                        .values(finish_time = row.finish_time)

                    res = conn.execute(stmt)
                    return res.rowcount

        return self.db.pool.do(thd)

    def getLastBuildsNumbers(self, buildername=None, sourcestamps=None, num_builds=1):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests
            buildsets_tbl = self.db .model.buildsets
            sourcestampsets_tbl = self.db.model.sourcestampsets
            sourcestamps_tbl = self.db.model.sourcestamps
            builds_tbl = self.db.model.builds

            stmt = sa.select([buildrequests_tbl.c.id],
                          from_obj=buildrequests_tbl
                          .join(buildsets_tbl,
                                (buildrequests_tbl.c.buildsetid == buildsets_tbl.c.id) &
                                (buildrequests_tbl.c.buildername == buildername)
                                & (buildrequests_tbl.c.complete == 1))
                          .join(sourcestampsets_tbl,
                                (buildsets_tbl.c.sourcestampsetid == sourcestampsets_tbl.c.id)),
                          order_by = [sa.desc(buildrequests_tbl.c.id)]).limit(num_builds)

            if sourcestamps:
                stmt.join(sourcestamps_tbl,
                          (sourcestamps_tbl.c.sourcestampsetid == sourcestampsets_tbl.c.id)
                          & (sourcestamps_tbl.c.codebase == sa.bindparam('b_codebase'))
                          & (sourcestamps_tbl.c.branch == sa.bindparam('b_branch')))
                res = conn.execute(stmt, sourcestamps)
            else:
                res = conn.execute(stmt)

            rows = res.fetchall()

            lastBuilds = []
            if rows:
                brids = [r.id for r in rows]
                smt2 = sa.select(columns=[builds_tbl.c.number]).where(builds_tbl.c.brid.in_(brids))
                res = conn.execute(smt2)
                rows = res.fetchall()
                if rows:
                    lastBuilds = [row.number for row in rows]

            res.close()

            return lastBuilds

        return self.db.pool.do(thd)

    def _bdictFromRow(self, row):
        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)

        _bdict = dict(
            bid=row.id,
            brid=row.brid,
            number=row.number,
            start_time=mkdt(row.start_time),
            finish_time=mkdt(row.finish_time))
        if 'results' in row.keys():
            _bdict['results'] = row.results
        return _bdict
