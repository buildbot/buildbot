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

import mock

from buildbot import config
from buildbot import locks
from buildbot.buildworker import base
from buildbot.test.fake import bworkermanager
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakeprotocol
from buildbot.test.fake import worker
from buildbot.test.util import interfaces
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.trial import unittest


class ConcreteBuildWorker(base.AbstractBuildWorker):
    pass


class BuildWorkerInterfaceTests(interfaces.InterfaceTests):

    def test_attr_workername(self):
        self.failUnless(hasattr(self.sl, 'workername'))

    def test_attr_properties(self):
        self.failUnless(hasattr(self.sl, 'properties'))

    @defer.inlineCallbacks
    def test_attr_worker_basedir(self):
        yield self.callAttached()
        self.assertIsInstance(self.sl.worker_basedir, str)

    @defer.inlineCallbacks
    def test_attr_path_module(self):
        yield self.callAttached()
        self.failUnless(hasattr(self.sl, 'path_module'))

    @defer.inlineCallbacks
    def test_attr_worker_system(self):
        yield self.callAttached()
        self.failUnless(hasattr(self.sl, 'worker_system'))

    def test_signature_acquireLocks(self):
        @self.assertArgSpecMatches(self.sl.acquireLocks)
        def acquireLocks(self):
            pass

    def test_signature_releaseLocks(self):
        @self.assertArgSpecMatches(self.sl.releaseLocks)
        def releaseLocks(self):
            pass

    def test_signature_attached(self):
        @self.assertArgSpecMatches(self.sl.attached)
        def attached(self, conn):
            pass

    def test_signature_detached(self):
        @self.assertArgSpecMatches(self.sl.detached)
        def detached(self):
            pass

    def test_signature_addWorkerBuilder(self):
        @self.assertArgSpecMatches(self.sl.addWorkerBuilder)
        def addWorkerBuilder(self, sb):
            pass

    def test_signature_removeWorkerBuilder(self):
        @self.assertArgSpecMatches(self.sl.removeWorkerBuilder)
        def removeWorkerBuilder(self, sb):
            pass

    def test_signature_buildFinished(self):
        @self.assertArgSpecMatches(self.sl.buildFinished)
        def buildFinished(self, sb):
            pass

    def test_signature_canStartBuild(self):
        @self.assertArgSpecMatches(self.sl.canStartBuild)
        def canStartBuild(self):
            pass


class RealBuildWorkerItfc(unittest.TestCase, BuildWorkerInterfaceTests):

    def setUp(self):
        self.sl = ConcreteBuildWorker('sl', 'pa')

    def callAttached(self):
        self.master = fakemaster.make_master(testcase=self, wantData=True)
        self.master.buildworkers.disownServiceParent()
        self.buildworkers = bworkermanager.FakeBuildworkerManager()
        self.buildworkers.setServiceParent(self.master)
        self.master.buildworkers = self.buildworkers
        self.sl.setServiceParent(self.master.buildworkers)
        self.conn = fakeprotocol.FakeConnection(self.master, self.sl)
        return self.sl.attached(self.conn)


class FakeBuildWorkerItfc(unittest.TestCase, BuildWorkerInterfaceTests):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self)
        self.sl = worker.FakeWorker(self.master)

    def callAttached(self):
        self.conn = fakeprotocol.FakeConnection(self.master, self.sl)
        return self.sl.attached(self.conn)


class TestAbstractBuildWorker(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, wantData=True,
                                             testcase=self)
        self.botmaster = self.master.botmaster
        self.master.buildworkers.disownServiceParent()
        self.buildworkers = self.master.buildworkers = bworkermanager.FakeBuildworkerManager()
        self.buildworkers.setServiceParent(self.master)
        self.clock = task.Clock()
        self.patch(reactor, 'callLater', self.clock.callLater)
        self.patch(reactor, 'seconds', self.clock.seconds)

    def createBuildworker(self, name='bot', password='pass', attached=False, configured=True, **kwargs):
        worker = ConcreteBuildWorker(name, password, **kwargs)
        if configured:
            worker.setServiceParent(self.buildworkers)
        if attached:
            worker.conn = fakeprotocol.FakeConnection(self.master, worker)
        return worker

    def test_constructor_minimal(self):
        bs = ConcreteBuildWorker('bot', 'pass')
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.max_builds, None)
        self.assertEqual(bs.notify_on_missing, [])
        self.assertEqual(bs.missing_timeout, 10 * 60)
        self.assertEqual(bs.properties.getProperty('workername'), 'bot')
        self.assertEqual(bs.access, [])

    def test_constructor_full(self):
        lock1, lock2 = mock.Mock(name='lock1'), mock.Mock(name='lock2')
        bs = ConcreteBuildWorker('bot', 'pass',
                                max_builds=2,
                                notify_on_missing=['me@me.com'],
                                missing_timeout=120,
                                properties={'a': 'b'},
                                locks=[lock1, lock2])

        self.assertEqual(bs.max_builds, 2)
        self.assertEqual(bs.notify_on_missing, ['me@me.com'])
        self.assertEqual(bs.missing_timeout, 120)
        self.assertEqual(bs.properties.getProperty('a'), 'b')
        self.assertEqual(bs.access, [lock1, lock2])

    def test_constructor_notify_on_missing_not_list(self):
        bs = ConcreteBuildWorker('bot', 'pass',
                                notify_on_missing='foo@foo.com')
        # turned into a list:
        self.assertEqual(bs.notify_on_missing, ['foo@foo.com'])

    def test_constructor_notify_on_missing_not_string(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          ConcreteBuildWorker('bot', 'pass',
                                             notify_on_missing=['a@b.com', 13]))

    @defer.inlineCallbacks
    def do_test_reconfigService(self, old, new, existingRegistration=True):
        old.parent = self.master
        if existingRegistration:
            old.registration = bworkermanager.FakeBuildworkerRegistration(old)
        old.missing_timer = mock.Mock(name='missing_timer')
        yield old.startService()

        yield old.reconfigServiceWithSibling(new)

    @defer.inlineCallbacks
    def test_reconfigService_attrs(self):
        old = self.createBuildworker('bot', 'pass',
                                    max_builds=2,
                                    notify_on_missing=['me@me.com'],
                                    missing_timeout=120,
                                    properties={'a': 'b'})
        new = self.createBuildworker('bot', 'pass', configured=False,
                                    max_builds=3,
                                    notify_on_missing=['her@me.com'],
                                    missing_timeout=121,
                                    properties={'a': 'c'})

        old.updateWorker = mock.Mock(side_effect=lambda: defer.succeed(None))

        yield self.do_test_reconfigService(old, new)

        self.assertEqual(old.max_builds, 3)
        self.assertEqual(old.notify_on_missing, ['her@me.com'])
        self.assertEqual(old.missing_timeout, 121)
        self.assertEqual(old.properties.getProperty('a'), 'c')
        self.assertEqual(old.registration.updates, ['bot'])
        self.assertTrue(old.updateWorker.called)

    @defer.inlineCallbacks
    def test_reconfigService_has_properties(self):
        old = self.createBuildworker(name="bot", password="pass")

        yield self.do_test_reconfigService(old, old)
        self.assertTrue(old.properties.getProperty('workername'), 'bot')

    @defer.inlineCallbacks
    def test_reconfigService_initial_registration(self):
        old = self.createBuildworker('bot', 'pass')
        yield self.do_test_reconfigService(old, old,
                                           existingRegistration=False)
        self.assertIn('bot', self.master.buildworkers.registrations)
        self.assertEqual(old.registration.updates, ['bot'])

    @defer.inlineCallbacks
    def test_stopService(self):
        worker = self.createBuildworker()
        yield worker.startService()

        reg = worker.registration

        yield worker.stopService()

        self.assertTrue(reg.unregistered)
        self.assertEqual(worker.registration, None)

    # FIXME: Test that reconfig properly deals with
    #   1) locks
    #   2) telling worker about builder
    #   3) missing timer
    # in both the initial config and a reconfiguration.

    def test_startMissingTimer_no_parent(self):
        bs = ConcreteBuildWorker('bot', 'pass',
                                notify_on_missing=['abc'],
                                missing_timeout=10)
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_startMissingTimer_no_timeout(self):
        bs = ConcreteBuildWorker('bot', 'pass',
                                notify_on_missing=['abc'],
                                missing_timeout=0)
        bs.parent = mock.Mock()
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_startMissingTimer_no_notify(self):
        bs = ConcreteBuildWorker('bot', 'pass',
                                missing_timeout=3600)
        bs.parent = mock.Mock()
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_missing_timer(self):
        bs = ConcreteBuildWorker('bot', 'pass',
                                notify_on_missing=['abc'],
                                missing_timeout=100)
        bs.parent = mock.Mock()
        bs.startMissingTimer()
        self.assertNotEqual(bs.missing_timer, None)
        bs.stopMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    @defer.inlineCallbacks
    def test_setServiceParent_started(self):
        master = self.master
        bsmanager = master.buildworkers
        yield master.startService()
        bs = ConcreteBuildWorker('bot', 'pass')
        bs.setServiceParent(bsmanager)
        self.assertEqual(bs.manager, bsmanager)
        self.assertEqual(bs.parent, bsmanager)
        self.assertEqual(bsmanager.master, master)
        self.assertEqual(bs.master, master)

    @defer.inlineCallbacks
    def test_setServiceParent_masterLocks(self):
        """
        http://trac.buildbot.net/ticket/2278
        """
        master = self.master
        bsmanager = master.buildworkers
        yield master.startService()
        lock = locks.MasterLock('masterlock')
        bs = ConcreteBuildWorker('bot', 'pass', locks=[lock.access("counting")])
        bs.setServiceParent(bsmanager)

    @defer.inlineCallbacks
    def test_setServiceParent_workerLocks(self):
        """
        http://trac.buildbot.net/ticket/2278
        """
        master = self.master
        bsmanager = master.buildworkers
        yield master.startService()
        lock = locks.WorkerLock('lock')
        bs = ConcreteBuildWorker('bot', 'pass', locks=[lock.access("counting")])
        bs.setServiceParent(bsmanager)

    @defer.inlineCallbacks
    def test_startService_getWorkerInfo_empty(self):
        worker = self.createBuildworker()
        yield worker.startService()

        self.assertEqual(worker.worker_status.getAdmin(), None)
        self.assertEqual(worker.worker_status.getHost(), None)
        self.assertEqual(worker.worker_status.getAccessURI(), None)
        self.assertEqual(worker.worker_status.getVersion(), None)

        # check that a new worker row was added for this buildworker
        bs = yield self.master.db.buildworkers.getBuildworker(name='bot')
        self.assertEqual(bs['name'], 'bot')

    @defer.inlineCallbacks
    def test_startService_getWorkerInfo_fromDb(self):
        self.master.db.insertTestData([
            fakedb.Buildworker(id=9292, name='bot', info={
                'admin': 'TheAdmin',
                'host': 'TheHost',
                'access_uri': 'TheURI',
                'version': 'TheVersion'
            })
        ])
        worker = self.createBuildworker()

        yield worker.startService()

        self.assertEqual(worker.buildworkerid, 9292)
        self.assertEqual(worker.worker_status.getAdmin(), 'TheAdmin')
        self.assertEqual(worker.worker_status.getHost(), 'TheHost')
        self.assertEqual(worker.worker_status.getAccessURI(), 'TheURI')
        self.assertEqual(worker.worker_status.getVersion(), 'TheVersion')

    @defer.inlineCallbacks
    def test_attached_remoteGetWorkerInfo(self):
        worker = self.createBuildworker()
        yield worker.startService()

        ENVIRON = {}
        COMMANDS = {'cmd1': '1', 'cmd2': '1'}

        conn = fakeprotocol.FakeConnection(worker.master, worker)
        conn.info = {
            'admin': 'TheAdmin',
            'host': 'TheHost',
            'access_uri': 'TheURI',
            'environ': ENVIRON,
            'basedir': 'TheBaseDir',
            'system': 'TheWorkerSystem',
            'version': 'version',
            'worker_commands': COMMANDS,
        }
        yield worker.attached(conn)

        # check the values get set right
        self.assertEqual(worker.worker_status.getAdmin(), "TheAdmin")
        self.assertEqual(worker.worker_status.getHost(), "TheHost")
        self.assertEqual(worker.worker_status.getAccessURI(), "TheURI")
        self.assertEqual(worker.worker_environ, ENVIRON)
        self.assertEqual(worker.worker_basedir, 'TheBaseDir')
        self.assertEqual(worker.worker_system, 'TheWorkerSystem')
        self.assertEqual(worker.worker_commands, COMMANDS)

    @defer.inlineCallbacks
    def test_attached_callsMaybeStartBuildsForWorker(self):
        worker = self.createBuildworker()
        yield worker.startService()
        yield worker.reconfigServiceWithSibling(worker)

        conn = fakeprotocol.FakeConnection(worker.master, worker)
        conn.info = {}
        yield worker.attached(conn)

        self.assertEqual(self.botmaster.buildsStartedForWorkers, ["bot"])

    @defer.inlineCallbacks
    def test_attached_workerInfoUpdates(self):
        # put in stale info:
        self.master.db.insertTestData([
            fakedb.Buildworker(name='bot', info={
                'admin': 'WrongAdmin',
                'host': 'WrongHost',
                'access_uri': 'WrongURI',
                'version': 'WrongVersion'
            })
        ])
        worker = self.createBuildworker()
        yield worker.startService()

        conn = fakeprotocol.FakeConnection(worker.master, worker)
        conn.info = {
            'admin': 'TheAdmin',
            'host': 'TheHost',
            'access_uri': 'TheURI',
            'version': 'TheVersion',
        }
        yield worker.attached(conn)

        self.assertEqual(worker.worker_status.getAdmin(), 'TheAdmin')
        self.assertEqual(worker.worker_status.getHost(), 'TheHost')
        self.assertEqual(worker.worker_status.getAccessURI(), 'TheURI')
        self.assertEqual(worker.worker_status.getVersion(), 'TheVersion')

        # and the db is updated too:
        buildworker = yield self.master.db.buildworkers.getBuildworker(name="bot")

        self.assertEqual(buildworker['workerinfo']['admin'], 'TheAdmin')
        self.assertEqual(buildworker['workerinfo']['host'], 'TheHost')
        self.assertEqual(buildworker['workerinfo']['access_uri'], 'TheURI')
        self.assertEqual(buildworker['workerinfo']['version'], 'TheVersion')

    @defer.inlineCallbacks
    def test_worker_shutdown(self):
        worker = self.createBuildworker(attached=True)
        yield worker.startService()

        yield worker.shutdown()
        self.assertEqual(worker.conn.remoteCalls, [('remoteSetBuilderList', []), ('remoteShutdown',)])

    @defer.inlineCallbacks
    def test_worker_shutdown_not_connected(self):
        worker = self.createBuildworker(attached=False)
        yield worker.startService()

        # No exceptions should be raised here
        yield worker.shutdown()

    @defer.inlineCallbacks
    def test_shutdownRequested(self):
        worker = self.createBuildworker(attached=False)
        yield worker.startService()

        yield worker.shutdownRequested()
        self.assertEqual(worker.worker_status.getGraceful(), True)
