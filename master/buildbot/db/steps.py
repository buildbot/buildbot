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


import json

import sqlalchemy as sa

from twisted.internet import defer

from buildbot.db import base
from buildbot.util import epoch2datetime


class StepsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst
    url_lock = None

    @defer.inlineCallbacks
    def getStep(self, stepid=None, buildid=None, number=None, name=None):
        tbl = self.db.model.steps
        if stepid is not None:
            wc = (tbl.c.id == stepid)
        else:
            if buildid is None:
                raise RuntimeError('must supply either stepid or buildid')
            if number is not None:
                wc = (tbl.c.number == number)
            elif name is not None:
                wc = (tbl.c.name == name)
            else:
                raise RuntimeError('must supply either number or name')
            wc = wc & (tbl.c.buildid == buildid)

        def thd(conn):
            q = self.db.model.steps.select(whereclause=wc)
            res = conn.execute(q)
            row = res.fetchone()

            rv = None
            if row:
                rv = self._stepdictFromRow(row)
            res.close()
            return rv
        return (yield self.db.pool.do(thd))

    # returns a Deferred that returns a value
    def getSteps(self, buildid):
        def thd(conn):
            tbl = self.db.model.steps
            q = tbl.select()
            q = q.where(tbl.c.buildid == buildid)
            q = q.order_by(tbl.c.number)
            res = conn.execute(q)
            return [self._stepdictFromRow(row) for row in res.fetchall()]
        return self.db.pool.do(thd)

    # returns a Deferred that returns a value
    def addStep(self, buildid, name, state_string):
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
                              state_string=state_string,
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
            names = {row[0] for row in res}
            num = 1
            while True:
                numstr = f'_{num}'
                newname = name[:50 - len(numstr)] + numstr
                if newname not in names:
                    break
                num += 1
            insert_row['name'] = newname
            r = conn.execute(self.db.model.steps.insert(), insert_row)
            got_id = r.inserted_primary_key[0]
            return (got_id, number, newname)
        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def startStep(self, stepid):
        started_at = int(self.master.reactor.seconds())

        def thd(conn):
            tbl = self.db.model.steps
            q = tbl.update(whereclause=(tbl.c.id == stepid))
            conn.execute(q, started_at=started_at)
        yield self.db.pool.do(thd)

    # returns a Deferred that returns None
    def setStepStateString(self, stepid, state_string):
        def thd(conn):
            tbl = self.db.model.steps
            q = tbl.update(whereclause=(tbl.c.id == stepid))
            conn.execute(q, state_string=state_string)
        return self.db.pool.do(thd)

    def addURL(self, stepid, name, url, _racehook=None):
        # This methods adds an URL to the db
        # This is a read modify write and thus there is a possibility
        # that several urls are added at the same time (e.g with a deferredlist
        # at the end of a step)
        # this race condition is only inside the same master, as only one master
        # is supposed to add urls to a buildstep.
        # so threading.lock is used, as we are in the thread pool
        if self.url_lock is None:
            # this runs in reactor thread, so no race here..
            self.url_lock = defer.DeferredLock()

        def thd(conn):

            tbl = self.db.model.steps
            wc = (tbl.c.id == stepid)
            q = sa.select([tbl.c.urls_json],
                          whereclause=wc)
            res = conn.execute(q)
            row = res.fetchone()
            if _racehook is not None:
                _racehook()
            urls = json.loads(row.urls_json)

            url_item = dict(name=name, url=url)

            if url_item not in urls:
                urls.append(url_item)
                q = tbl.update(whereclause=wc)
                conn.execute(q, urls_json=json.dumps(urls))

        return self.url_lock.run(lambda: self.db.pool.do(thd))

    # returns a Deferred that returns None
    def finishStep(self, stepid, results, hidden):
        def thd(conn):
            tbl = self.db.model.steps
            q = tbl.update(whereclause=(tbl.c.id == stepid))
            conn.execute(q,
                         complete_at=int(self.master.reactor.seconds()),
                         results=results,
                         hidden=1 if hidden else 0)
        return self.db.pool.do(thd)

    def _stepdictFromRow(self, row):
        return dict(
            id=row.id,
            number=row.number,
            name=row.name,
            buildid=row.buildid,
            started_at=epoch2datetime(row.started_at),
            complete_at=epoch2datetime(row.complete_at),
            state_string=row.state_string,
            results=row.results,
            urls=json.loads(row.urls_json),
            hidden=bool(row.hidden))
