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

from buildbot.db import base
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime
from twisted.internet import reactor
from twisted.python import log


class AlreadyClaimedError(Exception):
    pass


class NotClaimedError(Exception):
    pass


class BrDict(dict):
    pass


class BuildRequestsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst

    def getBuildRequest(self, brid):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            res = conn.execute(sa.select([
                reqs_tbl.outerjoin(claims_tbl,
                                   (reqs_tbl.c.id == claims_tbl.c.brid))],
                whereclause=(reqs_tbl.c.id == brid)), use_labels=True)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._brdictFromRow(row, self.db.master.masterid)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def getBuildRequests(self, buildername=None, complete=None, claimed=None,
                         bsid=None, branch=None, repository=None):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            bsets_tbl = self.db.model.buildsets
            bsss_tbl = self.db.model.buildset_sourcestamps
            sstamps_tbl = self.db.model.sourcestamps

            from_clause = reqs_tbl.outerjoin(claims_tbl,
                                             reqs_tbl.c.id == claims_tbl.c.brid)

            # for branches, we need to join to the buildset and its
            # sourcestamps
            if branch or repository:
                from_clause = from_clause.join(bsets_tbl,
                                               reqs_tbl.c.buildsetid == bsets_tbl.c.id)
                from_clause = from_clause.join(bsss_tbl,
                                               bsets_tbl.c.id == bsss_tbl.c.buildsetid)
                from_clause = from_clause.join(sstamps_tbl,
                                               bsss_tbl.c.sourcestampid == sstamps_tbl.c.id)

            q = sa.select([reqs_tbl, claims_tbl]).select_from(from_clause)
            if claimed is not None:
                if not claimed:
                    q = q.where(
                        (claims_tbl.c.claimed_at == None) &
                        (reqs_tbl.c.complete == 0))
                elif claimed == "mine":
                    q = q.where(
                        (claims_tbl.c.masterid == self.db.master.masterid))
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
                q = q.where(sstamps_tbl.c.branch == branch)
            if repository is not None:
                q = q.where(sstamps_tbl.c.repository == repository)

            res = conn.execute(q)

            return [self._brdictFromRow(row, self.db.master.masterid)
                    for row in res.fetchall()]
        return self.db.pool.do(thd)

    def claimBuildRequests(self, brids, claimed_at=None, _reactor=reactor):
        if claimed_at is not None:
            claimed_at = datetime2epoch(claimed_at)
        else:
            claimed_at = _reactor.seconds()

        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.buildrequest_claims

            try:
                q = tbl.insert()
                conn.execute(q, [
                    dict(brid=id, masterid=self.db.master.masterid,
                         claimed_at=claimed_at)
                    for id in brids])
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                transaction.rollback()
                raise AlreadyClaimedError

            transaction.commit()

        return self.db.pool.do(thd)

    def reclaimBuildRequests(self, brids, _reactor=reactor):
        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.buildrequest_claims
            claimed_at = _reactor.seconds()

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            iterator = iter(brids)

            while True:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break  # success!

                q = tbl.update(tbl.c.brid.in_(batch)
                               & (tbl.c.masterid == self.db.master.masterid))
                res = conn.execute(q, claimed_at=claimed_at)

                # if fewer rows were updated than expected, then something
                # went wrong
                if res.rowcount != len(batch):
                    transaction.rollback()
                    raise AlreadyClaimedError

            transaction.commit()
        return self.db.pool.do(thd)

    def unclaimBuildRequests(self, brids):
        def thd(conn):
            transaction = conn.begin()
            claims_tbl = self.db.model.buildrequest_claims

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            iterator = iter(brids)

            while True:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break  # success!

                try:
                    q = claims_tbl.delete(
                        (claims_tbl.c.brid.in_(batch))
                        & (claims_tbl.c.masterid == self.db.master.masterid))
                    conn.execute(q)
                except:
                    transaction.rollback()
                    raise

            transaction.commit()
        return self.db.pool.do(thd)

    def completeBuildRequests(self, brids, results, complete_at=None,
                              _reactor=reactor):
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

            while True:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break  # success!

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
            expired_brids = sa.select([reqs_tbl.c.id],
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

    def _brdictFromRow(self, row, master_masterid):
        claimed = mine = False
        claimed_at = None
        if row.claimed_at is not None:
            claimed_at = row.claimed_at
            claimed = True
            mine = row.masterid == master_masterid

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
                      submitted_at=submitted_at, complete_at=complete_at,
                      waited_for=bool(row.waited_for))
