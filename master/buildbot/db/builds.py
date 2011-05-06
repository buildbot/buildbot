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
(Very partial) support for builds in the database
"""

from twisted.internet import reactor
from buildbot.db import base
from buildbot.util import epoch2datetime

class BuildsConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle a little bit of information about builds.
    Avaialble at C{master.db.buildrequests}.

    NOTE: The interface for this module will change - the builds table
    duplicates some information available in pickles, without including all
    such information.  Do not depend on this API.

    Note that a single build may be represented in many rows in the builds
    table, as it the builds table represents 

    Builds are represented as dictionaries with keys C{bid} (the build ID,
    globally unique), C{number} (the build number, unique only within this
    master and builder), C{brid} (the ID of the build request that caused this
    build), C{start_time}, and C{finish_time} (datetime objects, or None).
    """

    def getBuild(self, bid):
        """
        Get a single build, in the format described above.  Returns
        C{None} if there is no such build.

        @param bid: build id
        @type bid: integer

        @returns: Build dictionary as above or None, via Deferred
        """
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

    def getBuildsForRequest(self, brid):
        """
        Get a list of builds for the given build request.  The resulting
        build dictionaries are in exactly the same format as for L{getBuild}.

        @param brids: list of build request ids

        @returns: List of build dictionaries as above, via Deferred
        """
        def thd(conn):
            tbl = self.db.model.builds
            q = tbl.select(whereclause=(tbl.c.brid == brid))
            res = conn.execute(q)
            return [ self._bdictFromRow(row) for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def addBuild(self, brid, number, _reactor=reactor):
        """
        Add a new build, recorded as having started now.

        @param brid: build request id
        @param number: build number

        @param _reactor: reactor to use (for testing)
        @param _race_hook: hook for testing

        @returns: build ID via Deferred
        """

        def thd(conn):
            start_time = _reactor.seconds()
            r = conn.execute(self.db.model.builds.insert(),
                    dict(number=number, brid=brid, start_time=start_time,
                        finish_time=None))
            return r.inserted_primary_key[0]
        return self.db.pool.do(thd)

    def finishBuilds(self, bids, _reactor=reactor):
        """

        Mark builds as finished, with C{finish_time} now.  This is done
        unconditionally, even if the builds are already finished.

        @param bids: build ids
        @type bids: list

        @param _reactor: reactor to use (for testing)

        @returns: Deferred
        """
        def thd(conn):
            tbl = self.db.model.builds
            now = _reactor.seconds()

            # split the bids into batches, so as not to overflow the parameter
            # lists of the database interface
            remaining = bids
            while remaining:
                batch, remaining = remaining[:100], remaining[100:]
                q = tbl.update(whereclause=(tbl.c.id.in_(batch)))
                conn.execute(q, finish_time=now)
        return self.db.pool.do(thd)

    def _bdictFromRow(self, row):
        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)

        return dict(
            bid=row.id,
            brid=row.brid,
            number=row.number,
            start_time=mkdt(row.start_time),
            finish_time=mkdt(row.finish_time))
