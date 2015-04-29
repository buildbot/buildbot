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

            lastBuilds = []
            maxSearch = num_builds if num_builds < 200 else 200

            q = sa.select(columns=[buildrequests_tbl.c.id, builds_tbl.c.number],
                          from_obj=buildrequests_tbl.join(builds_tbl,
                                                          (buildrequests_tbl.c.id == builds_tbl.c.brid)))\
                .where(buildrequests_tbl.c.complete == 1)\
                .where(buildrequests_tbl.c.buildername == buildername)

            if sourcestamps and len(sourcestamps) > 0:
                # check that sourcestampset match all branches x codebases
                clauses = []
                exclude_clauses = []
                for ss in sourcestamps:
                    stmt_include = sa.select([sourcestamps_tbl.c.sourcestampsetid]) \
                        .where(sourcestamps_tbl.c.sourcestampsetid ==  sourcestampsets_tbl.c.id ) \
                        .where(sourcestamps_tbl.c.codebase == ss['b_codebase'])\
                        .where(sourcestamps_tbl.c.branch == ss['b_branch'])
                    clauses.append(sourcestampsets_tbl.c.id == stmt_include)

                    if len(sourcestamps) > 1:
                        stmt_exclude = sa.select([sourcestamps_tbl.c.sourcestampsetid]) \
                            .where(sourcestamps_tbl.c.sourcestampsetid ==  sourcestampsets_tbl.c.id) \
                            .where(sourcestamps_tbl.c.codebase == ss['b_codebase'])\
                            .where(sourcestamps_tbl.c.branch != ss['b_branch'])
                        exclude_clauses.append(sourcestampsets_tbl.c.id == stmt_exclude)

                stmt2 = sa.select(columns=[sourcestampsets_tbl.c.id]) \
                    .where(sa.or_(*clauses))

                stmt3 = sa.select(columns=[buildsets_tbl.c.id])\
                        .where(buildsets_tbl.c.sourcestampsetid.in_(stmt2))

                q = q.where(buildrequests_tbl.c.buildsetid.in_(stmt3))

                if len(sourcestamps) > 1:
                    stmt4 = sa.select(columns=[sourcestampsets_tbl.c.id])\
                        .where(sa.or_(*exclude_clauses))

                    stmt5 = sa.select(columns=[buildsets_tbl.c.id])\
                        .where(buildsets_tbl.c.sourcestampsetid.in_(stmt4))

                    q = q.where(~buildrequests_tbl.c.buildsetid.in_(stmt5))

            q = q.order_by(sa.desc(builds_tbl.c.number)).limit(maxSearch)

            res = conn.execute(q)

            rows = res.fetchall()
            if rows:
                for row in rows:
                    if row.number not in lastBuilds:
                        lastBuilds.append(row.number)

            res.close()

            return sorted(lastBuilds, reverse=True)

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
