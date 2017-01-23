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

import itertools

import sqlalchemy as sa

from twisted.internet import reactor
from twisted.python import log

from buildbot.db import NULL
from buildbot.db import base
from buildbot.process.results import RETRY
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime


class AlreadyClaimedError(Exception):
    pass


class NotClaimedError(Exception):
    pass


class BrDict(dict):
    pass


class BuildRequestsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst

    def _saSelectQuery(self):
        reqs_tbl = self.db.model.buildrequests
        claims_tbl = self.db.model.buildrequest_claims
        bsets_tbl = self.db.model.buildsets
        builder_tbl = self.db.model.builders
        bsss_tbl = self.db.model.buildset_sourcestamps
        sstamps_tbl = self.db.model.sourcestamps

        from_clause = reqs_tbl.outerjoin(claims_tbl,
                                         reqs_tbl.c.id == claims_tbl.c.brid)
        from_clause = from_clause.join(bsets_tbl,
                                       reqs_tbl.c.buildsetid == bsets_tbl.c.id)
        from_clause = from_clause.join(bsss_tbl,
                                       bsets_tbl.c.id == bsss_tbl.c.buildsetid)
        from_clause = from_clause.join(sstamps_tbl,
                                       bsss_tbl.c.sourcestampid == sstamps_tbl.c.id)
        from_clause = from_clause.join(builder_tbl,
                                       reqs_tbl.c.builderid == builder_tbl.c.id)

        return sa.select([reqs_tbl, claims_tbl, sstamps_tbl.c.branch,
                          sstamps_tbl.c.repository, sstamps_tbl.c.codebase, builder_tbl.c.name.label('buildername')]).select_from(from_clause)

    def getBuildRequest(self, brid):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            q = self._saSelectQuery()
            q = q.where(reqs_tbl.c.id == brid)
            res = conn.execute(q)
            row = res.fetchone()
            rv = None
            if row:
                rv = self._brdictFromRow(row, self.db.master.masterid)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def getBuildRequests(self, builderid=None, complete=None, claimed=None,
                         bsid=None, branch=None, repository=None, resultSpec=None):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            sstamps_tbl = self.db.model.sourcestamps
            q = self._saSelectQuery()
            if claimed is not None:
                if isinstance(claimed, bool):
                    if not claimed:
                        q = q.where(
                            (claims_tbl.c.claimed_at == NULL) &
                            (reqs_tbl.c.complete == 0))
                    else:
                        q = q.where(
                            (claims_tbl.c.claimed_at != NULL))
                else:
                    q = q.where(
                        (claims_tbl.c.masterid == claimed))
            if builderid is not None:
                q = q.where(reqs_tbl.c.builderid == builderid)
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

            if resultSpec is not None:
                return resultSpec.thd_execute(
                    conn, q,
                    lambda r: self._brdictFromRow(r, self.db.master.masterid))

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
                raise AlreadyClaimedError()

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
                    raise AlreadyClaimedError()

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
                except Exception:
                    transaction.rollback()
                    raise

            transaction.commit()
        return self.db.pool.do(thd)

    def completeBuildRequests(self, brids, results, complete_at=None,
                              _reactor=reactor):
        assert results != RETRY, "a buildrequest cannot be completed with a retry status!"
        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = _reactor.seconds()

        def thd(conn):
            transaction = conn.begin()

            # the update here is simple, but a number of conditions are
            # attached to ensure that we do not update a row inappropriately,
            # Note that checking that the request is mine would require a
            # subquery, so for efficiency that is not checked.

            reqs_tbl = self.db.model.buildrequests

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            for batch in self.doBatch(brids, 100):

                q = reqs_tbl.update()
                q = q.where(reqs_tbl.c.id.in_(batch))
                q = q.where(reqs_tbl.c.complete != 1)
                res = conn.execute(q,
                                   complete=1,
                                   results=results,
                                   complete_at=complete_at)

                # if an incorrect number of rows were updated, then we failed.
                if res.rowcount != len(batch):
                    log.msg("tried to complete %d buildrequests, "
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

        @d.addCallback
        def log_nonzero_count(count):
            if count != 0:
                log.msg("unclaimed %d expired buildrequests (over %d seconds "
                        "old)" % (count, old))
        return d

    @staticmethod
    def _brdictFromRow(row, master_masterid):
        claimed = False
        claimed_by_masterid = None
        claimed_at = None
        if row.claimed_at is not None:
            claimed_at = row.claimed_at
            claimed = True
            claimed_by_masterid = row.masterid

        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)
        submitted_at = mkdt(row.submitted_at)
        complete_at = mkdt(row.complete_at)
        claimed_at = mkdt(claimed_at)

        return BrDict(buildrequestid=row.id, buildsetid=row.buildsetid,
                      builderid=row.builderid, buildername=row.buildername,
                      priority=row.priority,
                      claimed=claimed, claimed_at=claimed_at,
                      claimed_by_masterid=claimed_by_masterid,
                      complete=bool(row.complete), results=row.results,
                      submitted_at=submitted_at, complete_at=complete_at,
                      waited_for=bool(row.waited_for))
