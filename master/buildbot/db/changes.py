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
Support for changes in the database
"""

from buildbot.util import json
import sqlalchemy as sa
from twisted.internet import defer, reactor
from buildbot.db import base
from buildbot.util import epoch2datetime, datetime2epoch

class ChDict(dict):
    pass

class ChangesConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def addChange(self, author=None, files=None, comments=None, is_dir=0,
            revision=None, when_timestamp=None, branch=None,
            category=None, revlink='', properties={}, repository='', codebase='',
            project='', uid=None, _reactor=reactor):
        assert project is not None, "project must be a string, not None"
        assert repository is not None, "repository must be a string, not None"

        if when_timestamp is None:
            when_timestamp = epoch2datetime(_reactor.seconds())

        # verify that source is 'Change' for each property
        for pv in properties.values():
            assert pv[1] == 'Change', ("properties must be qualified with"
                                       "source 'Change'")

        def thd(conn):
            # note that in a read-uncommitted database like SQLite this
            # transaction does not buy atomicitiy - other database users may
            # still come across a change without its files, properties,
            # etc.  That's OK, since we don't announce the change until it's
            # all in the database, but beware.

            transaction = conn.begin()

            ch_tbl = self.db.model.changes

            self.check_length(ch_tbl.c.author, author)
            self.check_length(ch_tbl.c.comments, comments)
            self.check_length(ch_tbl.c.branch, branch)
            self.check_length(ch_tbl.c.revision, revision)
            self.check_length(ch_tbl.c.revlink, revlink)
            self.check_length(ch_tbl.c.category, category)
            self.check_length(ch_tbl.c.repository, repository)
            self.check_length(ch_tbl.c.project, project)

            r = conn.execute(ch_tbl.insert(), dict(
                author=author,
                comments=comments,
                is_dir=is_dir,
                branch=branch,
                revision=revision,
                revlink=revlink,
                when_timestamp=datetime2epoch(when_timestamp),
                category=category,
                repository=repository,
                codebase=codebase,
                project=project))
            changeid = r.inserted_primary_key[0]
            if files:
                tbl = self.db.model.change_files
                for f in files:
                    self.check_length(tbl.c.filename, f)
                conn.execute(tbl.insert(), [
                    dict(changeid=changeid, filename=f)
                        for f in files
                    ])
            if properties:
                tbl = self.db.model.change_properties
                inserts = [
                    dict(changeid=changeid,
                        property_name=k,
                        property_value=json.dumps(v))
                    for k,v in properties.iteritems()
                ]
                for i in inserts:
                    self.check_length(tbl.c.property_name,
                            i['property_name'])
                    self.check_length(tbl.c.property_value,
                            i['property_value'])

                conn.execute(tbl.insert(), inserts)
            if uid:
                ins = self.db.model.change_users.insert()
                conn.execute(ins, dict(changeid=changeid, uid=uid))

            transaction.commit()

            return changeid
        d = self.db.pool.do(thd)
        return d

    @base.cached("chdicts")
    def getChange(self, changeid):
        assert changeid >= 0
        def thd(conn):
            # get the row from the 'changes' table
            changes_tbl = self.db.model.changes
            q = changes_tbl.select(whereclause=(changes_tbl.c.changeid == changeid))
            rp = conn.execute(q)
            row = rp.fetchone()
            if not row:
                return None
            # and fetch the ancillary data (files, properties)
            return self._chdict_from_change_row_thd(conn, row)
        d = self.db.pool.do(thd)
        return d

    def getChangeUids(self, changeid):
        assert changeid >= 0
        def thd(conn):
            cu_tbl = self.db.model.change_users
            q = cu_tbl.select(whereclause=(cu_tbl.c.changeid == changeid))
            res = conn.execute(q)
            rows = res.fetchall()
            row_uids = [ row.uid for row in rows ]
            return row_uids
        d = self.db.pool.do(thd)
        return d

    def getRecentChanges(self, count):
        def thd(conn):
            # get the changeids from the 'changes' table
            changes_tbl = self.db.model.changes
            q = sa.select([changes_tbl.c.changeid],
                    order_by=[sa.desc(changes_tbl.c.changeid)],
                    limit=count)
            rp = conn.execute(q)
            changeids = [ row.changeid for row in rp ]
            rp.close()
            return list(reversed(changeids))
        d = self.db.pool.do(thd)

        # then turn those into changes, using the cache
        def get_changes(changeids):
            return defer.gatherResults([ self.getChange(changeid)
                                         for changeid in changeids ])
        d.addCallback(get_changes)
        return d

    def getLatestChangeid(self):
        def thd(conn):
            changes_tbl = self.db.model.changes
            q = sa.select([ changes_tbl.c.changeid ],
                    order_by=sa.desc(changes_tbl.c.changeid),
                    limit=1)
            return conn.scalar(q)
        d = self.db.pool.do(thd)
        return d

    # utility methods

    def pruneChanges(self, changeHorizon):
        """
        Called periodically by DBConnector, this method deletes changes older
        than C{changeHorizon}.
        """

        if not changeHorizon:
            return defer.succeed(None)
        def thd(conn):
            changes_tbl = self.db.model.changes

            # First, get the list of changes to delete.  This could be written
            # as a subquery but then that subquery would be run for every
            # table, which is very inefficient; also, MySQL's subquery support
            # leaves much to be desired, and doesn't support this particular
            # form.
            q = sa.select([changes_tbl.c.changeid],
                          order_by=[sa.desc(changes_tbl.c.changeid)],
                          offset=changeHorizon)
            res = conn.execute(q)
            ids_to_delete = [ r.changeid for r in res ]

            # and delete from all relevant tables, in dependency order
            for table_name in ('scheduler_changes', 'sourcestamp_changes',
                               'change_files', 'change_properties', 'changes',
                               'change_users'):
                remaining = ids_to_delete[:]
                while remaining:
                    batch, remaining = remaining[:100], remaining[100:]
                    table = self.db.model.metadata.tables[table_name]
                    conn.execute(
                        table.delete(table.c.changeid.in_(batch)))
        return self.db.pool.do(thd)

    def _chdict_from_change_row_thd(self, conn, ch_row):
        # This method must be run in a db.pool thread, and returns a chdict
        # given a row from the 'changes' table
        change_files_tbl = self.db.model.change_files
        change_properties_tbl = self.db.model.change_properties

        chdict = ChDict(
                changeid=ch_row.changeid,
                author=ch_row.author,
                files=[], # see below
                comments=ch_row.comments,
                is_dir=ch_row.is_dir,
                revision=ch_row.revision,
                when_timestamp=epoch2datetime(ch_row.when_timestamp),
                branch=ch_row.branch,
                category=ch_row.category,
                revlink=ch_row.revlink,
                properties={}, # see below
                repository=ch_row.repository,
                codebase=ch_row.codebase,
                project=ch_row.project)

        query = change_files_tbl.select(
                whereclause=(change_files_tbl.c.changeid == ch_row.changeid))
        rows = conn.execute(query)
        for r in rows:
            chdict['files'].append(r.filename)

        # and properties must be given without a source, so strip that, but
        # be flexible in case users have used a development version where the
        # change properties were recorded incorrectly
        def split_vs(vs):
            try:
                v,s = vs
                if s != "Change":
                    v,s = vs, "Change"
            except:
                v,s = vs, "Change"
            return v, s

        query = change_properties_tbl.select(
                whereclause=(change_properties_tbl.c.changeid == ch_row.changeid))
        rows = conn.execute(query)
        for r in rows:
            try:
                v, s = split_vs(json.loads(r.property_value))
                chdict['properties'][r.property_name] = (v,s)
            except ValueError:
                pass

        return chdict
