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

import time
import sqlalchemy as sa
from datetime import datetime
from buildbot.util import json
from buildbot.db import base

class BuildsetsConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle getting buildsets into and out of the
    database.  An instance is available at C{master.db.buildsets}.
    """

    def addBuildset(self, ssid, reason, properties, builderNames,
                   external_idstring=None):
        """
        Add a new Buildset to the database, along with the buildrequests for
        each named builder, returning the resulting bsid via a Deferred.
        Arguments should be specified by keyword.

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

        @returns: buildset ID via a Deferred
        """
        def thd(conn):
            submitted_at = datetime.now()
            submitted_at_epoch = time.mktime(submitted_at.timetuple())

            transaction = conn.begin()

            # insert the buildset itself
            r = conn.execute(self.db.model.buildsets.insert(), dict(
                sourcestampid=ssid,
                submitted_at=submitted_at_epoch,
                reason=reason,
                external_idstring=external_idstring))
            bsid = r.inserted_primary_key[0]

            # add any properties
            if properties:
                conn.execute(self.db.model.buildset_properties.insert(), [
                    dict(buildsetid=bsid, property_name=k,
                         property_value=json.dumps([v,s]))
                    for k,(v,s) in properties.iteritems() ])

            # and finish with a build request for each builder
            conn.execute(self.db.model.buildrequests.insert(), [
                dict(buildsetid=bsid, buildername=buildername,
                     submitted_at=submitted_at_epoch)
                for buildername in builderNames ])

            transaction.commit()

            return bsid
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
