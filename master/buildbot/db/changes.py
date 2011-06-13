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
    """
    A DBConnectorComponent to handle getting changes into and out of the
    database.  An instance is available at C{master.db.changes}.

    Changes are represented as dictionaries with the following keys:

    - changeid: the ID of this change
    - author: the author of the change (unicode string)
    - files: list of source-code filenames changed (unicode strings)
    - comments: user comments (unicode string)
    - is_dir: deprecated
    - links: list of links for this change, e.g., to web views, review
      (unicode strings)
    - revision: revision for this change (unicode string), or None if unknown
    - when_timestamp: time of the commit (datetime instance)
    - branch: branch on which the change took place (unicode string), or None
      for the "default branch", whatever that might mean
    - category: user-defined category of this change (unicode string or None)
    - revlink: link to a web view of this change (unicode string or None)
    - properties: user-specified properties for this change, represented as a
      dictionary mapping keys to (value, source)
    - repository: repository where this change occurred (unicode string)
    - project: user-defined project to which this change corresponds (unicode
      string)
    """

    def addChange(self, author=None, files=None, comments=None, is_dir=0,
            links=None, revision=None, when_timestamp=None, branch=None,
            category=None, revlink='', properties={}, repository='',
            project='', _reactor=reactor):
        """Add a Change with the given attributes to the database; returns
        a Change instance via a deferred.  All arguments are keyword arguments.

        @param author: the author of this change
        @type author: unicode string

        @param files: a list of filenames that were changed
        @type branch: list of unicode strings

        @param comments: user comments on the change
        @type branch: unicode string

        @param is_dir: deprecated

        @param links: a list of links related to this change, e.g., to web
        viewers or review pages
        @type links: list of unicode strings

        @param revision: the revision identifier for this change
        @type revision: unicode string

        @param when_timestamp: when this change occurred, or the current time
          if None
        @type when_timestamp: datetime instance or None

        @param branch: the branch on which this change took place
        @type branch: unicode string

        @param category: category for this change (arbitrary use by Buildbot
        users)
        @type category: unicode string

        @param revlink: link to a web view of this revision
        @type revlink: unicode string

        @param properties: properties to set on this change
        @type properties: dictionary, where values are tuples of (value,
        source).  At the moment, the source must be C{'Change'}, although
        this may be relaxed in later versions.

        @param repository: the repository in which this change took place
        @type repository: unicode string

        @param project: the project this change is a part of
        @type project: unicode string

        @param _reactor: for testing

        @returns: new change's ID via Deferred
        """
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
            # still come across a change without its links, files, properties,
            # etc.  That's OK, since we don't announce the change until it's
            # all in the database, but beware.

            transaction = conn.begin()

            ins = self.db.model.changes.insert()
            r = conn.execute(ins, dict(
                author=author,
                comments=comments,
                is_dir=is_dir,
                branch=branch,
                revision=revision,
                revlink=revlink,
                when_timestamp=datetime2epoch(when_timestamp),
                category=category,
                repository=repository,
                project=project))
            changeid = r.inserted_primary_key[0]
            if links:
                ins = self.db.model.change_links.insert()
                conn.execute(ins, [
                    dict(changeid=changeid, link=l)
                        for l in links
                    ])
            if files:
                ins = self.db.model.change_files.insert()
                conn.execute(ins, [
                    dict(changeid=changeid, filename=f)
                        for f in files
                    ])
            if properties:
                ins = self.db.model.change_properties.insert()
                conn.execute(ins, [
                    dict(changeid=changeid,
                        property_name=k,
                        property_value=json.dumps(v))
                    for k,v in properties.iteritems()
                ])

            transaction.commit()

            return changeid
        d = self.db.pool.do(thd)
        return d

    @base.cached("chdicts")
    def getChange(self, changeid):
        """
        Get a change dictionary for the given changeid, or None if no such
        change exists.

        @param changeid: the id of the change instance to fetch

        @param no_cache: bypass cache and always fetch from database
        @type no_cache: boolean

        @returns: Change dictionary via Deferred
        """
        assert changeid >= 0
        def thd(conn):
            # get the row from the 'changes' table
            changes_tbl = self.db.model.changes
            q = changes_tbl.select(whereclause=(changes_tbl.c.changeid == changeid))
            rp = conn.execute(q)
            row = rp.fetchone()
            if not row:
                return None
            # and fetch the ancillary data (links, files, properties)
            return self._chdict_from_change_row_thd(conn, row)
        d = self.db.pool.do(thd)
        return d

    def getRecentChanges(self, count):
        """
        Get a list of the C{count} most recent changes, represented as
        dictionaies; returns fewer if that many do not exist.

        @param count: maximum number of instances to return

        @returns: list of dictionaries via Deferred, ordered by changeid
        """
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
        """
        Get the most-recently-assigned changeid, or None if there are no
        changes at all.

        @returns: changeid via Deferred
        """
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
                               'change_files', 'change_links',
                               'change_properties', 'changes'):
                table = self.db.model.metadata.tables[table_name]
                conn.execute(
                    table.delete(table.c.changeid.in_(ids_to_delete)))
        return self.db.pool.do(thd)

    def _chdict_from_change_row_thd(self, conn, ch_row):
        # This method must be run in a db.pool thread, and returns a chdict
        # given a row from the 'changes' table
        change_links_tbl = self.db.model.change_links
        change_files_tbl = self.db.model.change_files
        change_properties_tbl = self.db.model.change_properties

        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)

        chdict = ChDict(
                changeid=ch_row.changeid,
                author=ch_row.author,
                files=[], # see below
                comments=ch_row.comments,
                is_dir=ch_row.is_dir,
                links=[], # see below
                revision=ch_row.revision,
                when_timestamp=mkdt(ch_row.when_timestamp),
                branch=ch_row.branch,
                category=ch_row.category,
                revlink=ch_row.revlink,
                properties={}, # see below
                repository=ch_row.repository,
                project=ch_row.project)

        query = change_links_tbl.select(
                whereclause=(change_links_tbl.c.changeid == ch_row.changeid))
        rows = conn.execute(query)
        for r in rows:
            chdict['links'].append(r.link)

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
            v, s = split_vs(json.loads(r.property_value))
            chdict['properties'][r.property_name] = (v,s)

        return chdict
