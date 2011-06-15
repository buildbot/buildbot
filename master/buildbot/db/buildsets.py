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
from buildbot.util import json
from buildbot.db import base
from buildbot.util import epoch2datetime

class BsDict(dict):
    pass

class BuildsetsConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle getting buildsets into and out of the
    database.  An instance is available at C{master.db.buildsets}.
    """

    def addBuildset(self, ssid, reason, properties, builderNames,
                   external_idstring=None, _reactor=reactor):
        """
        Add a new Buildset to the database, along with the buildrequests for
        each named builder, returning the resulting bsid via a Deferred.
        Arguments should be specified by keyword.

        The return value is a tuple C{(bsid, brids)} where C{bsid} is the
        inserted buildset ID and C{brids} is a dictionary mapping buildernames
        to build request IDs.

        @param ssid: id of the SourceStamp for this buildset
        @type ssid: integer

        @param reason: reason for this buildset
        @type reason: short unicode string

        @param properties: properties for this buildset
        @type properties: dictionary, where values are tuples of (value,
        source)

        @param builderNames: builders specified by this buildset
        @type builderNames: list of strings

        @param external_idstring: external key to identify this buildset;
        defaults to None
        @type external_idstring: unicode string

        @param _reactor: for testing

        @returns: buildset ID and buildrequest IDs, via a Deferred
        """
        def thd(conn):
            submitted_at = _reactor.seconds()

            transaction = conn.begin()

            # insert the buildset itself
            r = conn.execute(self.db.model.buildsets.insert(), dict(
                sourcestampid=ssid, submitted_at=submitted_at,
                reason=reason, complete=0, complete_at=None, results=-1,
                external_idstring=external_idstring))
            bsid = r.inserted_primary_key[0]

            # add any properties
            if properties:
                conn.execute(self.db.model.buildset_properties.insert(), [
                    dict(buildsetid=bsid, property_name=k,
                         property_value=json.dumps([v,s]))
                    for k,(v,s) in properties.iteritems() ])

            # and finish with a build request for each builder.  Note that
            # sqlalchemy and the Python DBAPI do not provide a way to recover
            # inserted IDs from a multi-row insert, so this is done one row at
            # a time.
            brids = {}
            ins = self.db.model.buildrequests.insert()
            for buildername in builderNames:
                r = conn.execute(ins,
                    dict(buildsetid=bsid, buildername=buildername, priority=0,
                        claimed_at=0, claimed_by_name=None,
                        claimed_by_incarnation=None, complete=0, results=-1,
                        submitted_at=submitted_at, complete_at=None))

                brids[buildername] = r.inserted_primary_key[0]

            transaction.commit()

            return (bsid, brids)
        return self.db.pool.do(thd)

    def completeBuildset(self, bsid, results, _reactor=reactor):
        """
        Complete a buildset, marking it with the given C{results} and setting
        its C{completed_at} to the current time.

        @param bsid: buildset ID to complete
        @type bsid: integer

        @param results: integer result code
        @type results: integer

        @param _reactor: reactor to use (for testing)

        @returns: Deferred
        @raises KeyError: if the row does not exist or is already complete
        """
        def thd(conn):
            tbl = self.db.model.buildsets

            q = tbl.update(whereclause=(
                (tbl.c.id == bsid) &
                ((tbl.c.complete == None) | (tbl.c.complete != 1))))
            res = conn.execute(q,
                complete=1,
                results=results,
                complete_at=_reactor.seconds())

            if res.rowcount != 1:
                raise KeyError
        return self.db.pool.do(thd)

    def getBuildset(self, bsid):
        """
        Get a dictionary representing the given buildset, or None
        if no such buildset exists.

        The dictionary has keys C{bsid}, C{external_idstring}, C{reason},
        C{sourcestampid}, C{submitted_at}, C{complete}, C{complete_at}, and
        C{results}.  The C{*_at} keys point to datetime objects.  Use
        L{getBuildsetProperties} to fetch the properties for a buildset.

        Note that buildsets are not cached, as the values in the database are
        not fixed.

        @param bsid: buildset ID

        @returns: dictionary as above, or None, via Deferred
        """
        def thd(conn):
            bs_tbl = self.db.model.buildsets
            q = bs_tbl.select(whereclause=(bs_tbl.c.id == bsid))
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            return self._row2dict(row)
        return self.db.pool.do(thd)

    def getBuildsets(self, complete=None):
        """
        Get a list of buildset dictionaries (see L{getBuildset}) matching
        the given criteria.

        Since this method is often used to detect changed build requests, it
        always bypasses the cache.

        @param complete: if True, return only complete buildsets; if False,
        return only incomplete buildsets; if None or omitted, return all
        buildsets

        @returns: list of dictionaries, via Deferred
        """
        def thd(conn):
            bs_tbl = self.db.model.buildsets
            q = bs_tbl.select()
            if complete is not None:
                if complete:
                    q = q.where(bs_tbl.c.complete != 0)
                else:
                    q = q.where((bs_tbl.c.complete == 0) |
                                (bs_tbl.c.complete == None))
            res = conn.execute(q)
            return [ self._row2dict(row) for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def getBuildsetProperties(self, buildsetid):
        """
        Return the properties for a buildset, in the same format they were
        given to L{addBuildset}.

        Note that this method does not distinguish a nonexistent buildset from
        a buildset with no properties, and returns C{{}} in either case.

        @param buildsetid: buildset ID

        @returns: dictionary mapping property name to (value, source), via
        Deferred
        """
        def thd(conn):
            bsp_tbl = self.db.model.buildset_properties
            q = sa.select(
                [ bsp_tbl.c.property_name, bsp_tbl.c.property_value ],
                whereclause=(bsp_tbl.c.buildsetid == buildsetid))
            return dict([ (row.property_name,
                           tuple(json.loads(row.property_value)))
                          for row in conn.execute(q) ])
        return self.db.pool.do(thd)

    def subscribeToBuildset(self, schedulerid, buildsetid):
        """
        Add a row to C{scheduler_upstream_buildsets} indicating that
        C{schedulerid} is interested in buildset C{bsid}.

        @param schedulerid: downstream scheduler
        @type schedulerid: integer

        @param buildsetid: buildset id the scheduler is subscribing to
        @type buildsetid: integer

        @returns: Deferred
        """
        def thd(conn):
            conn.execute(self.db.model.scheduler_upstream_buildsets.insert(),
                    schedulerid=schedulerid,
                    buildsetid=buildsetid,
                    active=1)
        return self.db.pool.do(thd)

    def unsubscribeFromBuildset(self, schedulerid, buildsetid):
        """
        The opposite of L{subscribeToBuildset}, this removes the subcription
        row from the database, rather than simply marking it as inactive.

        @param schedulerid: downstream scheduler
        @type schedulerid: integer

        @param buildsetid: buildset id the scheduler is subscribing to
        @type buildsetid: integer

        @returns: Deferred
        """
        def thd(conn):
            tbl = self.db.model.scheduler_upstream_buildsets
            conn.execute(tbl.delete(
                    (tbl.c.schedulerid == schedulerid) &
                    (tbl.c.buildsetid == buildsetid)))
        return self.db.pool.do(thd)

    def getSubscribedBuildsets(self, schedulerid):
        """
        Get the set of buildsets to which this scheduler is subscribed, along
        with the buildsets' current results.  This will exclude any rows marked
        as not active.

        The return value is a list of tuples, each containing a buildset ID, a
        sourcestamp ID, a boolean indicating that the buildset is complete, and
        the buildset's result.

        @param schedulerid: downstream scheduler
        @type schedulerid: integer

        @returns: list as described, via Deferred
        """
        def thd(conn):
            bs_tbl = self.db.model.buildsets
            upstreams_tbl = self.db.model.scheduler_upstream_buildsets
            q = sa.select(
                [bs_tbl.c.id, bs_tbl.c.sourcestampid,
                 bs_tbl.c.results, bs_tbl.c.complete],
                whereclause=(
                    (upstreams_tbl.c.schedulerid == schedulerid) &
                    (upstreams_tbl.c.buildsetid == bs_tbl.c.id) &
                    (upstreams_tbl.c.active != 0)),
                distinct=True)
            return [ (row.id, row.sourcestampid, row.complete, row.results)
                     for row in conn.execute(q).fetchall() ]
        return self.db.pool.do(thd)

    def _row2dict(self, row):
        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)
        return BsDict(external_idstring=row.external_idstring,
                reason=row.reason, sourcestampid=row.sourcestampid,
                submitted_at=mkdt(row.submitted_at),
                complete=bool(row.complete),
                complete_at=mkdt(row.complete_at), results=row.results,
                bsid=row.id)

