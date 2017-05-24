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

import sqlalchemy as sa

from twisted.internet import defer

from buildbot.db import base


class BuildersConnectorComponent(base.DBConnectorComponent):

    def findBuilderId(self, name):
        tbl = self.db.model.builders
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name == name),
            insert_values=dict(
                name=name,
                name_hash=self.hashColumns(name),
            ))

    @defer.inlineCallbacks
    def updateBuilderInfo(self, builderid, description, tags):
        # convert to tag IDs first, as necessary
        def toTagid(tag):
            if isinstance(tag, type(1)):
                return defer.succeed(tag)
            ssConnector = self.master.db.tags
            return ssConnector.findTagId(tag)

        tagsids = [r[1] for r in (yield defer.DeferredList(
            [toTagid(tag) for tag in tags],
            fireOnOneErrback=True,
            consumeErrors=True))]

        def thd(conn):
            builders_tbl = self.db.model.builders
            builders_tags_tbl = self.db.model.builders_tags
            transaction = conn.begin()

            q = builders_tbl.update(
                whereclause=(builders_tbl.c.id == builderid))
            conn.execute(q, description=description).close()
            # remove previous builders_tags
            conn.execute(builders_tags_tbl.delete(
                whereclause=((builders_tags_tbl.c.builderid == builderid)))).close()

            # add tag ids
            if tagsids:
                conn.execute(builders_tags_tbl.insert(),
                             [dict(builderid=builderid, tagid=tagid)
                              for tagid in tagsids]).close()

            transaction.commit()

        defer.returnValue((yield self.db.pool.do(thd)))

    def getBuilder(self, builderid):
        d = self.getBuilders(_builderid=builderid)

        @d.addCallback
        def first(bldrs):
            if bldrs:
                return bldrs[0]
            return None
        return d

    def addBuilderMaster(self, builderid=None, masterid=None):
        def thd(conn, no_recurse=False):
            try:
                tbl = self.db.model.builder_masters
                q = tbl.insert()
                conn.execute(q, builderid=builderid, masterid=masterid)
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                pass
        return self.db.pool.do(thd)

    def removeBuilderMaster(self, builderid=None, masterid=None):
        def thd(conn, no_recurse=False):
            tbl = self.db.model.builder_masters
            conn.execute(tbl.delete(
                whereclause=((tbl.c.builderid == builderid) &
                             (tbl.c.masterid == masterid))))
        return self.db.pool.do(thd)

    def getBuilders(self, masterid=None, _builderid=None):
        def thd(conn):
            bldr_tbl = self.db.model.builders
            bm_tbl = self.db.model.builder_masters
            j = bldr_tbl.outerjoin(bm_tbl)
            # if we want to filter by masterid, we must join to builder_masters
            # again, so we can still get the full set of masters for each
            # builder
            if masterid is not None:
                limiting_bm_tbl = bm_tbl.alias('limiting_bm')
                j = j.join(limiting_bm_tbl,
                           onclause=(bldr_tbl.c.id == limiting_bm_tbl.c.builderid))
            q = sa.select(
                [bldr_tbl.c.id, bldr_tbl.c.name,
                    bldr_tbl.c.description, bm_tbl.c.masterid],
                from_obj=[j],
                order_by=[bldr_tbl.c.id, bm_tbl.c.masterid])
            if masterid is not None:
                # filter the masterid from the limiting table
                q = q.where(limiting_bm_tbl.c.masterid == masterid)
            if _builderid is not None:
                q = q.where(bldr_tbl.c.id == _builderid)

            # now group those by builderid, aggregating by masterid
            rv = []
            last = None
            for row in conn.execute(q).fetchall():
                # pylint: disable=unsubscriptable-object
                if not last or row['id'] != last['id']:
                    last = self._thd_row2dict(conn, row)
                    rv.append(last)
                if row['masterid']:
                    last['masterids'].append(row['masterid'])
            return rv
        return self.db.pool.do(thd)

    def _thd_row2dict(self, conn, row):
        # get tags
        builders_tags = self.db.model.builders_tags
        tags = self.db.model.tags
        from_clause = tags
        from_clause = from_clause.join(builders_tags)
        q = sa.select([tags.c.name],
                      (builders_tags.c.builderid == row.id)).select_from(from_clause)

        tags = [r.name for r in
                conn.execute(q).fetchall()]

        return dict(id=row.id, name=row.name, masterids=[],
                    description=row.description,
                    tags=tags)
