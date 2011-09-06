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

    def classifyChanges(self, schedulerid, classifications):
        def thd(conn):
            tbl = self.db.model.scheduler_changes
            ins_q = tbl.insert()
            upd_q = tbl.update(
                    ((tbl.c.schedulerid == schedulerid)
                    & (tbl.c.changeid == sa.bindparam('wc_changeid'))))
            for changeid, important in classifications.items():
                # convert the 'important' value into an integer, since that
                # is the column type
                imp_int = important and 1 or 0
                try:
                    conn.execute(ins_q,
                            schedulerid=schedulerid,
                            changeid=changeid,
                            important=imp_int)
                except (sqlalchemy.exc.ProgrammingError,
                        sqlalchemy.exc.IntegrityError):
                    # insert failed, so try an update
                    conn.execute(upd_q,
                            wc_changeid=changeid,
                            important=imp_int)

        return self.db.pool.do(thd)

    def flushChangeClassifications(self, schedulerid, less_than=None):
        def thd(conn):
            scheduler_changes_tbl = self.db.model.scheduler_changes
            wc = (scheduler_changes_tbl.c.schedulerid == schedulerid)
            if less_than is not None:
                wc = wc & (scheduler_changes_tbl.c.changeid < less_than)
            q = scheduler_changes_tbl.delete(whereclause=wc)
            conn.execute(q)
        return self.db.pool.do(thd)

    class Thunk: pass
    def getChangeClassifications(self, schedulerid, branch=Thunk):
        def thd(conn):
            scheduler_changes_tbl = self.db.model.scheduler_changes
            changes_tbl = self.db.model.changes

            wc = (scheduler_changes_tbl.c.schedulerid == schedulerid)
            if branch is not self.Thunk:
                wc = wc & (
                    (scheduler_changes_tbl.c.changeid == changes_tbl.c.changeid) &
                    (changes_tbl.c.branch == branch))
            q = sa.select(
                [ scheduler_changes_tbl.c.changeid, scheduler_changes_tbl.c.important ],
                whereclause=wc)
            return dict([ (r.changeid, [False,True][r.important]) for r in conn.execute(q) ])
        return self.db.pool.do(thd)

    def getSchedulerId(self, sched_name, sched_class):
        """
        Get the schedulerid for the given scheduler, creating a new schedulerid
        if none is found.

        Note that this makes no attempt to "claim" the schedulerid: schedulers
        with the same name and class, but running in different masters, will be
        assigned the same schedulerid - with disastrous results.

        @param sched_name: the scheduler's configured name
        @param sched_class: the class name of this scheduler
        @returns: schedulerid, via a Deferred
        """
        def thd(conn):
            # get a matching row, *or* one without a class_name (from 0.8.0)
            schedulers_tbl = self.db.model.schedulers
            q = schedulers_tbl.select(
                    whereclause=(
                        (schedulers_tbl.c.name == sched_name) &
                        ((schedulers_tbl.c.class_name == sched_class) |
                         (schedulers_tbl.c.class_name == ''))))
            res = conn.execute(q)
            row = res.fetchone()
            res.close()

            # if no existing row, then insert a new one and return it.  There
            # is no protection against races here, but that's OK - the worst
            # that happens is two sourcestamps with identical content; before
            # 0.8.4 this was always the case.
            if not row:
                q = schedulers_tbl.insert()
                res = conn.execute(q,
                        name=sched_name,
                        class_name=sched_class,
                        state='{}')
                return res.inserted_primary_key[0]

            # upgrade the row with the class name, if necessary
            if row.class_name == '':
                q = schedulers_tbl.update(
                    whereclause=(
                        (schedulers_tbl.c.name == sched_name) &
                        (schedulers_tbl.c.class_name == '')))
                conn.execute(q, class_name=sched_class)
            return row.schedulerid
        return self.db.pool.do(thd)
