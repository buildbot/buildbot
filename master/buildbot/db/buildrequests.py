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

    def getBuildRequest(self, brid):
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
            tbl = self.db.model.buildrequests
            res = conn.execute(tbl.select(whereclause=(tbl.c.id == brid)))
            row = res.fetchone()

            rv = None
            if row:
                rv = self._brdictFromRow(row)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def getBuildRequests(self, buildername=None, complete=None, claimed=None,
            bsid=None):
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
            tbl = self.db.model.buildrequests
            q = tbl.select()
            if claimed is not None:
                if not claimed:
                    q = q.where(
                        ((tbl.c.claimed_at == None) |
                         (tbl.c.claimed_at == 0)) &
                        (tbl.c.claimed_by_name == None) &
                        (tbl.c.claimed_by_incarnation == None) &
                        (tbl.c.complete == 0))
                elif claimed == "mine":
                    master_name = self.db.master.master_name
                    master_incarnation = self.db.master.master_incarnation
                    q = q.where(
                        (tbl.c.claimed_at != None) &
                        (tbl.c.claimed_by_name == master_name) &
                        (tbl.c.claimed_by_incarnation == master_incarnation))
                else:
                    q = q.where(
                        (tbl.c.claimed_at != None) &
                        (tbl.c.claimed_at != 0) &
                        (tbl.c.claimed_by_name != None) &
                        (tbl.c.claimed_by_incarnation != None))
            if buildername is not None:
                q = q.where(tbl.c.buildername == buildername)
            if complete is not None:
                if complete:
                    q = q.where(tbl.c.complete != 0)
                else:
                    q = q.where(tbl.c.complete == 0)
            if bsid is not None:
                q = q.where(tbl.c.buildsetid == bsid)
            res = conn.execute(q)

            return [ self._brdictFromRow(row) for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def claimBuildRequests(self, brids, _reactor=reactor, _race_hook=None):
        """
        Try to "claim" the indicated build requests for this buildmaster
        instance.  The resulting deferred will fire normally on success, or
        fail with L{AleadyClaimedError} if I{any} of the build requests are
        already claimed by another master instance, or don't exist.  In this
        case, none of the claims will take effect.

        This can be used to re-claim build requests, too.  That is, it will
        succeed in claiming a build request that is already claimed by this
        master instance, and will update its claimed_at date.

        @param brids: ids of buildrequests to claim
        @type brids: list

        @param _reactor: reactor to use (for testing)
        @param _race_hook: hook for testing

        @returns: Deferred
        """

        # This function attempts to work reasonably well across a number of
        # database engines with a variety of transactional isolation levels.
        # Unlike older versions of Buildbot, this uses a qualified UPDATE
        # statement that will only claim unclaimed builds, so no potential
        # serialization of parallel UPDATE operations can result in both
        # parties believing they have claimed a build request.  This technique
        # will tend to work better in environments with higher isolation
        # levels, and may result in an IntegrityError for SERIALIZABLE
        # databases.
        #
        # We then perform a post-UPDATE check to ensure that we really have
        # claimed all of the desired build requests.  This will be most
        # effective in environments with lower transactional isolation levels,
        # which may incorrectly serialize the conflicting UPDATES.

        def alreadyClaimed(conn, tmp):
            # helper function to un-claim already-claimed requests, if we can't
            # claim all of them.  This may be redundant for the finer database
            # engines, but won't hurt.
            master_name = self.db.master.master_name
            master_incarnation = self.db.master.master_incarnation
            tbl = self.db.model.buildrequests

            # only select *my builds* in this set of brids
            q = tbl.update()
            q = q.where((tbl.c.id.in_(tmp.select())) &
                ((tbl.c.claimed_at != None) &
                 (tbl.c.claimed_by_name == master_name) &
                 (tbl.c.claimed_by_incarnation == master_incarnation)))
            # and unclaim them
            conn.execute(q,
                claimed_at=None,
                claimed_by_name=None,
                claimed_by_incarnation=None)

        def thd(conn):
            # update conditioned on the request being unclaimed, or claimed by
            # this instance.  In either case, the claimed_at is set to the
            # current time, so this will re-claim an already-claimed requeset.
            master_name = self.db.master.master_name
            master_incarnation = self.db.master.master_incarnation
            tbl = self.db.model.buildrequests

            # first, create a temporary table containing all of the ID's
            # we want to claim
            tmp_meta = sa.MetaData(bind=conn)
            tmp = sa.Table('bbtmp_claim_ids', tmp_meta,
                    sa.Column('brid', sa.Integer),
                    prefixes=['TEMPORARY'])
            tmp.create()

            transaction = conn.begin()

            try:
                q = tmp.insert()
                conn.execute(q, [ dict(brid=id) for id in brids ])

                q = tbl.update(whereclause=(tbl.c.id.in_(tmp.select())))
                q = q.where(
                    # unclaimed
                    (((tbl.c.claimed_at == None) | (tbl.c.claimed_at == 0)) &
                    (tbl.c.claimed_by_name == None) &
                    (tbl.c.claimed_by_incarnation == None)) |
                    # .. or mine
                    ((tbl.c.claimed_at != None) &
                    (tbl.c.claimed_by_name == master_name) &
                    (tbl.c.claimed_by_incarnation == master_incarnation)))
                res = conn.execute(q,
                    claimed_at=_reactor.seconds(),
                    claimed_by_name=self.db.master.master_name,
                    claimed_by_incarnation=self.db.master.master_incarnation)
                updated_rows = res.rowcount
                res.close()

                # if no rows or too few rows were updated, then we failed; this
                # will roll back the transaction
                if updated_rows != len(brids):
                    # MySQL doesn't do transactions, so roll this back manually
                    if conn.engine.dialect.name == 'mysql':
                        alreadyClaimed(conn, tmp)
                    transaction.rollback()
                    raise AlreadyClaimedError

                transaction.commit()

                # testing hook to simulate a race condition
                if _race_hook:
                    _race_hook(conn)

                # but double-check to be sure all of the desired build requests
                # now belong to this master
                q = sa.select([tbl.c.claimed_by_name,
                            tbl.c.claimed_by_incarnation],
                            whereclause=(tbl.c.id.in_(tmp.select())))
                res = conn.execute(q)
                for row in res:
                    if row.claimed_by_name != master_name or \
                            row.claimed_by_incarnation != master_incarnation:
                        # note that the transaction is already committed here; too
                        # bad!  We'll just fake it by unclaiming those requests (so
                        # hopefully this was not a reclaim)
                        alreadyClaimed(conn, tmp)
                        raise AlreadyClaimedError
                res.close()
            finally:
                # clean up after ourselves, even though it's a temporary table;
                # note that checkfirst=True does not work here for Postgres
                # (#2010).
                tmp.drop()

        return self.db.pool.do(thd)

    def unclaimBuildRequests(self, brids):
        """
        Release this master's claim on all of the given build requests.  This
        will check that the requests are claimed by this master, but will not
        fail if they are not so claimed.

        @param brids: ids of buildrequests to unclaim
        @type brids: list

        @returns: Deferred
        """
        def thd(conn):
            master_name = self.db.master.master_name
            master_incarnation = self.db.master.master_incarnation
            tbl = self.db.model.buildrequests

            q = tbl.update(whereclause=(tbl.c.id.in_(brids)))
            q = q.where(
                # incomplete
                (tbl.c.complete == 0) &
                # .. and mine only
                (tbl.c.claimed_at != None) &
                (tbl.c.claimed_by_name == master_name) &
                (tbl.c.claimed_by_incarnation == master_incarnation))
            res = conn.execute(q,
                claimed_at=0,
                claimed_by_name=None,
                claimed_by_incarnation=None)
            res.close()
        return self.db.pool.do(thd)

    def completeBuildRequests(self, brids, results, _reactor=reactor):
        """
        Complete a set of build requests, all of which are owned by this master
        instance.  This will fail with L{NotClaimedError} if the build request
        is not claimed by this instance, is already completed, or does not
        exist.

        @param brids: build request IDs to complete
        @type brids: integer

        @param results: integer result code
        @type results: integer

        @param _reactor: reactor to use (for testing)

        @returns: Deferred
        """
        def thd(conn):
            # the update here is simple, but a number of conditions are
            # attached to ensure that we do not update a row inappropriately
            master_name = self.db.master.master_name
            master_incarnation = self.db.master.master_incarnation
            tbl = self.db.model.buildrequests

            q = tbl.update(whereclause=(tbl.c.id.in_(brids)))
            q = q.where(
                (tbl.c.claimed_at != None) &
                (tbl.c.claimed_by_name == master_name) &
                (tbl.c.claimed_by_incarnation == master_incarnation) &
                (tbl.c.complete == 0))
            res = conn.execute(q,
                complete=1,
                results=results,
                complete_at=_reactor.seconds())

            # if no rows were updated, then we failed (and left things in an
            # awkward state, at that!)
            if res.rowcount != len(brids):
                raise NotClaimedError
        return self.db.pool.do(thd)

    def unclaimOldIncarnationRequests(self):
        """
        Find any incomplete build requests claimed by an old incarnation of
        this master and mark them as unclaimed.

        @returns: Deferred
        """
        def thd(conn):
            tbl = self.db.model.buildrequests
            master_name = self.db.master.master_name
            master_incarnation = self.db.master.master_incarnation

            q = tbl.update(whereclause=(
                    (tbl.c.claimed_by_name == master_name) &
                    (tbl.c.claimed_by_incarnation != master_incarnation) &
                    (tbl.c.complete == 0)))
            res = conn.execute(q,
                claimed_at=0,
                claimed_by_name=None,
                claimed_by_incarnation=None)
            return res.rowcount
        d = self.db.pool.do(thd)
        def log_nonzero_count(count):
            if count != 0:
                log.msg("unclaimed %d buildrequests for an old instance of "
                        "this master" % (count,))
        d.addCallback(log_nonzero_count)
        return d

    def unclaimExpiredRequests(self, old, _reactor=reactor):
        """
        Find any incomplete claimed builds which are older than C{old} seconds,
        and clear their claim information.

        This is intended to catch builds that were claimed by a master which
        has since disappeared.

        @param old: number of seconds after which a claim is considered old
        @type old: int

        @param _reactor: for testing

        @returns: Deferred
        """
        def thd(conn):
            tbl = self.db.model.buildrequests
            old_epoch = _reactor.seconds() - old

            q = tbl.update(whereclause=(
                    (tbl.c.claimed_at != 0) &
                    (tbl.c.claimed_at < old_epoch) &
                    (tbl.c.complete == 0)))
            res = conn.execute(q,
                claimed_at=0,
                claimed_by_name=None,
                claimed_by_incarnation=None)
            return res.rowcount
        d = self.db.pool.do(thd)
        def log_nonzero_count(count):
            if count != 0:
                log.msg("unclaimed %d expired buildrequests (over %d seconds "
                        "old)" % (count, old))
        d.addCallback(log_nonzero_count)
        return d

    def _brdictFromRow(self, row):
        claimed = mine = False
        if (row.claimed_at
                and row.claimed_by_name is not None
                and row.claimed_by_incarnation is not None):
            claimed = True
            master_name = self.db.master.master_name
            master_incarnation = self.db.master.master_incarnation
            if (row.claimed_by_name == master_name and
                row.claimed_by_incarnation == master_incarnation):
               mine = True

        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)
        submitted_at = mkdt(row.submitted_at)
        claimed_at = mkdt(row.claimed_at)
        complete_at = mkdt(row.complete_at)

        return BrDict(brid=row.id, buildsetid=row.buildsetid,
                buildername=row.buildername, priority=row.priority,
                claimed=claimed, claimed_at=claimed_at, mine=mine,
                complete=bool(row.complete), results=row.results,
                submitted_at=submitted_at, complete_at=complete_at)
