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

import itertools
import sqlalchemy as sa
from sqlalchemy import or_
from sqlalchemy import func
from datetime import datetime, timedelta
from twisted.internet import reactor
from twisted.python import log
from buildbot.db import base
from buildbot.util import json
from buildbot.util import epoch2datetime, datetime2epoch
from buildbot.status.results import RESUME, CANCELED

class AlreadyClaimedError(Exception):
    pass

class NotClaimedError(Exception):
    pass

class UpdateBuildRequestError(Exception):
    pass

class UnsupportedQueueError(Exception):
    pass

class BrDict(dict):
    pass

def mkdt(epoch):
    if epoch:
        return epoch2datetime(epoch)

# private decorator to add a _master_objectid keyword argument, querying from
# the master
def with_master_objectid(fn):
    def wrap(self, *args, **kwargs):
        d = self.db.master.getObjectId()
        d.addCallback(lambda master_objectid :
                fn(self, _master_objectid=master_objectid, *args, **kwargs))
        return d
    wrap.__name__ = fn.__name__
    wrap.__doc__ = fn.__doc__
    return wrap

class BuildRequestsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    @with_master_objectid
    def getBuildRequest(self, brid, _master_objectid=None):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            res = conn.execute(sa.select([
                reqs_tbl.outerjoin(claims_tbl,
                                   (reqs_tbl.c.id == claims_tbl.c.brid)) ],
                whereclause=(reqs_tbl.c.id == brid)), use_labels=True)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._brdictFromRow(row, _master_objectid)
            res.close()
            return rv
        return self.db.pool.do(thd)

    @with_master_objectid
    def getBuildRequests(self, buildername=None, complete=None, claimed=None,
                         bsid=None, _master_objectid=None, brids=None,
                         branch=None, repository=None, results=None, mergebrids=None):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            bsets_tbl = self.db.model.buildsets
            sstamps_tbls = self.db.model.sourcestamps

            from_clause = reqs_tbl.outerjoin(claims_tbl,
                                             reqs_tbl.c.id == claims_tbl.c.brid)

            if branch or repository:
              from_clause = from_clause.join(bsets_tbl,
                                             reqs_tbl.c.buildsetid ==
                                             bsets_tbl.c.id)
              from_clause = from_clause.join(sstamps_tbls,
                                             bsets_tbl.c.sourcestampsetid ==
                                             sstamps_tbls.c.sourcestampsetid)

            q = sa.select([ reqs_tbl, claims_tbl ]).select_from(from_clause)

            if claimed is not None:
                if not claimed:
                    q = q.where(
                        (claims_tbl.c.claimed_at == None) &
                        (reqs_tbl.c.complete == 0))
                elif claimed == "mine":
                    q = q.where(
                        (claims_tbl.c.objectid == _master_objectid))
                else:
                    q = q.where(
                        (claims_tbl.c.claimed_at != None))

            if buildername is not None:
                q = q.where(reqs_tbl.c.buildername == buildername)

            if complete is not None:
                if complete:
                    q = q.where(reqs_tbl.c.complete != 0)
                else:
                    q = q.where(reqs_tbl.c.complete == 0)

            if bsid is not None:
                q = q.where(reqs_tbl.c.buildsetid == bsid)

            if brids is not None:
                q = q.where(reqs_tbl.c.id.in_(brids))

            if results is not None:
                q = q.where(reqs_tbl.c.results == results)

            if mergebrids is not None:
                if mergebrids == "exclude":
                    q = q.where(reqs_tbl.c.mergebrid == None)
                else:
                    q = q.where(reqs_tbl.c.mergebrid.in_(mergebrids))

            if branch is not None:
              q = q.where(sstamps_tbls.c.branch == branch)

            if repository is not None:
              q = q.where(sstamps_tbls.c.repository == repository)

            res = conn.execute(q)

            return [ self._brdictFromRow(row, _master_objectid)
                     for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def getTotalBuildsInTheLastDay(self):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            yesterday = datetime.now().date() - timedelta(1)
            beforeyesterday = datetime.now().date() - timedelta(2)
            yesterday_epoch = datetime2epoch(datetime(yesterday.year, yesterday.month, yesterday.day))
            beforeyesterday_epoch = datetime2epoch(datetime(beforeyesterday.year, beforeyesterday.month, beforeyesterday.day))
            query = sa.select([func.count(reqs_tbl.c.id).label("totalbuilds")])\
                .where(reqs_tbl.c.complete_at >= beforeyesterday_epoch)\
                .where(reqs_tbl.c.complete_at <= yesterday_epoch)\
                .where(reqs_tbl.c.complete == 1)\
                .where(reqs_tbl.c.mergebrid == None)\
                .where(reqs_tbl.c.artifactbrid == None)

            res = conn.execute(query)
            row = res.fetchone()
            return row.totalbuilds

        return self.db.pool.do(thd)


    @with_master_objectid
    def getBuildRequestInQueue(self, brids=None, buildername=None,
                               _master_objectid=None, sorted=False, limit=False):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims

            def checkConditions(query):
                if buildername:
                    query = query.where(reqs_tbl.c.buildername == buildername)

                if brids:
                    query = query.where(reqs_tbl.c.id.in_(brids))

                if limit:
                    query = query.limit(200)

                if sorted:
                    query = query.order_by(sa.desc(reqs_tbl.c.priority), sa.asc(reqs_tbl.c.submitted_at))

                return query

            def getResults(query):
                rv = []
                res = conn.execute(query)
                rows = res.fetchall()

                if rows:
                    for row in rows:
                        rv.append(self._brdictFromRow(row, _master_objectid))

                res.close()
                return rv

            pending = sa.select([reqs_tbl],
                          from_obj=reqs_tbl.outerjoin(claims_tbl, (reqs_tbl.c.id == claims_tbl.c.brid)),
                          whereclause=((claims_tbl.c.claimed_at == None) &
                                       (reqs_tbl.c.complete == 0)))

            pending = checkConditions(pending)

            resume = sa.select([reqs_tbl],
                               from_obj=reqs_tbl.join(claims_tbl, (reqs_tbl.c.id == claims_tbl.c.brid)
                                                      & (claims_tbl.c.objectid == _master_objectid)))\
                .where(reqs_tbl.c.results == RESUME)\
                .where(reqs_tbl.c.mergebrid == None)

            resume = checkConditions(resume)
            buildqueue = pending.alias('pending').select().union_all(resume.alias('resume').select())


            result = getResults(buildqueue)

            return result

        return self.db.pool.do(thd)

    @with_master_objectid
    def getPrioritizedBuildRequestsInQueue(self, buildername, queue=None, _master_objectid=None):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            buildset_properties_tbl = self.db.model.buildset_properties

            pending = sa.select([reqs_tbl.c.buildername, reqs_tbl.c.priority,
                                 reqs_tbl.c.submitted_at, reqs_tbl.c.results,
                                 buildset_properties_tbl.c.property_value,
                                 reqs_tbl.c.slavepool],
                          from_obj=reqs_tbl.outerjoin(claims_tbl, (reqs_tbl.c.id == claims_tbl.c.brid))
                                .outerjoin(buildset_properties_tbl,
                                      (buildset_properties_tbl.c.buildsetid == reqs_tbl.c.buildsetid)
                                           & (buildset_properties_tbl.c.property_name == 'selected_slave')),
                          whereclause=((claims_tbl.c.claimed_at == None) &
                                       (reqs_tbl.c.complete == 0)))\
                .where(reqs_tbl.c.buildername == buildername)\
                .order_by(sa.desc(reqs_tbl.c.priority), sa.asc(reqs_tbl.c.submitted_at))

            resumebuilds = sa.select([reqs_tbl.c.buildername, reqs_tbl.c.priority,
                                      reqs_tbl.c.submitted_at, reqs_tbl.c.results,
                                      buildset_properties_tbl.c.property_value,
                                      reqs_tbl.c.slavepool],
                               from_obj=reqs_tbl.join(claims_tbl,
                                                      (reqs_tbl.c.id == claims_tbl.c.brid)
                                                      & (claims_tbl.c.objectid == _master_objectid))
                                     .outerjoin(buildset_properties_tbl,
                                                (buildset_properties_tbl.c.buildsetid == reqs_tbl.c.buildsetid)
                                                & (buildset_properties_tbl.c.property_name == 'selected_slave')))\
                .where(reqs_tbl.c.results == RESUME)\
                .where(reqs_tbl.c.mergebrid == None)\
                .where(reqs_tbl.c.buildername == buildername)\
                .order_by(sa.desc(reqs_tbl.c.priority), sa.asc(reqs_tbl.c.submitted_at))

            if queue is None:
                buildersqueue = pending.alias('pending').select().union_all(resumebuilds.alias('resume').select())

            elif queue == 'unclaimed':
                buildersqueue = pending

            elif queue == 'resume':
                buildersqueue = resumebuilds

            else:
                raise UnsupportedQueueError

            res = conn.execute(buildersqueue)
            rows = res.fetchall()
            rv = []

            def getSelectedSlave(row):
                return json.loads(row.property_value)[0] if row.property_value and len(row.property_value) > 0 else None

            for row in rows:
                if row:
                    rv.append(dict(buildername=row.buildername,
                                   priority=row.priority,
                                   submitted_at=mkdt(row.submitted_at),
                                   results=row.results,
                                   selected_slave=getSelectedSlave(row),
                                   slavepool=row.slavepool))

            return rv

        return self.db.pool.do(thd)

    def getBuildRequestBySourcestamps(self, buildername=None, sourcestamps=None):
        def thd(conn):
            sourcestampsets_tbl = self.db.model.sourcestampsets
            sourcestamps_tbl = self.db.model.sourcestamps
            buildrequests_tbl = self.db.model.buildrequests
            buildsets_tbl = self.db .model.buildsets
            clauses = []

            # check sourcestampset has same number of row in the sourcestamps table
            stmt = sa.select([sourcestamps_tbl.c.sourcestampsetid]) \
                .where(sourcestamps_tbl.c.sourcestampsetid == sourcestampsets_tbl.c.id) \
                .group_by(sourcestamps_tbl.c.sourcestampsetid) \
                .having(sa.func.count(sourcestamps_tbl.c.id) == len(sourcestamps))

            clauses.append(sourcestampsets_tbl.c.id == stmt)
            clauses.append(sourcestampsets_tbl.c.id != sourcestamps[0]['b_sourcestampsetid'])

            # check that sourcestampset match all revisions x codebases
            for ss in sourcestamps:
                stmt_temp = sa.select([sourcestamps_tbl.c.sourcestampsetid]) \
                    .where(sourcestamps_tbl.c.sourcestampsetid ==  sourcestampsets_tbl.c.id ) \
                    .where(sourcestamps_tbl.c.codebase == ss['b_codebase']) \
                    .where(sourcestamps_tbl.c.revision == ss['b_revision'])\
                    .where(sourcestamps_tbl.c.branch == ss['b_branch'])
                clauses.append(sourcestampsets_tbl.c.id == stmt_temp)

            stmt2 = sa.select(columns=[sourcestampsets_tbl.c.id]) \
                .where(sa.and_(*clauses))

            stmt3 = sa.select(columns=[buildsets_tbl.c.id])\
                        .where(buildsets_tbl.c.sourcestampsetid.in_(stmt2))

            last_br = sa.select(columns=[sa.func.max(buildrequests_tbl.c.id).label("id")])\
                    .where(buildrequests_tbl.c.buildsetid.in_(stmt3))\
                    .where(buildrequests_tbl.c.complete == 1)\
                    .where(buildrequests_tbl.c.results == 0)\
                    .where(buildrequests_tbl.c.buildername == buildername)\
                    .where(buildrequests_tbl.c.artifactbrid == None)

            q = sa.select(columns=[buildrequests_tbl])\
                .where(buildrequests_tbl.c.id == last_br)

            res = conn.execute(q)
            row = res.fetchone()
            buildrequest = None
            if row:
                submitted_at = mkdt(row.submitted_at)
                complete_at = mkdt(row.complete_at)
                buildrequest = dict(brid=row.id, buildsetid=row.buildsetid,
                      buildername=row.buildername, priority=row.priority,
                      complete=bool(row.complete), results=row.results,
                      submitted_at=submitted_at, complete_at=complete_at, artifactbrid=row.artifactbrid)

            res.close()
            return buildrequest
        return self.db.pool.do(thd)

    def reusePreviousBuild(self, requests, artifactbrid):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

            brids = [br.id for br in requests]
            stmt = buildrequests_tbl.update()\
                .where(buildrequests_tbl.c.id.in_(brids))\
                .values(artifactbrid=artifactbrid)

            res = conn.execute(stmt)
            return res.rowcount

        return self.db.pool.do(thd)

    def updateMergedBuildRequest(self, requests):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

            mergedrequests = [br.id for br in requests[1:]]

            if len(mergedrequests) > 0:
                stmt2 = buildrequests_tbl.update() \
                    .where(buildrequests_tbl.c.id.in_(mergedrequests))\
                    .values(artifactbrid=requests[0].id)

                res = conn.execute(stmt2)
                return res.rowcount

        return self.db.pool.do(thd)

    @with_master_objectid
    def mergeBuildingRequest(self, requests, brids, number, claim=True, _reactor=reactor, _master_objectid=None):
        def thd(conn):
            transaction = conn.begin()
            try:
                if claim:
                    claimed_at = self.getClaimedAtValue(_reactor)
                    self.insertBuildRequestClaimsTable(conn, _master_objectid, brids, claimed_at)
                self.addBuilds(conn, brids, number)
                self.executeMergeBuildingRequests(conn, requests)
            except:
                transaction.rollback()
                raise

            transaction.commit()

        return self.db.pool.do(thd)

    def maybeUpdateMergedBrids(self, brids):
        def thd(conn):
            transaction = conn.begin()
            try:
                if len(brids) > 1:
                    buildrequests_tbl = self.db.model.buildrequests

                    q = sa.select([buildrequests_tbl.c.artifactbrid])\
                    .where(buildrequests_tbl.c.id == brids[0])
                    res = conn.execute(q)
                    row = res.fetchone()

                    artifactbrid = row.artifactbrid if row and (row.artifactbrid is not None) else brids[0]

                    stmt_brids = sa.select([buildrequests_tbl.c.id])\
                        .where(buildrequests_tbl.c.mergebrid == brids[0])\
                        .where(or_((buildrequests_tbl.c.artifactbrid != artifactbrid),
                                   (buildrequests_tbl.c.artifactbrid == None)))

                    res = conn.execute(stmt_brids)
                    rows = res.fetchall()
                    mergedrequests = [row.id for row in rows]
                    res.close()

                    if len(mergedrequests) > 0:
                        stmt2 = buildrequests_tbl.update()\
                            .where(buildrequests_tbl.c.id.in_(mergedrequests))\
                            .values(artifactbrid=artifactbrid)
                        conn.execute(stmt2)

            except:
                transaction.rollback()
                raise

            transaction.commit()

        return self.db.pool.do(thd)

    def executeMergeBuildingRequests(self, conn, requests):
            buildrequests_tbl = self.db.model.buildrequests
            mergedrequests = [br.id for br in requests[1:]]

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't
            iterator = iter(mergedrequests)
            batch = list(itertools.islice(iterator, 100))
            while len(batch) > 0:
                q = sa.select([buildrequests_tbl.c.artifactbrid]) \
                    .where(id == requests[0].id)
                res = conn.execute(q)
                row = res.fetchone()
                # by default it will mark using artifact generated from merged brid
                stmt2 = buildrequests_tbl.update() \
                    .where(buildrequests_tbl.c.id.in_(mergedrequests)) \
                    .values(artifactbrid=requests[0].id)\
                    .values(mergebrid=requests[0].id)

                if row and (row.artifactbrid is not None):
                    stmt2 = buildrequests_tbl.update() \
                    .where(buildrequests_tbl.c.id.in_(mergedrequests)) \
                    .values(artifactbrid=row.artifactbrid)\
                    .values(mergebrid=requests[0].id)
                conn.execute(stmt2)
                batch = list(itertools.islice(iterator, 100))

    def findCompatibleFinishedBuildRequest(self, buildername, startbrid):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

            q = sa.select([buildrequests_tbl]) \
                .where(buildrequests_tbl.c.startbrid == startbrid) \
                .where(buildrequests_tbl.c.buildername == buildername) \
                .where(buildrequests_tbl.c.complete == 1)

            res = conn.execute(q)
            row = res.fetchone()
            rv = None
            if row:
                rv = self._brdictFromRow(row, None)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def getRequestsCompatibleToMerge(self, buildername, startbrid, compatible_brids):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

            stmt = sa.select([buildrequests_tbl.c.id]) \
                .where(buildrequests_tbl.c.id.in_(compatible_brids)) \
                .where(buildrequests_tbl.c.buildername == buildername)\
                .where(buildrequests_tbl.c.startbrid == startbrid)

            res = conn.execute(stmt)
            rows = res.fetchall()
            merged_brids = [row.id for row in rows]

            res.close()
            return merged_brids
        return self.db.pool.do(thd)

    def executeMergeFinishedBuildRequest(self, conn, brdict, merged_brids):
        buildrequests_tbl = self.db.model.buildrequests

        completed_at = datetime2epoch(brdict['complete_at'])
        # we'll need to batch the brids into groups of 100, so that the
        # parameter lists supported by the DBAPI aren't
        iterator = iter(merged_brids)
        batch = list(itertools.islice(iterator, 100))
        while len(batch) > 0:
            stmt2 = buildrequests_tbl.update() \
                .where(buildrequests_tbl.c.id.in_(batch)) \
                .values(complete = 1) \
                .values(results=brdict['results']) \
                .values(mergebrid=brdict['brid']) \
                .values(complete_at = completed_at)

            if brdict['artifactbrid'] is None:
                stmt2 = stmt2.values(artifactbrid=brdict['brid'])
            else:
                stmt2 = stmt2.values(artifactbrid=brdict['artifactbrid'])
            conn.execute(stmt2)
            batch = list(itertools.islice(iterator, 100))

    def addFinishedBuilds(self, conn, brdict, merged_brids):
        builds_tbl = self.db.model.builds
        stmt3 = sa.select([builds_tbl.c.number,  builds_tbl.c.start_time, builds_tbl.c.finish_time],
                          order_by = [sa.desc(builds_tbl.c.number)]) \
            .where(builds_tbl.c.brid == brdict['brid'])

        res = conn.execute(stmt3)
        row = res.fetchone()
        if row:
            stmt4 = builds_tbl.insert()
            conn.execute(stmt4, [ dict(number=row.number, brid=br,
                                       start_time=row.start_time,finish_time=row.finish_time)
                                  for br in merged_brids ])
        res.close()

    @with_master_objectid
    def mergeFinishedBuildRequest(self, brdict, merged_brids, claim=True,
                                      _reactor=reactor, _master_objectid=None):
        def thd(conn):
            transaction = conn.begin()
            try:
                if claim:
                    claimed_at = self.getClaimedAtValue(_reactor)
                    self.insertBuildRequestClaimsTable(conn, _master_objectid, merged_brids, claimed_at)
                # build request will have same properties so we skip checking it
                self.executeMergeFinishedBuildRequest(conn, brdict, merged_brids)
                # insert builds
                self.addFinishedBuilds(conn, brdict, merged_brids)
            except:
                transaction.rollback()
                raise

            transaction.commit()
        return self.db.pool.do(thd)

    @with_master_objectid
    def mergePendingBuildRequests(self, brids, artifactbrid=None, claim=True, _reactor=reactor, _master_objectid=None):
        def thd(conn):
            transaction = conn.begin()
            try:
                buildrequests_tbl = self.db.model.buildrequests
                claimed_at = self.getClaimedAtValue(_reactor)
                if claim:
                    self.insertBuildRequestClaimsTable(conn, _master_objectid, brids, claimed_at)
                # we'll need to batch the brids into groups of 100, so that the
                # parameter lists supported by the DBAPI aren't
                iterator = iter(brids[1:])
                batch = list(itertools.islice(iterator, 100))
                while len(batch) > 0:

                    stmt = buildrequests_tbl.update()\
                        .where(sa.or_(buildrequests_tbl.c.id.in_(batch), buildrequests_tbl.c.mergebrid.in_(batch)))\
                        .values(mergebrid=brids[0])

                    if artifactbrid is not None:
                        stmt_br = sa.select([buildrequests_tbl.c.artifactbrid])\
                            .where(buildrequests_tbl.c.id==brids[0])
                        res = conn.execute(stmt_br)
                        row = res.fetchone()
                        stmt = stmt.values(artifactbrid=row.artifactbrid if row and row.artifactbrid else artifactbrid)

                    conn.execute(stmt)
                    batch = list(itertools.islice(iterator, 100))

            except:
                transaction.rollback()
                raise
            transaction.commit()

        return self.db.pool.do(thd)

    def getBuildRequestTriggered(self, triggeredbybrid, buildername):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

            stmt_br = sa.select([buildrequests_tbl]) \
                .where(buildrequests_tbl.c.buildername == buildername) \
                .where(buildrequests_tbl.c.triggeredbybrid == triggeredbybrid)

            res = conn.execute(stmt_br)
            row = res.fetchone()
            buildrequest = None
            if row:
                if row.artifactbrid:
                    stmt = sa.select([buildrequests_tbl]) \
                        .where(buildrequests_tbl.c.id == row.artifactbrid)
                    res = conn.execute(stmt)
                    br_row = res.fetchone()
                    if br_row:
                        row = br_row

                submitted_at = mkdt(row.submitted_at)
                complete_at = mkdt(row.complete_at)
                buildrequest = dict(brid=row.id, buildsetid=row.buildsetid,
                                    buildername=row.buildername, priority=row.priority,
                                    complete=bool(row.complete), results=row.results,
                                    submitted_at=submitted_at, complete_at=complete_at, artifactbrid=row.artifactbrid)

            res.close()
            return buildrequest

        return self.db.pool.do(thd)

    def getBuildRequestsTriggeredByScheduler(self, schedulername, stepname, triggeredbybrid):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests
            buildset_properties_tbl = self.db.model.buildset_properties

            clauses = []
            property_filter = [{'property_name': 'scheduler',
                                'property_value': '["'+schedulername+'", "Scheduler"]'},
                               {'property_name': 'stepname',
                                'property_value': '["'+stepname+'", "Trigger"]'}]

            for prop in property_filter:
                stmt = sa.select([buildrequests_tbl.c.id],
                                 from_obj=buildrequests_tbl
                                 .join(buildset_properties_tbl,
                                       (buildset_properties_tbl.c.buildsetid == buildrequests_tbl.c.buildsetid)))\
                    .where(buildrequests_tbl.c.triggeredbybrid == triggeredbybrid)\
                    .where(buildset_properties_tbl.c.property_name == prop['property_name'])\
                    .where(buildset_properties_tbl.c.property_value == prop['property_value'])
                clauses.append(buildrequests_tbl.c.id.in_(stmt))

            stmt_br = sa.select([buildrequests_tbl.c.id, buildrequests_tbl.c.buildsetid, buildrequests_tbl.c.buildername])\
                .where(sa.and_(*clauses))\
                .where(buildrequests_tbl.c.triggeredbybrid == triggeredbybrid)

            res = conn.execute(stmt_br)
            brids = {}
            bsid = None
            rows = res.fetchall()
            for row in rows:
                if bsid is None:
                    bsid = row.buildsetid

                brids[row.buildername] = row.id

            res.close()
            return (bsid, brids)

        return self.db.pool.do(thd)

    @with_master_objectid
    def getBuildRequestBuildChain(self, startbrid, _master_objectid=None):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            builds_tbl = self.db.model.builds
            claims_tbl = self.db.model.buildrequest_claims
            rv = []

            if startbrid:
                pending = sa.select([reqs_tbl.c.id, builds_tbl.c.number, reqs_tbl.c.results, reqs_tbl.c.buildername],
                      from_obj=reqs_tbl.outerjoin(builds_tbl, (reqs_tbl.c.id == builds_tbl.c.brid)),
                      whereclause=(reqs_tbl.c.startbrid == startbrid) &
                                   (reqs_tbl.c.complete == 0) & (reqs_tbl.c.mergebrid == None))\
                    .order_by(reqs_tbl.c.submitted_at)

                resume = sa.select([reqs_tbl.c.id, builds_tbl.c.number, reqs_tbl.c.results, reqs_tbl.c.buildername],
                                   from_obj=reqs_tbl.join(claims_tbl, (reqs_tbl.c.id == claims_tbl.c.brid)
                                                      & (claims_tbl.c.objectid == _master_objectid))
                                   .join(builds_tbl, (reqs_tbl.c.id == builds_tbl.c.brid)))\
                    .where(reqs_tbl.c.startbrid == startbrid)\
                    .where(reqs_tbl.c.results == RESUME)\
                    .where(reqs_tbl.c.complete == 1)\
                    .where(reqs_tbl.c.mergebrid == None)\
                    .order_by(reqs_tbl.c.submitted_at)

                buildrequests = pending.alias('pending').select().union_all(resume.alias('resume').select())

                res = conn.execute(buildrequests)
                rows = res.fetchall()
                if rows:
                    for row in rows:
                        rv.append(dict(brid=row.id, results=row.results, number=row.number,
                                   buildername=row.buildername))
                res.close()

            return rv

        return self.db.pool.do(thd)

    def insertBuildRequestClaimsTable(self, conn, _master_objectid, brids, claimed_at=None):
        tbl = self.db.model.buildrequest_claims
        q = tbl.insert()
        conn.execute(q, [dict(brid=id, objectid=_master_objectid,
                              claimed_at=claimed_at)
                         for id in brids])

    def getClaimedAtValue(self, _reactor, claimed_at=None):
        if claimed_at is not None:
            claimed_at = datetime2epoch(claimed_at)
        else:
            claimed_at = _reactor.seconds()
        return claimed_at

    @with_master_objectid
    def claimBuildRequests(self, brids, claimed_at=None, _reactor=reactor,
                            _master_objectid=None):
        if claimed_at is not None:
            claimed_at = datetime2epoch(claimed_at)
        else:
            claimed_at = _reactor.seconds()

        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.buildrequest_claims

            try:
                q = tbl.insert()
                conn.execute(q, [ dict(brid=id, objectid=_master_objectid,
                                    claimed_at=claimed_at)
                                  for id in brids ])
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                transaction.rollback()
                raise AlreadyClaimedError

            transaction.commit()

        return self.db.pool.do(thd)

    def addBuilds(self, conn, brids, number, _reactor=reactor):
        builds_tbl = self.db.model.builds
        start_time = _reactor.seconds()
        q = builds_tbl.insert()
        conn.execute(q, [ dict(number=number, brid=id,
                               start_time=start_time,finish_time=None)
                          for id in brids ])

    @with_master_objectid
    def reclaimBuildRequests(self, brids, _reactor=reactor,
                            _master_objectid=None):
        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.buildrequest_claims
            claimed_at = _reactor.seconds()

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            iterator = iter(brids)

            while 1:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break # success!

                q = tbl.update(tbl.c.brid.in_(batch)
                                & (tbl.c.objectid==_master_objectid))
                res = conn.execute(q, claimed_at=claimed_at)

                # if fewer rows were updated than expected, then something
                # went wrong
                if res.rowcount != len(batch):
                    transaction.rollback()
                    raise AlreadyClaimedError

            transaction.commit()
        return self.db.pool.do(thd)

    @with_master_objectid
    def unclaimBuildRequests(self, brids, results=None, _master_objectid=None):
        def thd(conn):
            transaction = conn.begin()
            claims_tbl = self.db.model.buildrequest_claims
            req_tbl = self.db.model.buildrequests

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            iterator = iter(brids)

            while 1:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break # success!

                try:
                    q = claims_tbl.delete(
                            (claims_tbl.c.brid.in_(batch))
                            & (claims_tbl.c.objectid == _master_objectid))
                    conn.execute(q)

                    q = req_tbl.update(req_tbl.c.id.in_(batch)).values(mergebrid=None)

                    if results is not None:
                        q = q.values(results=results)

                    conn.execute(q)
                except:
                    transaction.rollback()
                    raise

            transaction.commit()
        return self.db.pool.do(thd)

    def cancelResumeBuildRequests(self, brid):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

            transaction = conn.begin()
            try:
                stmt = sa.select([buildrequests_tbl.c.id])\
                    .where(or_(buildrequests_tbl.c.id == brid, buildrequests_tbl.c.mergebrid == brid))\
                    .where(buildrequests_tbl.c.results == RESUME).order_by(buildrequests_tbl.c.id)

                res = conn.execute(stmt)
                rows = res.fetchall()
                brids = [row.id for row in rows]
                res.close()

                if brids:
                    q = buildrequests_tbl.update().where(buildrequests_tbl.c.id.in_(brids))\
                        .values(complete=1).values(results=CANCELED)

                    conn.execute(q)
            except:
                transaction.rollback()
                log.msg("build request already started; cannot cancel")
                return

            transaction.commit()
        return self.db.pool.do(thd)


    def updateBuildRequests(self, brids, results=None, complete=None, slavepool=None):
        def thd(conn):

            transaction = conn.begin()
            buildrequests_tbl = self.db.model.buildrequests

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            iterator = iter(brids)

            while 1:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break # success!

                q = buildrequests_tbl.update()\
                    .where(buildrequests_tbl.c.id.in_(batch))

                if results:
                    q = q.values(results=results)

                if slavepool:
                    q = q.values(slavepool=slavepool)

                if complete:
                    q = q.values(complete=complete)

                if complete == 0:
                    q = q.values(complete_at=None)

                res = conn.execute(q)

                # if an incorrect number of rows were updated, then we failed.
                if res.rowcount != len(batch):
                    log.msg("tried to update %d buildreqests, "
                        "but only updated %d" % (len(batch), res.rowcount))
                    transaction.rollback()
                    raise UpdateBuildRequestError
            transaction.commit()
        return self.db.pool.do(thd)


    @with_master_objectid
    def completeBuildRequests(self, brids, results, complete_at=None,
                            _reactor=reactor, _master_objectid=None):
        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = _reactor.seconds()

        def thd(conn):
            transaction = conn.begin()

            # the update here is simple, but a number of conditions are
            # attached to ensure that we do not update a row inappropriately,
            # Note that checking that the request is mine would require a
            # subquery, so for efficiency that is not checed.

            reqs_tbl = self.db.model.buildrequests

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            iterator = iter(brids)

            while 1:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break # success!

                q = reqs_tbl.update()
                q = q.where(reqs_tbl.c.id.in_(batch))
                q = q.where(reqs_tbl.c.complete != 1)
                res = conn.execute(q,
                    complete=1,
                    results=results,
                    complete_at=complete_at)

                # if an incorrect number of rows were updated, then we failed.
                if res.rowcount != len(batch):
                    log.msg("tried to complete %d buildreqests, "
                        "but only completed %d" % (len(batch), res.rowcount))
                    transaction.rollback()
                    raise NotClaimedError
            transaction.commit()
        return self.db.pool.do(thd)

    def unclaimExpiredRequests(self, old, _reactor=reactor):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            old_epoch = _reactor.seconds() - old

            # select any expired requests, and delete each one individually
            expired_brids = sa.select([ reqs_tbl.c.id ],
                        whereclause=(reqs_tbl.c.complete != 1))
            res = conn.execute(claims_tbl.delete(
                        (claims_tbl.c.claimed_at < old_epoch) &
                        claims_tbl.c.brid.in_(expired_brids)))
            return res.rowcount
        d = self.db.pool.do(thd)
        def log_nonzero_count(count):
            if count != 0:
                log.msg("unclaimed %d expired buildrequests (over %d seconds "
                        "old)" % (count, old))
        d.addCallback(log_nonzero_count)
        return d

    def _brdictFromRow(self, row, master_objectid):
        claimed = mine = False
        claimed_at = None

        if 'claimed_at' in row.keys() and row.claimed_at is not None:
            claimed_at = row.claimed_at
            claimed = True
            mine = row.objectid == master_objectid

        submitted_at = mkdt(row.submitted_at)
        complete_at = mkdt(row.complete_at)
        claimed_at = mkdt(claimed_at)

        return BrDict(brid=row.id, buildsetid=row.buildsetid,
                buildername=row.buildername, priority=row.priority,
                claimed=claimed, claimed_at=claimed_at, mine=mine,
                complete=bool(row.complete), results=row.results,
                submitted_at=submitted_at, complete_at=complete_at,
                artifactbrid=row.artifactbrid, triggeredbybrid = row.triggeredbybrid,
                mergebrid=row.mergebrid, startbrid=row.startbrid, slavepool=row.slavepool)
