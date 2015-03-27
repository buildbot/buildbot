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

import sqlalchemy as sa
import sqlalchemy.exc

from buildbot.db import base


class SchedulersConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def classifyChanges(self, objectid, classifications):
        def thd(conn):
            tbl = self.db.model.scheduler_changes
            ins_q = tbl.insert()
            upd_q = tbl.update(
                ((tbl.c.objectid == objectid)
                 & (tbl.c.changeid == sa.bindparam('wc_changeid'))))
            for changeid, important in classifications.items():
                transaction = conn.begin()
                # convert the 'important' value into an integer, since that
                # is the column type
                imp_int = important and 1 or 0
                try:
                    conn.execute(ins_q,
                                 objectid=objectid,
                                 changeid=changeid,
                                 important=imp_int)
                except (sqlalchemy.exc.ProgrammingError,
                        sqlalchemy.exc.IntegrityError):
                    transaction.rollback()
                    transaction = conn.begin()
                    # insert failed, so try an update
                    conn.execute(upd_q,
                                 wc_changeid=changeid,
                                 important=imp_int)

                transaction.commit()
        return self.db.pool.do(thd)

    def flushChangeClassifications(self, objectid, less_than=None):
        def thd(conn):
            sch_ch_tbl = self.db.model.scheduler_changes
            wc = (sch_ch_tbl.c.objectid == objectid)
            if less_than is not None:
                wc = wc & (sch_ch_tbl.c.changeid < less_than)
            q = sch_ch_tbl.delete(whereclause=wc)
            conn.execute(q)
        return self.db.pool.do(thd)

    class Thunk:
        pass

    def getChangeClassifications(self, objectid, branch=Thunk,
                                 repository=Thunk, project=Thunk,
                                 codebase=Thunk):
        def thd(conn):
            sch_ch_tbl = self.db.model.scheduler_changes
            ch_tbl = self.db.model.changes

            wc = (sch_ch_tbl.c.objectid == objectid)

            # may need to filter further based on branch, etc
            extra_wheres = []
            if branch is not self.Thunk:
                extra_wheres.append(ch_tbl.c.branch == branch)
            if repository is not self.Thunk:
                extra_wheres.append(ch_tbl.c.repository == repository)
            if project is not self.Thunk:
                extra_wheres.append(ch_tbl.c.project == project)
            if codebase is not self.Thunk:
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
