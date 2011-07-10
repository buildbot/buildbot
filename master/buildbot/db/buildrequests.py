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

"""
Support for buildsets in the database
"""

import itertools
import sqlalchemy as sa
from twisted.internet import reactor
from twisted.python import log
from buildbot.db import base
from buildbot.util import epoch2datetime

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
                fn(self, *args, _master_objectid=master_objectid, **kwargs))
        return d
    wrap.__name__ = fn.__name__
    wrap.__doc__ = fn.__doc__
    return wrap

class BuildRequestsConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle buildrequests.  An instance is available
    at C{master.db.buildrequests}.

    Build Requests are represented as dictionaries with keys C{brid},
    C{buildsetid}, C{buildername}, C{priority}, C{claimed} (boolean),
    C{claimed_at}, C{mine} (boolean), C{complete}, C{results}, C{submitted_at},
    and C{complete_at}.  The two time parameters (C{*_at}) are presented as
    datetime objects.
    """

    @with_master_objectid
    def getBuildRequest(self, brid, _master_objectid=None):
        """
        Get a single BuildRequest, in the format described above.  Returns
        C{None} if there is no such buildrequest.

        Note that build requests are not cached, as the values in the database
        are not fixed.

        @param brid: build request id
        @type brid: integer

        @returns: Build request dictionary as above or None, via Deferred
        """
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            res = conn.execute(sa.select([
                reqs_tbl.outerjoin(claims_tbl,
                                   (reqs_tbl.c.id == claims_tbl.c.brid)) ],
                whereclause=(reqs_tbl.c.id == brid)))
            row = res.fetchone()

            rv = None
            if row:
                rv = self._brdictFromRow(row, _master_objectid)
            res.close()
            return rv
        return self.db.pool.do(thd)

    @with_master_objectid
    def getBuildRequests(self, buildername=None, complete=None, claimed=None,
            bsid=None, _master_objectid=None):
        """
        Get a list of build requests matching the given characteristics.  Note
        that C{unclaimed}, C{my_claimed}, and C{other_claimed} all default to
        C{False}, so at least one must be provided or no results will be
        returned.

        The C{claimed} parameter can be C{None} (the default) to ignore the
        claimed status of requests; C{True} to return only claimed builds,
        C{False} to return only unclaimed builds, or C{"mine"} to return only
        builds claimed by this master instance.  A request is considered
        unclaimed if its C{claimed_at} column is either NULL or 0, and it is
        not complete.  If C{bsid} is specified, then only build requests for
        that buildset will be returned.

        A build is considered completed if its C{complete} column is 1; the
        C{complete_at} column is not consulted.

        Since this method is often used to detect changed build requests, it
        always bypasses the cache.

        @param buildername: limit results to buildrequests for this builder
        @type buildername: string

        @param complete: if true, limit to completed buildrequests; if false,
        limit to incomplete buildrequests; if None, do not limit based on
        completion.

        @param claimed: see above

        @param bsid: see above

        @returns: List of build request dictionaries as above, via Deferred
        """
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            q = sa.select([ reqs_tbl.outerjoin(claims_tbl,
                                    reqs_tbl.c.id == claims_tbl.c.brid) ])
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
            res = conn.execute(q)

            return [ self._brdictFromRow(row, _master_objectid)
                     for row in res.fetchall() ]
        return self.db.pool.do(thd)

    @with_master_objectid
    def claimBuildRequests(self, brids, _reactor=reactor,
                            _master_objectid=None):
        """
        Try to "claim" the indicated build requests for this buildmaster
        instance.  The resulting deferred will fire normally on success, or
        fail with L{AleadyClaimedError} if I{any} of the build requests are
        already claimed by another master instance.  In this case, none of the
        claims will take effect.

        As of 0.8.5, this method can no longer be used to re-claim build
        requests.  All given brids must be unclaimed.  Use
        L{reclaimBuildRequests} to reclaim.

        On database backends that do not enforce referential integrity (e.g.,
        SQLite), this method will not prevent claims for nonexistent build
        requests.  On database backends that do not support transactions
        (MySQL), this method will not properly roll back any partial claims
        made before an L{AlreadyClaimedError} was generated.

        @param brids: ids of buildrequests to claim
        @type brids: list

        @param _reactor: reactor to use (for testing)

        @returns: Deferred
        """

        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.buildrequest_claims

            try:
                q = tbl.insert()
                claimed_at = _reactor.seconds()
                conn.execute(q, [ dict(brid=id, objectid=_master_objectid,
                                    claimed_at=claimed_at)
                                  for id in brids ])
            except sa.exc.IntegrityError:
                transaction.rollback()
                raise AlreadyClaimedError

            transaction.commit()

        return self.db.pool.do(thd)

    @with_master_objectid
    def reclaimBuildRequests(self, brids, _reactor=reactor,
                            _master_objectid=None):
        """
        Re-claim the given build requests, updating the timestamp, but checking
        that the requsts are owned by this master.  The resulting deferred will
        fire normally on success, or fail with L{AleadyClaimedError} if I{any}
        of the build requests are already claimed by another master instance,
        or don't exist.  In this case, none of the reclaims will take effect.

        @param brids: ids of buildrequests to reclaim
        @type brids: list

        @param _reactor: reactor to use (for testing)

        @returns: Deferred
        """

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
        """
        Release this master's claim on all of the given build requests.  This
        will not unclaim requests that are claimed by another master, but will
        not fail in this case.  The method does not check whether a request is
        completed.

        @param brids: ids of buildrequests to unclaim
        @type brids: list

        @returns: Deferred
        """
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
    def completeBuildRequests(self, brids, results, _reactor=reactor,
                                _master_objectid=None):
        """
        Complete a set of build requests, all of which are owned by this master
        instance.  This will fail with L{NotClaimedError} if the build request
        is already completed or does not exist.

        @param brids: build request IDs to complete
        @type brids: integer

        @param results: integer result code
        @type results: integer

        @param _reactor: reactor to use (for testing)

        @returns: Deferred
        """
        def thd(conn):
            transaction = conn.begin()

            # the update here is simple, but a number of conditions are
            # attached to ensure that we do not update a row inappropriately,
            # Note that checking that the request is mine would require a
            # subquery, so for efficiency that is not checed.

            reqs_tbl = self.db.model.buildrequests
            complete_at = _reactor.seconds()

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
        """
        Find any incomplete claimed builds which are older than C{old} seconds,
        and clear their claim information.

        This is intended to catch builds that were claimed by a master which
        has since disappeared.  As a side effect, it will log a message if any
        requests are unclaimed.

        @param old: number of seconds after which a claim is considered old
        @type old: int

        @param _reactor: for testing

        @returns: Deferred
        """
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
