# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla-specific Buildbot steps.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Brian Warner <warner@lothar.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import os, shutil

from twisted.trial import unittest
from twisted.python import failure, reflect
from twisted.internet import defer, reactor
from twisted.application import service
from buildbot import db, master
from buildbot.schedulers.manager import SchedulerManager
from buildbot.schedulers.basic import Scheduler
from buildbot.scripts import runner
from buildbot.changes.changes import OldChangeMaster, Change
from buildbot.changes.manager import ChangeManager
from buildbot.test.pollmixin import PollMixin
from buildbot.test.runutils import RunMixin
from buildbot.eventual import flushEventualQueue

class ShouldFailMixin:

    def shouldFail(self, expected_failure, which, substring,
                   callable, *args, **kwargs):
        assert substring is None or isinstance(substring, str)
        d = defer.maybeDeferred(callable, *args, **kwargs)
        def done(res):
            if isinstance(res, failure.Failure):
                res.trap(expected_failure)
                if substring:
                    self.failUnless(substring in str(res),
                                    "%s: substring '%s' not in '%s'"
                                    % (which, substring, str(res)))
                # make the Failure available to a subsequent callback, but
                # keep it from triggering an errback
                return [res]
            else:
                self.fail("%s was supposed to raise %s, not get '%s'" %
                          (which, expected_failure, res))
        d.addBoth(done)
        return d

class Base:
    def setUp(self):
        self._fn = None
        self.dbs = set()
    def shutDown(self):
        if self._fn and os.path.exists(self._fn):
            os.unlink(self._fn)
        for d in self.dbs:
            d.close()

class Create(Base, unittest.TestCase, ShouldFailMixin):

    def test_create(self):
        basedir = "db/create"
        if not os.path.isdir(basedir):
            os.makedirs(basedir)
        spec = db.DB("sqlite3", os.path.join(basedir, "db1.sqlite"))
        db.create_db(spec)
        db1 = db.open_db(spec)
        self.dbs.add(db1)
        version = db1.runQueryNow("SELECT version FROM version")[0][0]
        self.failUnlessEqual(version, 1)
        d = db1.runQuery("SELECT version FROM version")
        d.addCallback(lambda r: self.failUnlessEqual(r[0][0], 1, r))
        def _then(ign):
            db2 = db.DBConnector(spec)
            self.dbs.add(db2)
            version = db2.runQueryNow("SELECT version FROM version")[0][0]
            self.failUnlessEqual(version, 1)
            return db2.runQuery("SELECT version FROM version")
        d.addCallback(_then)
        d.addCallback(lambda r: self.failUnlessEqual(r[0][0], 1, r))
        return d

    def test_must_exist(self):
        basedir = "db/must_exist"
        if not os.path.isdir(basedir):
            os.makedirs(basedir)
        fn = self._fn = os.path.join(basedir, "nonexistent.sqlite")
        # sqlite databases spring into existence the moment you look at them,
        # so what we test here is that open_db() will not silently use such
        # an empty database.
        spec = db.DB("sqlite3", fn)
        db1 = db.DBConnector(spec) # should work
        self.dbs.add(db1)
        d = self.shouldFail(db.DatabaseNotReadyError, "must_exist",
                            "cannot use empty database",
                            db.open_db, spec)
        return d

    def test_must_not_exist(self):
        basedir = "db/must_not_exist"
        if not os.path.isdir(basedir):
            os.makedirs(basedir)
        spec = db.DB("sqlite3", os.path.join(basedir, "existing.sqlite"))
        db.create_db(spec)
        d = self.shouldFail(db.DBAlreadyExistsError, "must_not_exist",
                            "Refusing to touch an existing database",
                            db.create_db, spec)
        return d

    def test_old_version(self):
        basedir = "db/old_version"
        if not os.path.isdir(basedir):
            os.makedirs(basedir)
        fn = self._fn = os.path.join(basedir, "oldversion.sqlite")
        spec = db.DB("sqlite3", fn)
        dbapi = reflect.namedModule(db.get_sqlite_dbapi_name())
        conn = dbapi.connect(fn)
        c = conn.cursor()
        c.execute("CREATE TABLE version (version INTEGER);")
        c.execute("INSERT INTO version VALUES (0);")
        conn.commit()
        del conn
        d = self.shouldFail(db.DatabaseNotReadyError, "old_version",
                            "db is at version 0, I only know 1",
                            db.open_db, spec)
        return d

class Generic(Base, unittest.TestCase):
    def test_generic(self):
        basedir = "db/generic"
        if not os.path.isdir(basedir):
            os.makedirs(basedir)
        spec = db.DB("sqlite3", os.path.join(basedir, "db1.sqlite"))
        db.create_db(spec)
        db1 = db.open_db(spec)
        self.dbs.add(db1)
        db1.generic_set("key1", {"value": "is json"})
        self.failUnlessEqual(db1.generic_get("key1"), {"value": "is json"})
        self.failUnlessEqual(db1.generic_get("missing", 123), 123)
        db1.generic_set("key1", ["newvalue"])
        self.failUnlessEqual(db1.generic_get("key1"), ["newvalue"])


class FakeMaster(service.MultiService):
    def __init__(self):
        service.MultiService.__init__(self)
        self._changesWereAdded_calls = 0
        self._triggerSlaveManager_calls = 0
    def changesWereAdded(self):
        self._changesWereAdded_calls += 1
    def addChange(self, change):
        self.db.addChangeToDatabase(change)
    def triggerSlaveManager(self):
        self._triggerSlaveManager_calls += 1

class MigrateChanges(Base, unittest.TestCase):
    def create_pickle(self):
        # ugh, what was I thinking? pickles? with class instances? ick.
        cm = OldChangeMaster()
        cm.basedir = "db/migrate"
        os.makedirs(cm.basedir)
        c1 = Change(who="brian", files=["foo.c", "subdir/bar.c"],
                    comments="first change",
                    revision="1234")
        del c1.revlink
        c2 = Change(who="brian", files=["foo.c"],
                    comments="second change",
                    revision="1235", branch="release",
                    links=["url1", "url2"], revlink="url3",
                    properties={"who": "what"},
                    category="nifty")
        cm.addChange(c1)
        cm.addChange(c2)
        cm.saveYourself() # db/migrate/changes.pck
        return os.path.join(cm.basedir, "changes.pck")

    def test_migrate(self):
        fn = self.create_pickle()
        spec = db.DB("sqlite3", "db/migrate/state.sqlite")
        db.create_db(spec)
        the_db = db.open_db(spec)
        self.dbs.add(the_db)
        runner.migrate_changes_pickle_to_db(fn, the_db, silent=True)
        m = ChangeManager()
        m.parent = FakeMaster()
        m.parent.db = the_db

        c1 = m.getChangeNumberedNow(1)
        self.failUnlessEqual(c1.who, "brian")
        self.failUnlessEqual(c1.files, sorted(["foo.c", "subdir/bar.c"]))
        self.failUnlessEqual(c1.comments, "first change")
        self.failUnlessEqual(c1.revision, "1234")
        # more..

        c3 = Change("alice", ["baz.c"], "third change", revision="abcd")
        m.addChange(c3)

class Scheduling(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.harness_basedir = None
        self.parent = service.MultiService()
        self.parent.startService()

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        if self.harness_basedir:
            shutil.rmtree(self.harness_basedir)
        return defer.maybeDeferred(self.parent.stopService)

    def build_harness(self, basedir):
        self.harness_basedir = basedir
        m = FakeMaster()
        m.setServiceParent(self.parent)
        if not os.path.isdir(basedir):
            os.makedirs(basedir)
        spec = db.DB("sqlite3", os.path.join(basedir, "state.sqlite"))
        db.create_db(spec)
        m.db = db.open_db(spec)
        m.change_svc = cm = ChangeManager()
        cm.setServiceParent(m)
        sm = SchedulerManager(m, m.db, cm)
        sm.setServiceParent(m)
        return m, cm, sm

    def get_buildrequests(self, m, cm):
        r = m.db.runQueryNow("SELECT br.id,bs.sourcestampid"
                             " FROM buildrequests AS br, buildsets AS bs"
                             " WHERE br.buildsetid=bs.id")
        requests = []
        for (brid, ssid) in r:
            ss = m.db.getSourceStampNumberedNow(ssid)
            requests.append((brid, ss))
        return requests

    def test_update(self):
        m, cm, sm = self.build_harness("db/scheduling/update")
        s1 = Scheduler("one", branch=None, treeStableTimer=None,
                       builderNames=["builder-one"])
        s2 = Scheduler("two", branch=None, treeStableTimer=None,
                       builderNames=["builder-two"])
        s2a = Scheduler("two", branch=None, treeStableTimer=None,
                        builderNames=["builder-two-other"])
        d = sm.updateSchedulers([s1])
        def _check1(ign):
            all = list(sm)
            self.failUnlessEqual(len(all), 1)
            return sm.updateSchedulers([s1])
        d.addCallback(_check1)
        def _check2(ign):
            all = list(sm)
            self.failUnlessEqual(len(all), 1)
            return sm.updateSchedulers([s1, s2])
        d.addCallback(_check2)
        def _check3(ign):
            all = list(sm)
            self.failUnlessEqual(len(all), 2)
            return sm.updateSchedulers([s1, s2a])
        d.addCallback(_check3)
        def _check4(ign):
            all = list(sm)
            all.sort(key=lambda x: x.name)
            self.failUnlessEqual(len(all), 2)
            self.failUnlessEqual(all[0].name, "one")
            self.failUnlessEqual(all[1].builderNames, ["builder-two-other"])
        d.addCallback(_check4)
        d.addCallback(flushEventualQueue)
        return d

    def stall(self, res, timeout):
        d = defer.Deferred()
        reactor.callLater(timeout, d.callback, res)
        return d

    def test_immediate(self):
        m, cm, sm = self.build_harness("db/scheduler/immediate")
        def fileIsImportant(c):
            for fn in c.files:
                if not fn.endswith(".txt"):
                    return True
            return False
        # we set the treeStableTimer to something tiny, since "None" has a
        # special meaning ("do not merge Changes")
        s = Scheduler("one", branch=None, treeStableTimer=0.01,
                      builderNames=["builder-one"],
                      fileIsImportant=fileIsImportant)
        d = sm.updateSchedulers([s])

        # there are no changes in the database, so the scheduler should want
        # to keep sleeping.
        d.addCallback(lambda ign: s.run())
        def _sleep_forever_not_build(res):
            self.failUnlessEqual(res, None)
            pending = self.get_buildrequests(m, cm)
            self.failIf(pending)
        d.addCallback(_sleep_forever_not_build)

        # now add one change. The change is "unimportant", so no build will
        # be run.
        c1 = Change(who="brian", files=["docs.txt"],
                    comments="doc change",
                    revision="1234")
        d.addCallback(lambda ign: cm.addChange(c1))
        d.addCallback(lambda ign: s.run())
        d.addCallback(_sleep_forever_not_build)
        # running it again should tell us the same thing
        d.addCallback(lambda ign: s.run())
        d.addCallback(_sleep_forever_not_build)

        # now add a second change which evaluates as "important", which
        # should trigger a build with both changes after the treeStableTimer
        # has passed, which should be quickly
        c2 = Change(who="brian", files=["foo.c", "subdir/bar.c"],
                    comments="second change",
                    revision="1235")
        d.addCallback(lambda ign: cm.addChange(c2))
        # stall here to let the treeStableTimer expire
        d.addCallback(self.stall, 1.0)
        d.addCallback(lambda ign: s.run())
        def _build_not_sleep(res):
            # a BuildRequest should be pushed, and the Scheduler should go
            # back to sleep
            self.failUnlessEqual(res, None)
            pending = self.get_buildrequests(m, cm)
            self.failUnlessEqual(len(pending), 1)
            changes = pending[0][1].changes
            self.failUnlessEqual(len(changes), 2)
            self.failUnlessEqual(changes[0].revision, "1234")
            self.failUnlessEqual(changes[0].files, ["docs.txt"])
            self.failUnlessEqual(changes[1].revision, "1235")
            self.failUnlessIn("foo.c", changes[1].files)
            self.failUnlessIn("subdir/bar.c", changes[1].files)
        d.addCallback(_build_not_sleep)
        # running it again should not do anything
        d.addCallback(lambda ign: s.run())
        def _build_and_sleep(res):
            self.failUnlessEqual(res, None)
            pending = self.get_buildrequests(m, cm)
            self.failUnlessEqual(len(pending), 1)
        d.addCallback(_build_and_sleep)

        return d


    def test_stabletimer(self):
        m, cm, sm = self.build_harness("db/scheduler/stabletimer")
        s = Scheduler("one", branch=None, treeStableTimer=30,
                      builderNames=["builder-one"])
        d = sm.updateSchedulers([s])

        # there are no changes in the database, so the scheduler should want
        # to keep sleeping.
        d.addCallback(lambda ign: s.run())
        def _sleep_forever_not_build(res):
            self.failUnlessEqual(res, None)
            pending = self.get_buildrequests(m, cm)
            self.failIf(pending)
        d.addCallback(_sleep_forever_not_build)

        # now add one change. The scheduler should want to wait for the
        # tree-stable timer to fire.
        c1 = Change(who="brian", files=["foo.c"],
                    comments="first change",
                    revision="1234")
        d.addCallback(lambda ign: cm.addChange(c1))
        d.addCallback(lambda ign: s.run())
        def _sleep_not_build(res):
            # the scheduler should tell us that they want to be woken up in
            # 30 seconds. This test would be much too fragile if we actually
            # asserted anything about its value, though.
            self.failUnlessEqual(type(res), float)
            pending = self.get_buildrequests(m, cm)
            self.failIf(pending)
        d.addCallback(_sleep_not_build)

        # running it again should tell us roughly the same thing
        d.addCallback(lambda ign: s.run())
        d.addCallback(_sleep_not_build)
        def _reduce_timer(res):
            # artificially lower the tree-stable-timer value
            s.treeStableTimer = 0
        d.addCallback(_reduce_timer)
        d.addCallback(lambda ign: s.run())
        def _build_not_sleep(res):
            # a BuildRequest should be pushed, and the Scheduler should go
            # back to sleep
            self.failUnlessEqual(res, None)
            pending = self.get_buildrequests(m, cm)
            self.failUnlessEqual(len(pending), 1)
            changes = pending[0][1].changes
            self.failUnlessEqual(len(changes), 1)
            self.failUnlessEqual(changes[0].revision, "1234")
            self.failUnlessEqual(changes[0].files, ["foo.c"])
        d.addCallback(_build_not_sleep)

        return d

    def test_many_changes(self):
        m, cm, sm = self.build_harness("db/scheduler/many_changes")
        s = Scheduler("one", branch=None, treeStableTimer=0.01,
                      builderNames=["builder-one"])
        d = sm.updateSchedulers([s])

        # add ten changes, then process them all at once. Sometimes the
        # database connector has problems with lots of queries happening
        # simultaneously.
        for i in range(10):
            c = Change(who="brian", files=["foo%d.txt" % i],
                       comments="change %d" % i,
                       revision="%d" % (i+10))
            d.addCallback(lambda ign, c=c: cm.addChange(c))
        d.addCallback(self.stall, 1.0)
        d.addCallback(lambda ign: s.run())
        def _build_not_sleep(res):
            # a BuildRequest should be pushed, and the Scheduler should go
            # back to sleep
            self.failUnlessEqual(res, None)
            pending = self.get_buildrequests(m, cm)
            self.failUnlessEqual(len(pending), 1)
            changes = pending[0][1].changes
            self.failUnlessEqual(len(changes), 10)
        d.addCallback(_build_not_sleep)

        return d

config_1 = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.schedulers.basic import Scheduler
s = factory.s

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['slavePortnum'] = 0
c['schedulers'] = [Scheduler('one', branch=None, treeStableTimer=None,
                             builderNames=['b1'])]

f1 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=1)])

c['builders'] = [
    {'name': 'b1', 'slavenames': ['bot1'],
     'builddir': 'b1', 'factory': f1},
    ]
"""

class Building(RunMixin, unittest.TestCase, PollMixin):

    def setUp(self):
        # skip the usual RunMixin.setUp, because we want a BuildMaster with a
        # distinct basedir, but we do want connectSlave() and tearDown().
        self.basedir = "db/building/one"

    def tearDown(self):
        RunMixin.tearDown(self)
        # there are extant builders that will still try to write to this
        # directory, leading to a test failure -> test disabled
        shutil.rmtree(self.basedir)

    def create_master(self):
        # This eventually needs to be merged into RunMixin.
        os.makedirs(self.basedir)
        self.slaves = {}
        spec = db.DB("sqlite3", os.path.join(self.basedir, "state.sqlite"))
        db.create_db(spec)
        self.master = master.BuildMaster(self.basedir, db=spec)
        return self.master

    def disabled_test_one(self): # XXX disabled; see tearDown, above (bug #721)
        m = self.create_master()
        m.readConfig = True
        m.startService()
        cm = m.change_svc

        d = m.loadConfig(config_1)
        d2 = m.botmaster.loop.when_quiet()
        d.addCallback(lambda ign: d2)
        def _then(ign):
            b = m.botmaster.builders["b1"]
            self.failUnlessEqual(b.run_count, 1) # once at startup
            s = list(m.scheduler_manager)[0]
            self.failUnlessEqual(s.name, "one")
            c1 = Change(who="brian", files=["file.py"], comments="change",
                        revision="1234")
            cm.addChange(c1) # this triggers the scheduler loop
            d = m.scheduler_manager.when_quiet()
            d2 = m.botmaster.loop.when_quiet()
            d.addCallback(lambda ign: d2)
            def _check_no_slaves(ign):
                self.failUnlessEqual(b.run_count, 2)
                #self.failUnlessEqual(m._triggerSlaveManager_calls, 1)
                # the builder has no slaves yet, so it won't do anything
                d2 = m.botmaster.loop.when_quiet()
                d = self.connectSlave(["b1"]) # this should trigger a run()
                d.addCallback(lambda ign: d2)
                return d
            d.addCallback(_check_no_slaves)
            def _building_f():
                return bool(b.building)
            d.addCallback(lambda ign: self.poll(_building_f))
            def _later(ign):
                self.failUnlessEqual(b.run_count, 3)
                # at this point, a build ought to be running. Wait for it to
                # finish.
                self.failUnlessEqual(len(b.building), 1)
                b1 = b.building[0]
                self.failUnlessEqual(b1.requests[0].source.changes[0].files,
                                     ["file.py"])
                # but the ping is still running, and the build doesn't really
                # "start" until it finishes, which means we can't get a
                # BuildStatus yet, which means we can't do:
                #return b1.getStatus().waitUntilFinished()
                def _finished_f():
                    return b1.build_status and b1.build_status.isFinished()
                return self.poll(_finished_f)
            d.addCallback(_later)
            def _finished(ign):
                bs = m.getStatus().getBuilder("b1").getBuild(-1)
                ss = bs.getSourceStamp()
                self.failUnlessEqual(len(ss.changes), 1)
                c1 = ss.changes[0]
                self.failUnlessEqual(c1.who, "brian")
                self.failUnlessEqual(c1.files, ["file.py"])
                # the slave becoming idle should trigger another run()
                def _finished_f():
                    return b.run_count == 4
                return self.poll(_finished_f)
            d.addCallback(_finished)
            return d
        d.addCallback(_then)
        return d
