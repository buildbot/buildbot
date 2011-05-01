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

import base64
import time

from twisted.python import threadable, log
from twisted.application import internet, service
from buildbot.db import enginestrategy

from buildbot import util
from buildbot.util import collections as bbcollections
from buildbot.sourcestamp import SourceStamp
from buildbot.process.properties import Properties
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE
from buildbot.util.eventual import eventually
from buildbot.util import json
from buildbot.db import pool, model, changes, schedulers, sourcestamps
from buildbot.db import state, buildsets, buildrequests, builds

def str_or_none(s):
    if s is None:
        return None
    return str(s)

class Token: # used for _start_operation/_end_operation
    pass

from twisted.enterprise import adbapi
class TempAdbapiPool(adbapi.ConnectionPool):
    def __init__(self, engine):
        # this wants a module name, so give it one..
        adbapi.ConnectionPool.__init__(self, "buildbot.db.connector")
        self._engine = engine

    def connect(self):
        return self._engine.raw_connection()

    def stop(self):
        pass

class DBConnector(service.MultiService):
    """
    The connection between Buildbot and its backend database.  This is
    generally accessible as master.db, but is also used during upgrades.

    Most of the interesting operations available via the connector are
    implemented in connector components, available as attributes of this
    object, and listed below.
    """

    synchronized = ["notify", "_end_operation"] # TODO: remove
    MAX_QUERY_TIMES = 1000

    # Period, in seconds, of the cleanup task.  This master will perform
    # periodic cleanup actions on this schedule.
    CLEANUP_PERIOD = 3600

    def __init__(self, master, db_url, basedir):
        service.MultiService.__init__(self)
        self.master = master
        self.basedir = basedir
        "basedir for this master - used for upgrades"

        self._engine = enginestrategy.create_engine(db_url, basedir=self.basedir)
        self.pool = pool.DBThreadPool(self._engine)
        "thread pool (L{buildbot.db.pool.DBThreadPool}) for this db"

        self._oldpool = TempAdbapiPool(self._engine)

        self._sourcestamp_cache = util.LRUCache() # TODO: remove
        self._active_operations = set() # protected by synchronized= TODO: remove
        self._pending_notifications = [] # TODO: remove
        self._subscribers = bbcollections.defaultdict(set)

        self._started = False

        # set up components
        self.model = model.Model(self)
        "L{buildbot.db.model.Model} instance"

        self.changes = changes.ChangesConnectorComponent(self)
        "L{buildbot.db.changes.ChangesConnectorComponent} instance"

        self.schedulers = schedulers.SchedulersConnectorComponent(self)
        "L{buildbot.db.schedulers.ChangesConnectorComponent} instance"

        self.sourcestamps = sourcestamps.SourceStampsConnectorComponent(self)
        "L{buildbot.db.sourcestamps.SourceStampsConnectorComponent} instance"

        self.buildsets = buildsets.BuildsetsConnectorComponent(self)
        "L{buildbot.db.sourcestamps.BuildsetsConnectorComponent} instance"

        self.buildrequests = buildrequests.BuildRequestsConnectorComponent(self)
        "L{buildbot.db.sourcestamps.BuildRequestsConnectorComponent} instance"

        self.state = state.StateConnectorComponent(self)
        "L{buildbot.db.state.StateConnectorComponent} instance"

        self.builds = builds.BuildsConnectorComponent(self)
        "L{buildbot.db.builds.BuildsConnectorComponent} instance"

        self.cleanup_timer = internet.TimerService(self.CLEANUP_PERIOD, self.doCleanup)
        self.cleanup_timer.setServiceParent(self)

        self.changeHorizon = None # default value; set by master

    def start(self): # TODO: remove
        # this only *needs* to be called in reactorless environments (which
        # should be eliminated anyway).  but it doesn't hurt anyway
        self._oldpool.start()
        self._started = True

    def stop(self): # TODO: remove
        """Call this when you're done with me"""

        if not self._started:
            return
        self._oldpool.stop()
        self._started = False
        del self._oldpool

    def quoteq(self, query, returning=None): # TODO: remove
        """
        Given a query that contains qmark-style placeholders, like::
         INSERT INTO foo (col1, col2) VALUES (?,?)
        replace the '?' with '%s' if the backend uses format-style
        placeholders, like::
         INSERT INTO foo (col1, col2) VALUES (%s,%s)

        While there, append "RETURNING x" for backends that don't provide
        last row id (PostgreSQL and probably Oracle).
        """
        # PostgreSQL:
        # * doesn't return last row id, so we must append "RETURNING x"
        #   to queries where we want it and we must fetch it later,
        # PostgreSQL and MySQL:
        # * don't accept "?" in queries.
        if self._engine.dialect.name in ('postgres', 'postgresql', 'mysql'):
            query = query.replace("?", "%s")
        if self._engine.dialect.name in ('postgres', 'postgresql'):
            if returning:
                query += " RETURNING %s" % returning
        return query

    def lastrowid(self, t): # TODO: remove
        # PostgreSQL:
        # * fetch last row id from previously issued "RETURNING x" query.
        if self._engine.dialect.name in ('postgres', 'postgresql'):
            row = t.fetchone()
            if row:
                 return row[0]
            return -1

        # default
        return t.lastrowid

    def parmlist(self, count): # TODO: remove
        """
        When passing long lists of values to e.g., an INSERT query, it is
        tedious to pass long strings of ? placeholders.  This function will
        create a parenthesis-enclosed list of COUNT placeholders.  Note that
        the placeholders have already had quoteq() applied.
        """
        p = self.quoteq("?")
        return "(" + ",".join([p]*count) + ")"

    def runQueryNow(self, *args, **kwargs): # TODO: remove
        # synchronous+blocking version of runQuery()
        assert self._started
        return self.runInteractionNow(self._runQuery, *args, **kwargs)

    def _runQuery(self, c, *args, **kwargs):
        c.execute(*args, **kwargs)
        return c.fetchall()

    # TODO: remove
    def _start_operation(self):
        t = Token()
        self._active_operations.add(t)
        return t
    def _end_operation(self, t):
        # this is always invoked from the main thread, but is wrapped by
        # synchronized= and threadable.synchronous(), since it touches
        # self._pending_notifications, which is also touched by
        # runInteraction threads
        self._active_operations.discard(t)
        if self._active_operations:
            return
        for (category, args) in self._pending_notifications:
            # in the distributed system, this will be a
            # transport.write(" ".join([category] + [str(a) for a in args]))
            eventually(self.send_notification, category, args)
        self._pending_notifications = []

    def runInteractionNow(self, interaction, *args, **kwargs): # TODO: remove
        # synchronous+blocking version of runInteraction()
        assert self._started
        t = self._start_operation()
        try:
            return self._runInteractionNow(interaction, *args, **kwargs)
        finally:
            self._end_operation(t)

    def _runInteractionNow(self, interaction, *args, **kwargs): # TODO: remove
        conn = self._engine.raw_connection()
        c = conn.cursor()
        result = interaction(c, *args, **kwargs)
        c.close()
        conn.commit()
        return result

    def notify(self, category, *args): # TODO: remove
        # this is wrapped by synchronized= and threadable.synchronous(),
        # since it will be invoked from runInteraction threads
        self._pending_notifications.append( (category,args) )

    def send_notification(self, category, args): # TODO: remove
        # in the distributed system, this will be invoked by lineReceived()
        #print "SEND", category, args
        for observer in self._subscribers[category]:
            eventually(observer, category, *args)

    def subscribe_to(self, category, observer): # TODO: remove
        self._subscribers[category].add(observer)

    def runQuery(self, *args, **kwargs): # TODO: remove
        assert self._started
        d = self._oldpool.runQuery(*args, **kwargs)
        return d

    def _runQuery_done(self, res, start, t): # TODO: remove
        self._end_operation(t)
        return res

    def runInteraction(self, *args, **kwargs): # TODO: remove
        assert self._started
        start = time.time()
        t = self._start_operation()
        d = self._oldpool.runInteraction(*args, **kwargs)
        d.addBoth(self._runInteraction_done, start, t)
        return d
    def _runInteraction_done(self, res, start, t): # TODO: remove
        self._end_operation(t)
        return res

    # SourceStamp-manipulating methods

    def getSourceStampNumberedNow(self, ssid, t=None):
        assert isinstance(ssid, (int, long))
        ss = self._sourcestamp_cache.get(ssid)
        if ss:
            return ss
        if t:
            ss = self._txn_getSourceStampNumbered(t, ssid)
        else:
            ss = self.runInteractionNow(self._txn_getSourceStampNumbered,
                                           ssid)
        self._sourcestamp_cache.add(ssid, ss)
        return ss

    def _txn_getSourceStampNumbered(self, t, ssid):
        assert isinstance(ssid, (int, long))
        t.execute(self.quoteq("SELECT branch,revision,patchid,project,repository"
                              " FROM sourcestamps WHERE id=?"),
                  (ssid,))
        r = t.fetchall()
        if not r:
            return None
        (branch_u, revision_u, patchid, project, repository) = r[0]
        branch = str_or_none(branch_u)
        revision = str_or_none(revision_u)

        patch = None
        if patchid is not None:
            t.execute(self.quoteq("SELECT patchlevel,patch_base64,subdir"
                                  " FROM patches WHERE id=?"),
                      (patchid,))
            r = t.fetchall()
            assert len(r) == 1
            (patch_level, patch_text_base64, subdir_u) = r[0]
            patch_text = base64.b64decode(patch_text_base64)
            if subdir_u:
                patch = (patch_level, patch_text, str(subdir_u))
            else:
                patch = (patch_level, patch_text)

        t.execute(self.quoteq("SELECT changeid FROM sourcestamp_changes"
                              " WHERE sourcestampid=?"
                              " ORDER BY changeid ASC"),
                  (ssid,))
        r = t.fetchall()
        changes = None
        if r:
            changes = [self.getChangeNumberedNow(changeid, t)
                       for (changeid,) in r]
        ss = SourceStamp(branch, revision, patch, changes, project=project, repository=repository)
        ss.ssid = ssid
        return ss

    # Properties methods

    # used by getChangeNumberedNow (below)
    def get_properties_from_db(self, tablename, idname, id, t=None):
        if t:
            return self._txn_get_properties_from_db(t, tablename, idname, id)
        else:
            return self.runInteractionNow(self._txn_get_properties_from_db,
                                          tablename, idname, id)

    def _txn_get_properties_from_db(self, t, tablename, idname, id):
        # apparently you can't use argument placeholders for table names. Don't
        # call this with a weird-looking tablename.
        q = self.quoteq("SELECT property_name,property_value FROM %s WHERE %s=?"
                        % (tablename, idname))
        t.execute(self.quoteq(q), (id,))
        retval = Properties()
        for key, value_json in t.fetchall():
            value = json.loads(value_json)
            if tablename == "change_properties":
                # change_properties does not store a source
                value, source = value, "Change"
            else:
                # buildset_properties stores a tuple (value, source)
                value, source = value
            retval.setProperty(str(key), value, source)
        return retval

    # BuildRequest-manipulation methods

    def get_buildername_for_brid(self, brid):
        assert isinstance(brid, (int, long))
        return self.runInteractionNow(self._txn_get_buildername_for_brid, brid)
    def _txn_get_buildername_for_brid(self, t, brid):
        assert isinstance(brid, (int, long))
        t.execute(self.quoteq("SELECT buildername FROM buildrequests"
                              " WHERE id=?"),
                  (brid,))
        r = t.fetchall()
        if not r:
            return None
        return r[0][0]

    # used by Builder.buildFinished
    def builds_finished(self, bids):
        return self.runInteractionNow(self._txn_build_finished, bids)
    def _txn_build_finished(self, t, bids):
        now = time.time()
        while bids:
            batch, bids = bids[:100], bids[100:]
            q = self.quoteq("UPDATE builds SET finish_time = ?"
                            " WHERE id IN " + self.parmlist(len(batch)))
            qargs = [now] + list(batch)
            t.execute(q, qargs)

    # used by BuildRequestStatus.getBuilds
    def get_buildnums_for_brid(self, brid):
        return self.runInteractionNow(self._txn_get_buildnums_for_brid, brid)
    def _txn_get_buildnums_for_brid(self, t, brid):
        t.execute(self.quoteq("SELECT number FROM builds WHERE brid=?"),
                  (brid,))
        return [number for (number,) in t.fetchall()]

    # used by Builder.buildFinished
    def resubmit_buildrequests(self, brids):
        return self.runInteraction(self._txn_resubmit_buildreqs, brids)
    def _txn_resubmit_buildreqs(self, t, brids):
        # the interrupted build that gets resubmitted will still have the
        # same submitted_at value, so it should be re-started first
        while brids:
            batch, brids = brids[:100], brids[100:]
            q = self.quoteq("UPDATE buildrequests"
                            " SET claimed_at=0,"
                            "     claimed_by_name=NULL, claimed_by_incarnation=NULL"
                            " WHERE id IN " + self.parmlist(len(batch)))
            t.execute(q, batch)

    # used by BuildRequestControl.cancel and Builder.cancelBuildRequest
    def cancel_buildrequests(self, brids):
        return self.runInteractionNow(self._txn_cancel_buildrequest, brids)
    def _txn_cancel_buildrequest(self, t, brids):
        # TODO: we aren't entirely sure if it'd be safe to just delete the
        # buildrequest: what else might be waiting on it that would then just
        # hang forever?. _check_buildset() should handle it well (an empty
        # buildset will appear complete and SUCCESS-ful). But we haven't
        # thought it through enough to be sure. So for now, "cancel" means
        # "mark as complete and FAILURE".
        while brids:
            batch, brids = brids[:100], brids[100:]

            if True:
                now = time.time()
                q = self.quoteq("UPDATE buildrequests"
                                " SET complete=1, results=?, complete_at=?"
                                " WHERE id IN " + self.parmlist(len(batch)))
                t.execute(q, [FAILURE, now]+batch)
            else:
                q = self.quoteq("DELETE FROM buildrequests"
                                " WHERE id IN " + self.parmlist(len(batch)))
                t.execute(q, batch)

            # now, does this cause any buildsets to complete?
            q = self.quoteq("SELECT bs.id"
                            " FROM buildsets AS bs, buildrequests AS br"
                            " WHERE br.buildsetid=bs.id AND bs.complete=0"
                            "  AND br.id in "
                            + self.parmlist(len(batch)))
            t.execute(q, batch)
            bsids = [bsid for (bsid,) in t.fetchall()]
            for bsid in bsids:
                self._check_buildset(t, bsid, now)


    def _check_buildset(self, t, bsid, now):
        q = self.quoteq("SELECT br.complete,br.results"
                        " FROM buildsets AS bs, buildrequests AS br"
                        " WHERE bs.complete=0"
                        "  AND br.buildsetid=bs.id AND bs.id=?")
        t.execute(q, (bsid,))
        results = t.fetchall()
        is_complete = True
        bs_results = SUCCESS
        for (complete, r) in results:
            if not complete:
                # still waiting
                is_complete = False
            # mark the buildset as a failure if anything worse than
            # WARNINGS resulted from any one of the buildrequests
            if r not in (SUCCESS, WARNINGS):
                bs_results = FAILURE
        if is_complete:
            # they were all successful
            q = self.quoteq("UPDATE buildsets"
                            " SET complete=1, complete_at=?, results=?"
                            " WHERE id=?")
            t.execute(q, (now, bs_results, bsid))
            # notify the master
            self.master.buildsetComplete(bsid, bs_results)

    # used by BuildSetStatus
    def get_buildrequestids_for_buildset(self, bsid):
        return self.runInteractionNow(self._txn_get_buildrequestids_for_buildset,
                                      bsid)
    def _txn_get_buildrequestids_for_buildset(self, t, bsid):
        t.execute(self.quoteq("SELECT buildername,id FROM buildrequests"
                              " WHERE buildsetid=?"),
                  (bsid,))
        return dict(t.fetchall())

    # use by Status.getBuildSets
    def examine_buildset(self, bsid):
        return self.runInteractionNow(self._txn_examine_buildset, bsid)
    def _txn_examine_buildset(self, t, bsid):
        # "finished" means complete=1 for all builds. Return False until
        # all builds are complete, then True.
        # "successful" means complete=1 and results!=FAILURE for all builds.
        # Returns None until the last success or the first failure. Returns
        # False if there is at least one failure. Returns True if all are
        # successful.
        q = self.quoteq("SELECT br.complete,br.results"
                        " FROM buildsets AS bs, buildrequests AS br"
                        " WHERE br.buildsetid=bs.id AND bs.id=?")
        t.execute(q, (bsid,))
        results = t.fetchall()
        finished = True
        successful = None
        for (c,r) in results:
            if not c:
                finished = False
            if c and r not in (SUCCESS, WARNINGS):
                successful = False
        if finished and successful is None:
            successful = True
        return (successful, finished)

    # used by BuildSetStatus.getReason, etc.
    def get_buildset_info(self, bsid):
        return self.runInteractionNow(self._txn_get_buildset_info, bsid)
    def _txn_get_buildset_info(self, t, bsid):
        q = self.quoteq("SELECT external_idstring, reason, sourcestampid,"
                        "       complete, results"
                        " FROM buildsets WHERE id=?")
        t.execute(q, (bsid,))
        res = t.fetchall()
        if res:
            (external, reason, ssid, complete, results) = res[0]
            external_idstring = str_or_none(external)
            reason = str_or_none(reason)
            complete = bool(complete)
            return (external_idstring, reason, ssid, complete, results)
        return None # shouldn't happen

    # used by getSourceStamp
    def getChangeNumberedNow(self, changeid, t=None):
        # this is a synchronous/blocking version of getChangeByNumber
        assert changeid >= 0
        if t:
            c = self._txn_getChangeNumberedNow(t, changeid)
        else:
            c = self.runInteractionNow(self._txn_getChangeNumberedNow, changeid)
        return c
    def _txn_getChangeNumberedNow(self, t, changeid):
        q = self.quoteq("SELECT author, comments,"
                        " is_dir, branch, revision, revlink,"
                        " when_timestamp, category,"
                        " repository, project"
                        " FROM changes WHERE changeid = ?")
        t.execute(q, (changeid,))
        rows = t.fetchall()
        if not rows:
            return None
        (who, comments,
         isdir, branch, revision, revlink,
         when, category, repository, project) = rows[0]
        branch = str_or_none(branch)
        revision = str_or_none(revision)
        q = self.quoteq("SELECT link FROM change_links WHERE changeid=?")
        t.execute(q, (changeid,))
        rows = t.fetchall()
        links = [row[0] for row in rows]
        links.sort()

        q = self.quoteq("SELECT filename FROM change_files WHERE changeid=?")
        t.execute(q, (changeid,))
        rows = t.fetchall()
        files = [row[0] for row in rows]
        files.sort()

        p = self.get_properties_from_db("change_properties", "changeid",
                                        changeid, t)
        from buildbot.changes.changes import Change
        c = Change(who=who, files=files, comments=comments, isdir=isdir,
                   links=links, revision=revision, when=when,
                   branch=branch, category=category, revlink=revlink,
                   repository=repository, project=project)
        c.properties.updateFromProperties(p)
        c.number = changeid
        return c

    def doCleanup(self):
        """
        Perform any periodic database cleanup tasks.

        @returns: Deferred
        """
        d = self.changes.pruneChanges(self.changeHorizon)
        d.addErrback(log.err, 'while pruning changes')
        return d

threadable.synchronize(DBConnector)
