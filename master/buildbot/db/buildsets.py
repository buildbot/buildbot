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
from buildbot.util import epoch2datetime, datetime2epoch

class BsDict(dict):
    pass

class BuildsetsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def addBuildset(self, sourcestampsetid, reason, properties, builderNames,
                   external_idstring=None, _reactor=reactor):
        def thd(conn):
            submitted_at = _reactor.seconds()

            transaction = conn.begin()

            # insert the buildset itself
            r = conn.execute(self.db.model.buildsets.insert(), dict(
                sourcestampsetid=sourcestampsetid, submitted_at=submitted_at,
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

    def completeBuildset(self, bsid, results, complete_at=None,
                                _reactor=reactor):
        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = _reactor.seconds()

        def thd(conn):
            tbl = self.db.model.buildsets

            q = tbl.update(whereclause=(
                (tbl.c.id == bsid) &
                ((tbl.c.complete == None) | (tbl.c.complete != 1))))
            res = conn.execute(q,
                complete=1,
                results=results,
                complete_at=complete_at)

            if res.rowcount != 1:
                raise KeyError
        return self.db.pool.do(thd)

    def getBuildset(self, bsid):
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
            l = []
            for row in conn.execute(q):
                try:
                    properties = json.loads(row.property_value)
                    l.append((row.property_name,
                           tuple(properties)))
                except ValueError:
                    pass
            return dict(l)
        return self.db.pool.do(thd)

    def _row2dict(self, row):
        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)
        return BsDict(external_idstring=row.external_idstring,
                reason=row.reason, sourcestampsetid=row.sourcestampsetid,
                submitted_at=mkdt(row.submitted_at),
                complete=bool(row.complete),
                complete_at=mkdt(row.complete_at), results=row.results,
                bsid=row.id)
