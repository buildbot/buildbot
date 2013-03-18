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
from twisted.internet import reactor
from twisted.python import log
from buildbot.db import base
from buildbot.util import epoch2datetime, datetime2epoch

class AlreadyClaimedError(Exception):
    pass

class NotClaimedError(Exception):
    pass

class BrDict(dict):
    pass

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
            bsid=None, _master_objectid=None, branch=None, repository=None):
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

            if branch is not None:
              q = q.where(sstamps_tbls.c.branch == branch)
            if repository is not None:
              q = q.where(sstamps_tbls.c.repository == repository)

            res = conn.execute(q)

            return [ self._brdictFromRow(row, _master_objectid)
                     for row in res.fetchall() ]
        return self.db.pool.do(thd)

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
    def unclaimBuildRequests(self, brids, _master_objectid=None):
        def thd(conn):
            transaction = conn.begin()
            claims_tbl = self.db.model.buildrequest_claims

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
                except:
                    transaction.rollback()
                    raise

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
        if row.claimed_at is not None:
            claimed_at = row.claimed_at
            claimed = True
            mine = row.objectid == master_objectid

        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)
        submitted_at = mkdt(row.submitted_at)
        complete_at = mkdt(row.complete_at)
        claimed_at = mkdt(row.claimed_at)

        return BrDict(brid=row.id, buildsetid=row.buildsetid,
                buildername=row.buildername, priority=row.priority,
                claimed=claimed, claimed_at=claimed_at, mine=mine,
                complete=bool(row.complete), results=row.results,
                submitted_at=submitted_at, complete_at=complete_at)
