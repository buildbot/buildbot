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

import sys
import Queue
from buildbot.util import json
import sqlalchemy as sa
from twisted.python import log
from buildbot.changes.changes import Change
from buildbot.db import base
from buildbot import util

class ChangesConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle getting changes into and out of the
    database.  An instance is available at C{master.db.changes}.
    """

    changeHorizon = 0
    "maximum number of changes to keep on hand, or 0 to keep all changes forever"
    # TODO: add a threadsafe change cache

    def changeEventGenerator(self, branches=[], categories=[], committers=[], minTime=0):
        "deprecated. do not use."
        # the technique here is to use a queue and a boolean value to
        # communicate between the db thread and the main thread.  The queue
        # sends completed change tuples to the main thread, while the boolean
        # value indicates that the thread should exit.
        #
        # If this wacky hack seems sensible to you, you're not looking hard
        # enough!  Once the web UI is rewritten (waterfall and console are the only
        # consumers of the generator), this should be killed with fire.

        queue = Queue.Queue(16)
        stop_flag = [ False ]

        def thd(conn):
            try:
                changes_tbl = self.db.model.changes

                query = changes_tbl.select()
                if branches:
                    query = query.where(changes_tbl.c.branch.in_(branches))
                if categories:
                    query = query.where(changes_tbl.c.category.in_(categories))
                if committers:
                    query = query.where(changes_tbl.c.author.in_(committers))
                if minTime:
                    query = query.where(changes_tbl.c.when_timestamp > minTime)
                query = query.order_by(sa.desc(changes_tbl.c.changeid))
                change_rows = conn.execute(query)
                for ch_row in change_rows:
                    chdict = self._chdict_from_change_row_thd(conn, ch_row)
                    # bail out if we've been asked to stop
                    if stop_flag[0]:
                        break
                    queue.put(chdict)
                queue.put(None)
            except:
                # push exceptions onto the queue and return
                queue.put(sys.exc_info())
        d = self.db.pool.do(thd)

        # note that we don't actually look at the results of this deferred.  If
        # an error occurs in the thread, it is handled by returning a tuple
        # instead.  Still, we might as well handle any exceptions that get
        # raised into failures
        d.addErrback(log.err)

        try:
            while True:
                chdict = queue.get()
                if chdict is None:
                    # we've seen all of the changes
                    break
                if isinstance(chdict, tuple):
                    # exception in thread; raise it here
                    raise chdict[0], chdict[1], chdict[2]
                else:
                    yield self._change_from_chdict(chdict)
        # we'll get GeneratorExit when the generator is garbage-collected before it
        # has finished, so signal to the thread that its work is finished.
        # TODO: GeneratorExit is not supported in Python-2.4, which means this method
        # won't work there.  Which is OK.  This method needs to die, quickly.
        except GeneratorExit:
            stop_flag[0] = False
            # .. and drain the queue
            while not queue.empty():
                queue.get()

    def addChange(self, who, files, comments, isdir=0, links=None,
                 revision=None, when=None, branch=None, category=None,
                 revlink='', properties={}, repository='', project=''):
        """Add the a Change with the given attributes to the database; returns
        a Change instance via a deferred.

        @param who: the author of this change
        @type branch: unicode string

        @param files: a list of filenames that were changed
        @type branch: list of unicode strings

        @param comments: user comments on the change
        @type branch: unicode string

        @param isdir: deprecated

        @param links: a list of links related to this change, e.g., to web viewers
        or review pages
        @type links: list of unicode strings

        @param revision: the revision identifier for this change
        @type revision: unicode string

        @param when: when this change occurs; defaults to now, and cannot be later
        than now
        @type when: integer (UNIX epoch time)

        @param branch: the branch on which this change took place
        @type branch: unicode string

        @param category: category for this change (arbitrary use by Buildbot users)
        @type category: unicode string

        @param revlink: link to a web view of this revision
        @type revlink: unicode string

        @param properties: properties to set on this change
        @type properties: dictionary with string keys and simple values (JSON-able)

        @param repository: the repository in which this change took place
        @type repository: unicode string

        @param project: the project this change is a part of
        @type project: unicode string

        @returns: a L{buildbot.changes.changes.Change} instance via Deferred
        """
        # first create the change, although with no 'number'
        change = Change(who=who, files=files, comments=comments, isdir=isdir,
                links=links, revision=revision, when=when, branch=branch,
                category=category, revlink=revlink, properties=properties,
                repository=repository, project=project)

        # then add it to the database and update its '.number'
        def thd(conn):
            assert change.number is None
            ins = self.db.model.changes.insert()
            r = conn.execute(ins, dict(
                author=change.who,
                comments=change.comments,
                is_dir=change.isdir,
                branch=change.branch,
                revision=change.revision,
                revlink=change.revlink,
                when_timestamp=change.when,
                category=change.category,
                repository=change.repository,
                project=change.project))
            change.number = r.inserted_primary_key[0]
            if change.links:
                ins = self.db.model.change_links.insert()
                conn.execute(ins, [
                    dict(changeid=change.number, link=l)
                        for l in change.links
                    ])
            if change.files:
                ins = self.db.model.change_files.insert()
                conn.execute(ins, [
                    dict(changeid=change.number, filename=f)
                        for f in change.files
                    ])
            if change.properties:
                ins = self.db.model.change_properties.insert()
                conn.execute(ins, [
                    dict(changeid=change.number, property_name=k, property_value=json.dumps(v))
                        for k,v,s in change.properties.asList()
                    ])
            return change
        d = self.db.pool.do(thd)
        # prune changes, if necessary
        d.addCallback(lambda _ : self._prune_changes(change.number))
        # return the change
        d.addCallback(lambda _ : change)
        return d

    def getChangeInstance(self, changeid):
        """
        Get a L{buildbot.changes.changes.Change} instance for the given changeid,
        or None if no such change exists.

        @param changeid: the id of the change instance to fetch

        @returns: Change instance via Deferred
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

        def make_change(chdict):
            if not chdict:
                return None
            return self._change_from_chdict(chdict)
        d.addCallback(make_change)
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

    def setChangeHorizon(self, changeHorizon): # TODO: remove
        "this method should go away"
        self.changeHorizon = changeHorizon

    # cache management

    def _flush_cache(self):
        pass # TODO

    # utility methods

    _last_prune = 0
    def _prune_changes(self, last_added_changeid):
        # this is an expensive operation, so only do it once per minute, in case
        # addChange is called frequently
        if not self.changeHorizon or self._last_prune > util.now() - 60:
            return
        self._last_prune = util.now()
        log.msg("pruning changes")

        def thd(conn):
            changes_tbl = self.db.model.changes
            current_horizon = last_added_changeid - self.changeHorizon

            # create a subquery giving the changes to delete
            ids_to_delete_query = sa.select([changes_tbl.c.changeid],
                                    whereclause=changes_tbl.c.changeid <= current_horizon)

            # and delete from all relevant tables, *ending* with the changes table
            for table_name in ('scheduler_changes', 'sourcestamp_changes', 'change_files',
                               'change_links', 'change_properties', 'changes'):
                table = self.db.model.metadata.tables[table_name]
                conn.execute(
                    table.delete(table.c.changeid.in_(ids_to_delete_query)))
        return self.db.pool.do(thd)

    def _chdict_from_change_row_thd(self, conn, ch_row):
        # This method must be run in a db.pool thread, and returns a chdict
        # (which can be used to construct a Change object), given a row from
        # the 'changes' table
        change_links_tbl = self.db.model.change_links
        change_files_tbl = self.db.model.change_files
        change_properties_tbl = self.db.model.change_properties

        chdict = dict(
                number=ch_row.changeid,
                who=ch_row.author,
                files=[], # see below
                comments=ch_row.comments,
                isdir=ch_row.is_dir,
                links=[], # see below
                revision=ch_row.revision,
                when=ch_row.when_timestamp,
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

        query = change_properties_tbl.select(
                whereclause=(change_properties_tbl.c.changeid == ch_row.changeid))
        rows = conn.execute(query)
        for r in rows:
            chdict['properties'][r.property_name] = json.loads(r.property_value)

        return chdict

    def _change_from_chdict(self, chdict):
        # create a Change object, given a chdict
        changeid = chdict.pop('number')
        c = Change(**chdict)
        c.number = changeid
        return c
