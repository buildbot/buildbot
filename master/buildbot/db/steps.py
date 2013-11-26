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

from buildbot.db import base
from buildbot.util import epoch2datetime
from buildbot.util import json
from twisted.internet import defer
from twisted.internet import reactor


class StepsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst

    def _getStep(self, whereclause):
        def thd(conn):
            q = self.db.model.steps.select(whereclause=whereclause)
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._stepdictFromRow(row)
            res.close()
            return rv
        return self.db.pool.do(thd)

    def getStep(self, stepid):
        return self._getStep(self.db.model.steps.c.id == stepid)

    def getStepByBuild(self, buildid, number=None, name=None):
        tbl = self.db.model.steps
        if number is not None:
            wc = (tbl.c.number == number)
        elif name is not None:
            wc = (tbl.c.name == name)
        else:
            return defer.fail(RuntimeError('must supply either number or name'))
        wc = wc & (tbl.c.buildid == buildid)
        return self._getStep(wc)

    def getSteps(self, buildid):
        def thd(conn):
            tbl = self.db.model.steps
            q = tbl.select()
            q = q.where(tbl.c.buildid == buildid)
            q = q.order_by(tbl.c.number)
            res = conn.execute(q)
            return [self._stepdictFromRow(row) for row in res.fetchall()]
        return self.db.pool.do(thd)

    def addStep(self, buildid, name, state_strings):
        state_strings_json = json.dumps(state_strings)

        def thd(conn):
            tbl = self.db.model.steps
            # get the highest current number
            r = conn.execute(sa.select([sa.func.max(tbl.c.number)],
                                       whereclause=(tbl.c.buildid == buildid)))
            number = r.scalar()
            number = 0 if number is None else number + 1

            # note that there is no chance for a race condition here,
            # since only one master is inserting steps.  If there is a
            # conflict, then the name is likely already taken.
            insert_row = dict(buildid=buildid, number=number,
                              started_at=None, complete_at=None,
                              state_strings_json=state_strings_json,
                              urls_json='[]', name=name)
            try:
                r = conn.execute(self.db.model.steps.insert(), insert_row)
                got_id = r.inserted_primary_key[0]
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                got_id = None

            if got_id:
                return (got_id, number, name)

            # we didn't get an id, so calculate a unique name and use that
            # instead.  Because names are truncated at the right to fit in a
            # 50-character identifier, this isn't a simple query.
            res = conn.execute(sa.select([tbl.c.name],
                                         whereclause=((tbl.c.buildid == buildid))))
            names = set([row[0] for row in res])
            num = 1
            while True:
                numstr = '_%d' % num
                newname = name[:50 - len(numstr)] + numstr
                if newname not in names:
                    break
                num += 1
            insert_row['name'] = newname
            r = conn.execute(self.db.model.steps.insert(), insert_row)
            got_id = r.inserted_primary_key[0]
            return (got_id, number, newname)
        return self.db.pool.do(thd)

    def startStep(self, stepid, _reactor=reactor):
        started_at = _reactor.seconds()

        def thd(conn):
            tbl = self.db.model.steps
            q = tbl.update(whereclause=(tbl.c.id == stepid))
            conn.execute(q, started_at=started_at)
        return self.db.pool.do(thd)

    def setStepStateStrings(self, stepid, state_strings):
        def thd(conn):
            tbl = self.db.model.steps
            q = tbl.update(whereclause=(tbl.c.id == stepid))
            conn.execute(q, state_strings_json=json.dumps(state_strings))
        return self.db.pool.do(thd)

    def finishStep(self, stepid, results, _reactor=reactor):
        def thd(conn):
            tbl = self.db.model.steps
            q = tbl.update(whereclause=(tbl.c.id == stepid))
            conn.execute(q,
                         complete_at=_reactor.seconds(),
                         results=results)
        return self.db.pool.do(thd)

    def _stepdictFromRow(self, row):
        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)

        return dict(
            id=row.id,
            number=row.number,
            name=row.name,
            buildid=row.buildid,
            started_at=mkdt(row.started_at),
            complete_at=mkdt(row.complete_at),
            state_strings=json.loads(row.state_strings_json),
            results=row.results,
            urls=json.loads(row.urls_json))
