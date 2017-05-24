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
from future.utils import iteritems

import sqlalchemy as sa
import sqlalchemy.exc

from twisted.internet import defer

from buildbot.db import NULL
from buildbot.db import base


class SchedulerAlreadyClaimedError(Exception):
    pass


class SchedulersConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst

    def enable(self, schedulerid, v):
        def thd(conn):
            tbl = self.db.model.schedulers
            q = tbl.update(whereclause=(tbl.c.id == schedulerid))
            conn.execute(q, enabled=int(v))
        return self.db.pool.do(thd)

    def classifyChanges(self, schedulerid, classifications):
        def thd(conn):
            tbl = self.db.model.scheduler_changes
            ins_q = tbl.insert()
            upd_q = tbl.update(
                ((tbl.c.schedulerid == schedulerid) &
                 (tbl.c.changeid == sa.bindparam('wc_changeid'))))
            for changeid, important in iteritems(classifications):
                transaction = conn.begin()
                # convert the 'important' value into an integer, since that
                # is the column type
                imp_int = int(bool(important))
                try:
                    conn.execute(ins_q,
                                 schedulerid=schedulerid,
                                 changeid=changeid,
                                 important=imp_int).close()
                except (sqlalchemy.exc.ProgrammingError,
                        sqlalchemy.exc.IntegrityError):
                    transaction.rollback()
                    transaction = conn.begin()
                    # insert failed, so try an update
                    conn.execute(upd_q,
                                 wc_changeid=changeid,
                                 important=imp_int).close()

                transaction.commit()
        return self.db.pool.do(thd)

    def flushChangeClassifications(self, schedulerid, less_than=None):
        def thd(conn):
            sch_ch_tbl = self.db.model.scheduler_changes
            wc = (sch_ch_tbl.c.schedulerid == schedulerid)
            if less_than is not None:
                wc = wc & (sch_ch_tbl.c.changeid < less_than)
            q = sch_ch_tbl.delete(whereclause=wc)
            conn.execute(q).close()
        return self.db.pool.do(thd)

    def getChangeClassifications(self, schedulerid, branch=-1,
                                 repository=-1, project=-1,
                                 codebase=-1):
        # -1 here stands for "argument not given", since None has meaning
        # as a branch
        def thd(conn):
            sch_ch_tbl = self.db.model.scheduler_changes
            ch_tbl = self.db.model.changes

            wc = (sch_ch_tbl.c.schedulerid == schedulerid)

            # may need to filter further based on branch, etc
            extra_wheres = []
            if branch != -1:
                extra_wheres.append(ch_tbl.c.branch == branch)
            if repository != -1:
                extra_wheres.append(ch_tbl.c.repository == repository)
            if project != -1:
                extra_wheres.append(ch_tbl.c.project == project)
            if codebase != -1:
                extra_wheres.append(ch_tbl.c.codebase == codebase)

            # if we need to filter further append those, as well as a join
            # on changeid (but just once for that one)
            if extra_wheres:
                wc &= (sch_ch_tbl.c.changeid == ch_tbl.c.changeid)
                for w in extra_wheres:
                    wc &= w

            q = sa.select(
                [sch_ch_tbl.c.changeid, sch_ch_tbl.c.important],
                whereclause=wc)
            return dict([(r.changeid, [False, True][r.important])
                         for r in conn.execute(q)])
        return self.db.pool.do(thd)

    def findSchedulerId(self, name):
        tbl = self.db.model.schedulers
        name_hash = self.hashColumns(name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name_hash == name_hash),
            insert_values=dict(
                name=name,
                name_hash=name_hash,
            ))

    def setSchedulerMaster(self, schedulerid, masterid):
        def thd(conn):
            sch_mst_tbl = self.db.model.scheduler_masters

            # handle the masterid=None case to get it out of the way
            if masterid is None:
                q = sch_mst_tbl.delete(
                    whereclause=(sch_mst_tbl.c.schedulerid == schedulerid))
                conn.execute(q).close()
                return

            # try a blind insert..
            try:
                q = sch_mst_tbl.insert()
                conn.execute(q,
                             dict(schedulerid=schedulerid, masterid=masterid)).close()
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                # someone already owns this scheduler, but who?
                join = self.db.model.masters.outerjoin(
                    sch_mst_tbl,
                    (self.db.model.masters.c.id == sch_mst_tbl.c.masterid))

                q = sa.select([self.db.model.masters.c.name,
                               sch_mst_tbl.c.masterid], from_obj=join, whereclause=(
                    sch_mst_tbl.c.schedulerid == schedulerid))
                row = conn.execute(q).fetchone()
                # ok, that was us, so we just do nothing
                if row['masterid'] == masterid:
                    return
                raise SchedulerAlreadyClaimedError(
                    "already claimed by {}".format(row['name']))

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getScheduler(self, schedulerid):
        sch = yield self.getSchedulers(_schedulerid=schedulerid)
        if sch:
            defer.returnValue(sch[0])

    def getSchedulers(self, active=None, masterid=None, _schedulerid=None):
        def thd(conn):
            sch_tbl = self.db.model.schedulers
            sch_mst_tbl = self.db.model.scheduler_masters

            # handle the trivial case of masterid=xx and active=False
            if masterid is not None and active is not None and not active:
                return []

            join = sch_tbl.outerjoin(sch_mst_tbl,
                                     (sch_tbl.c.id == sch_mst_tbl.c.schedulerid))

            # if we're given a _schedulerid, select only that row
            wc = None
            if _schedulerid:
                wc = (sch_tbl.c.id == _schedulerid)
            else:
                # otherwise, filter with active, if necessary
                if masterid is not None:
                    wc = (sch_mst_tbl.c.masterid == masterid)
                elif active:
                    wc = (sch_mst_tbl.c.masterid != NULL)
                elif active is not None:
                    wc = (sch_mst_tbl.c.masterid == NULL)

            q = sa.select([sch_tbl.c.id, sch_tbl.c.name, sch_tbl.c.enabled,
                           sch_mst_tbl.c.masterid],
                          from_obj=join, whereclause=wc)

            return [dict(id=row.id, name=row.name, enabled=bool(row.enabled),
                         masterid=row.masterid)
                    for row in conn.execute(q).fetchall()]
        return self.db.pool.do(thd)
