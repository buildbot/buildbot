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

from parameterized import parameterized

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot import locks
from buildbot.machine.base import Machine
from buildbot.plugins import util
from buildbot.process import properties
from buildbot.secrets.manager import SecretManager
from buildbot.test import fakedb
from buildbot.test.fake import bworkermanager
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakeprotocol
from buildbot.test.fake import worker
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import interfaces
from buildbot.test.util import logging
from buildbot.worker import AbstractLatentWorker
from buildbot.worker import base


class ConcreteWorker(base.AbstractWorker):
    pass


class FakeBuilder:
    def getBuilderId(self):
        return defer.succeed(1)


class WorkerInterfaceTests(interfaces.InterfaceTests):

    def test_attr_workername(self):
        self.assertTrue(hasattr(self.wrk, 'workername'))

    def test_attr_properties(self):
        self.assertTrue(hasattr(self.wrk, 'properties'))

    def test_attr_defaultProperties(self):
        self.assertTrue(hasattr(self.wrk, 'defaultProperties'))

    @defer.inlineCallbacks
    def test_attr_worker_basedir(self):
        yield self.callAttached()
        self.assertIsInstance(self.wrk.worker_basedir, str)

    @defer.inlineCallbacks
    def test_attr_path_module(self):
        yield self.callAttached()
        self.assertTrue(hasattr(self.wrk, 'path_module'))

    @defer.inlineCallbacks
    def test_attr_worker_system(self):
        yield self.callAttached()
        self.assertTrue(hasattr(self.wrk, 'worker_system'))

    def test_signature_acquireLocks(self):
        @self.assertArgSpecMatches(self.wrk.acquireLocks)
        def acquireLocks(self):
            pass

    def test_signature_releaseLocks(self):
        @self.assertArgSpecMatches(self.wrk.releaseLocks)
        def releaseLocks(self):
            pass

    def test_signature_attached(self):
        @self.assertArgSpecMatches(self.wrk.attached)
        def attached(self, conn):
            pass

    def test_signature_detached(self):
        @self.assertArgSpecMatches(self.wrk.detached)
        def detached(self):
            pass

    def test_signature_addWorkerForBuilder(self):
        @self.assertArgSpecMatches(self.wrk.addWorkerForBuilder)
        def addWorkerForBuilder(self, wfb):
            pass

    def test_signature_removeWorkerForBuilder(self):
        @self.assertArgSpecMatches(self.wrk.removeWorkerForBuilder)
        def removeWorkerForBuilder(self, wfb):
            pass

    def test_signature_buildFinished(self):
        @self.assertArgSpecMatches(self.wrk.buildFinished)
        def buildFinished(self, wfb):
            pass

    def test_signature_canStartBuild(self):
        @self.assertArgSpecMatches(self.wrk.canStartBuild)
        def canStartBuild(self):
            pass


class RealWorkerItfc(TestReactorMixin, unittest.TestCase, WorkerInterfaceTests):

    def setUp(self):
        self.setup_test_reactor()
        self.wrk = ConcreteWorker('wrk', 'pa')

    @defer.inlineCallbacks
    def callAttached(self):
        self.master = fakemaster.make_master(self, wantData=True)
        yield self.master.workers.disownServiceParent()
        self.workers = bworkermanager.FakeWorkerManager()
        yield self.workers.setServiceParent(self.master)
        self.master.workers = self.workers
        yield self.wrk.setServiceParent(self.master.workers)
        self.conn = fakeprotocol.FakeConnection(self.wrk)
        yield self.wrk.attached(self.conn)


class FakeWorkerItfc(TestReactorMixin, unittest.TestCase,
                     WorkerInterfaceTests):

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        self.wrk = worker.FakeWorker(self.master)

    def callAttached(self):
        self.conn = fakeprotocol.FakeConnection(self.wrk)
        return self.wrk.attached(self.conn)


class TestAbstractWorker(logging.LoggingMixin, TestReactorMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.setUpLogging()
        self.master = fakemaster.make_master(self, wantDb=True, wantData=True)
        self.botmaster = self.master.botmaster
        yield self.master.workers.disownServiceParent()
        self.workers = self.master.workers = bworkermanager.FakeWorkerManager()
        yield self.workers.setServiceParent(self.master)

    @defer.inlineCallbacks
    def createWorker(self, name='bot', password='pass', attached=False, configured=True, **kwargs):
        worker = ConcreteWorker(name, password, **kwargs)
        if configured:
            yield worker.setServiceParent(self.workers)
        if attached:
            worker.conn = fakeprotocol.FakeConnection(worker)
        return worker

    @defer.inlineCallbacks
    def createMachine(self, name, configured=True, **kwargs):
        machine = Machine(name)
        if configured:
            yield machine.setServiceParent(self.master.machine_manager)
        return machine

    @defer.inlineCallbacks
    def test_constructor_minimal(self):
        bs = yield self.createWorker('bot', 'pass')
        yield bs.startService()
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.max_builds, None)
        self.assertEqual(bs.notify_on_missing, [])
        self.assertEqual(bs.missing_timeout, ConcreteWorker.DEFAULT_MISSING_TIMEOUT)
        self.assertEqual(bs.properties.getProperty('workername'), 'bot')
        self.assertEqual(bs.access, [])

    @defer.inlineCallbacks
    def test_constructor_secrets(self):
        fake_storage_service = FakeSecretStorage()

        secret_service = SecretManager()
        secret_service.services = [fake_storage_service]
        yield secret_service.setServiceParent(self.master)

        fake_storage_service.reconfigService(secretdict={"passkey": "1234"})

        bs = yield self.createWorker('bot', util.Secret('passkey'))
        yield bs.startService()
        self.assertEqual(bs.password, '1234')

    @defer.inlineCallbacks
    def test_constructor_full(self):
        lock1, lock2 = locks.MasterLock('lock1'), locks.MasterLock('lock2')
        access1, access2 = lock1.access('counting'), lock2.access('counting')

        bs = yield self.createWorker('bot', 'pass',
                            max_builds=2,
                            notify_on_missing=['me@me.com'],
                            missing_timeout=120,
                            properties={'a': 'b'},
                            locks=[access1, access2])
        yield bs.startService()

        self.assertEqual(bs.max_builds, 2)
        self.assertEqual(bs.notify_on_missing, ['me@me.com'])
        self.assertEqual(bs.missing_timeout, 120)
        self.assertEqual(bs.properties.getProperty('a'), 'b')
        self.assertEqual(bs.access, [access1, access2])

    @defer.inlineCallbacks
    def test_constructor_notify_on_missing_not_list(self):
        bs = yield self.createWorker('bot', 'pass',
                            notify_on_missing='foo@foo.com')
        yield bs.startService()
        # turned into a list:
        self.assertEqual(bs.notify_on_missing, ['foo@foo.com'])

    def test_constructor_notify_on_missing_not_string(self):
        with self.assertRaises(config.ConfigErrors):
            ConcreteWorker('bot', 'pass', notify_on_missing=['a@b.com', 13])

    @defer.inlineCallbacks
    def do_test_reconfigService(self, old, new, existingRegistration=True):
        old.parent = self.master
        if existingRegistration:
            old.registration = bworkermanager.FakeWorkerRegistration(old)
        old.missing_timer = mock.Mock(name='missing_timer')

        if not old.running:
            yield old.startService()

        yield old.reconfigServiceWithSibling(new)

    @defer.inlineCallbacks
    def test_reconfigService_attrs(self):
        old = yield self.createWorker('bot', 'pass',
                                max_builds=2,
                                notify_on_missing=['me@me.com'],
                                missing_timeout=120,
                                properties={'a': 'b'})
        new = yield self.createWorker('bot', 'pass', configured=False,
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
        old = yield self.createWorker(name="bot", password="pass")

        yield self.do_test_reconfigService(old, old)
        self.assertTrue(old.properties.getProperty('workername'), 'bot')

    @defer.inlineCallbacks
    def test_setupProperties(self):
        props = properties.Properties()
        props.setProperty('foo', 1, 'Scheduler')
        props.setProperty('bar', 'bleh', 'Change')
        props.setProperty('omg', 'wtf', 'Builder')

        wrkr = yield self.createWorker(
            'bot', 'passwd',
            defaultProperties={'bar': 'onoes', 'cuckoo': 42})

        wrkr.setupProperties(props)

        self.assertEquals(props.getProperty('bar'), 'bleh')
        self.assertEquals(props.getProperty('cuckoo'), 42)

    @defer.inlineCallbacks
    def test_reconfigService_initial_registration(self):
        old = yield self.createWorker('bot', 'pass')
        yield self.do_test_reconfigService(old, old,
                                           existingRegistration=False)
        self.assertIn('bot', self.master.workers.registrations)
        self.assertEqual(old.registration.updates, ['bot'])

    @defer.inlineCallbacks
    def test_reconfigService_builder(self):
        old = yield self.createWorker('bot', 'pass')
        yield self.do_test_reconfigService(old, old)

        # initial configuration, there is no builder configured
        self.assertEqual(old._configured_builderid_list, [])
        workers = yield self.master.data.get(('workers',))
        self.assertEqual(len(workers[0]['configured_on']), 0)

        new = yield self.createWorker('bot', 'pass', configured=False)

        # we create a fake builder, and associate to the master
        self.botmaster.builders['bot'] = [FakeBuilder()]
        self.master.db.insertTestData([
            fakedb.Builder(id=1, name='builder'),
            fakedb.BuilderMaster(builderid=1, masterid=824)
        ])
        # on reconfig, the db should see the builder configured for this worker
        yield old.reconfigServiceWithSibling(new)
        self.assertEqual(old._configured_builderid_list, [1])
        workers = yield self.master.data.get(('workers',))
        self.assertEqual(len(workers[0]['configured_on']), 1)
        self.assertEqual(workers[0]['configured_on'][0]['builderid'], 1)

    @defer.inlineCallbacks
    def test_reconfig_service_no_machine(self):
        old = yield self.createWorker('bot', 'pass')
        self.assertIsNone(old.machine)

        yield self.do_test_reconfigService(old, old)
        self.assertIsNone(old.machine)

    @defer.inlineCallbacks
    def test_reconfig_service_with_machine_initial(self):
        machine = yield self.createMachine('machine1')
        old = yield self.createWorker('bot', 'pass', machine_name='machine1')
        self.assertIsNone(old.machine)

        yield self.do_test_reconfigService(old, old)
        self.assertIs(old.machine, machine)

    @defer.inlineCallbacks
    def test_reconfig_service_with_unknown_machine(self):
        old = yield self.createWorker('bot', 'pass', machine_name='machine1')
        self.assertIsNone(old.machine)

        yield self.do_test_reconfigService(old, old)
        self.assertLogged('Unknown machine')

    @parameterized.expand([
        ('None_to_machine_initial',
         False, None, None, 'machine1', 'machine1'),
        ('None_to_machine',
         True, None, None, 'machine1', 'machine1'),
        ('machine_to_None_initial',
         False, 'machine1', None, None, None),
        ('machine_to_None',
         True, 'machine1', 'machine1', None, None),
        ('machine_to_same_machine_initial',
         False, 'machine1', None, 'machine1', 'machine1'),
        ('machine_to_same_machine',
         True, 'machine1', 'machine1', 'machine1', 'machine1'),
        ('machine_to_another_machine_initial',
         False, 'machine1', None, 'machine2', 'machine2'),
        ('machine_to_another_machine',
         True, 'machine1', 'machine1', 'machine2', 'machine2'),
    ])
    @defer.inlineCallbacks
    def test_reconfig_service_machine(self, test_name,
                                      do_initial_self_reconfig,
                                      old_machine_name,
                                      expected_old_machine_name,
                                      new_machine_name,
                                      expected_new_machine_name):

        machine1 = yield self.createMachine('machine1')
        machine2 = yield self.createMachine('machine2')

        name_to_machine = {
            None: None,
            machine1.name: machine1,
            machine2.name: machine2,
        }

        expected_old_machine = name_to_machine[expected_old_machine_name]
        expected_new_machine = name_to_machine[expected_new_machine_name]

        old = yield self.createWorker('bot', 'pass',
                                      machine_name=old_machine_name)
        new = yield self.createWorker('bot', 'pass', configured=False,
                                      machine_name=new_machine_name)

        if do_initial_self_reconfig:
            yield self.do_test_reconfigService(old, old)

        self.assertIs(old.machine, expected_old_machine)

        yield self.do_test_reconfigService(old, new)
        self.assertIs(old.machine, expected_new_machine)

    @defer.inlineCallbacks
    def test_stopService(self):
        worker = yield self.createWorker()
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
        bs = ConcreteWorker('bot', 'pass',
                            notify_on_missing=['abc'],
                            missing_timeout=10)
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_startMissingTimer_no_timeout(self):
        bs = ConcreteWorker('bot', 'pass',
                            notify_on_missing=['abc'],
                            missing_timeout=0)
        bs.parent = mock.Mock()
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_startMissingTimer_no_notify(self):
        bs = ConcreteWorker('bot', 'pass',
                            missing_timeout=3600)
        bs.parent = mock.Mock()
        bs.running = True
        bs.startMissingTimer()
        self.assertNotEqual(bs.missing_timer, None)

    def test_missing_timer(self):
        bs = ConcreteWorker('bot', 'pass',
                            notify_on_missing=['abc'],
                            missing_timeout=100)
        bs.parent = mock.Mock()
        bs.running = True
        bs.startMissingTimer()
        self.assertNotEqual(bs.missing_timer, None)
        bs.stopMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    @defer.inlineCallbacks
    def test_setServiceParent_started(self):
        master = self.master
        bsmanager = master.workers
        yield master.startService()
        bs = ConcreteWorker('bot', 'pass')
        yield bs.setServiceParent(bsmanager)
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
        bsmanager = master.workers
        yield master.startService()
        lock = locks.MasterLock('masterlock')
        bs = ConcreteWorker('bot', 'pass', locks=[lock.access("counting")])
        yield bs.setServiceParent(bsmanager)

    @defer.inlineCallbacks
    def test_setServiceParent_workerLocks(self):
        """
        http://trac.buildbot.net/ticket/2278
        """
        master = self.master
        bsmanager = master.workers
        yield master.startService()
        lock = locks.WorkerLock('lock')
        bs = ConcreteWorker('bot', 'pass', locks=[lock.access("counting")])
        yield bs.setServiceParent(bsmanager)

    @defer.inlineCallbacks
    def test_startService_paused_true(self):
        """Test that paused state is restored on a buildbot restart"""
        self.master.db.insertTestData([
            fakedb.Worker(id=9292, name='bot', paused=1)
        ])

        worker = yield self.createWorker()

        yield worker.startService()

        self.assertTrue(worker.isPaused())
        self.assertFalse(worker._graceful)

    @defer.inlineCallbacks
    def test_startService_graceful_true(self):
        """Test that graceful state is NOT restored on a buildbot restart"""
        self.master.db.insertTestData([
            fakedb.Worker(id=9292, name='bot', graceful=1)
        ])

        worker = yield self.createWorker()

        yield worker.startService()

        self.assertFalse(worker.isPaused())
        self.assertFalse(worker._graceful)

    @defer.inlineCallbacks
    def test_startService_getWorkerInfo_empty(self):
        worker = yield self.createWorker()
        yield worker.startService()

        self.assertEqual(len(worker.info.asDict()), 0)

        # check that a new worker row was added for this worker
        bs = yield self.master.db.workers.getWorker(name='bot')
        self.assertEqual(bs['name'], 'bot')

    @defer.inlineCallbacks
    def test_startService_getWorkerInfo_fromDb(self):
        self.master.db.insertTestData([
            fakedb.Worker(id=9292, name='bot', info={
                'admin': 'TheAdmin',
                'host': 'TheHost',
                'access_uri': 'TheURI',
                'version': 'TheVersion'
            })
        ])
        worker = yield self.createWorker()

        yield worker.startService()

        self.assertEqual(worker.workerid, 9292)

        self.assertEqual(worker.info.asDict(), {
            'version': ('TheVersion', 'Worker'),
            'admin': ('TheAdmin', 'Worker'),
            'host': ('TheHost', 'Worker'),
            'access_uri': ('TheURI', 'Worker'),
        })

    @defer.inlineCallbacks
    def test_attached_remoteGetWorkerInfo(self):
        worker = yield self.createWorker()
        yield worker.startService()

        ENVIRON = {}
        COMMANDS = {'cmd1': '1', 'cmd2': '1'}

        conn = fakeprotocol.FakeConnection(worker)
        conn.info = {
            'admin': 'TheAdmin',
            'host': 'TheHost',
            'access_uri': 'TheURI',
            'environ': ENVIRON,
            'basedir': 'TheBaseDir',
            'system': 'TheWorkerSystem',
            'version': 'TheVersion',
            'worker_commands': COMMANDS,
        }
        yield worker.attached(conn)

        self.assertEqual(worker.info.asDict(), {
            'version': ('TheVersion', 'Worker'),
            'admin': ('TheAdmin', 'Worker'),
            'host': ('TheHost', 'Worker'),
            'access_uri': ('TheURI', 'Worker'),
            'basedir': ('TheBaseDir', 'Worker'),
            'system': ('TheWorkerSystem', 'Worker'),
        })

        self.assertEqual(worker.worker_environ, ENVIRON)
        self.assertEqual(worker.worker_basedir, 'TheBaseDir')
        self.assertEqual(worker.worker_system, 'TheWorkerSystem')
        self.assertEqual(worker.worker_commands, COMMANDS)

    @defer.inlineCallbacks
    def test_attached_callsMaybeStartBuildsForWorker(self):
        worker = yield self.createWorker()
        yield worker.startService()
        yield worker.reconfigServiceWithSibling(worker)

        conn = fakeprotocol.FakeConnection(worker)
        conn.info = {}
        yield worker.attached(conn)

        self.assertEqual(self.botmaster.buildsStartedForWorkers, ["bot"])

    @defer.inlineCallbacks
    def test_attached_workerInfoUpdates(self):
        # put in stale info:
        self.master.db.insertTestData([
            fakedb.Worker(name='bot', info={
                'admin': 'WrongAdmin',
                'host': 'WrongHost',
                'access_uri': 'WrongURI',
                'version': 'WrongVersion'
            })
        ])
        worker = yield self.createWorker()
        yield worker.startService()

        conn = fakeprotocol.FakeConnection(worker)
        conn.info = {
            'admin': 'TheAdmin',
            'host': 'TheHost',
            'access_uri': 'TheURI',
            'version': 'TheVersion',
        }
        yield worker.attached(conn)

        self.assertEqual(worker.info.asDict(), {
            'version': ('TheVersion', 'Worker'),
            'admin': ('TheAdmin', 'Worker'),
            'host': ('TheHost', 'Worker'),
            'access_uri': ('TheURI', 'Worker'),
        })

        # and the db is updated too:
        db_worker = yield self.master.db.workers.getWorker(name="bot")

        self.assertEqual(db_worker['workerinfo']['admin'], 'TheAdmin')
        self.assertEqual(db_worker['workerinfo']['host'], 'TheHost')
        self.assertEqual(db_worker['workerinfo']['access_uri'], 'TheURI')
        self.assertEqual(db_worker['workerinfo']['version'], 'TheVersion')

    @defer.inlineCallbacks
    def test_double_attached(self):
        worker = yield self.createWorker()
        yield worker.startService()

        conn = fakeprotocol.FakeConnection(worker)
        yield worker.attached(conn)
        conn = fakeprotocol.FakeConnection(worker)
        with self.assertRaisesRegex(
                AssertionError,
                "bot: fake_peer connecting, but we are already connected to: fake_peer"):
            yield worker.attached(conn)

    @defer.inlineCallbacks
    def test_worker_shutdown(self):
        worker = yield self.createWorker(attached=True)
        yield worker.startService()

        yield worker.shutdown()
        self.assertEqual(
            worker.conn.remoteCalls, [('remoteSetBuilderList', []), ('remoteShutdown',)])

    @defer.inlineCallbacks
    def test_worker_shutdown_not_connected(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()

        # No exceptions should be raised here
        yield worker.shutdown()

    @defer.inlineCallbacks
    def test_shutdownRequested(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()

        yield worker.shutdownRequested()
        self.assertEqual(worker._graceful, True)

    @defer.inlineCallbacks
    def test_missing_timer_missing(self):
        worker = yield self.createWorker(attached=False, missing_timeout=1)
        yield worker.startService()
        self.assertNotEqual(worker.missing_timer, None)
        yield self.reactor.advance(1)
        self.assertEqual(worker.missing_timer, None)
        self.assertEqual(len(self.master.data.updates.missingWorkers), 1)

    @defer.inlineCallbacks
    def test_missing_timer_stopped(self):
        worker = yield self.createWorker(attached=False, missing_timeout=1)
        yield worker.startService()
        self.assertNotEqual(worker.missing_timer, None)
        yield worker.stopService()
        self.assertEqual(worker.missing_timer, None)
        self.assertEqual(len(self.master.data.updates.missingWorkers), 0)

    @defer.inlineCallbacks
    def test_worker_actions_stop(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        worker.controlWorker(("worker", 1, "stop"), {'reason': "none"})
        self.assertEqual(worker._graceful, True)

    @defer.inlineCallbacks
    def test_worker_actions_kill(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        worker.controlWorker(("worker", 1, "kill"), {'reason': "none"})
        self.assertEqual(worker.conn, None)

    @defer.inlineCallbacks
    def test_worker_actions_pause(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        self.assertTrue(worker.canStartBuild())

        worker.controlWorker(("worker", 1, "pause"), {"reason": "none"})
        self.assertEqual(worker._paused, True)
        self.assertFalse(worker.canStartBuild())

        worker.controlWorker(("worker", 1, "unpause"), {"reason": "none"})
        self.assertEqual(worker._paused, False)
        self.assertTrue(worker.canStartBuild())

    @defer.inlineCallbacks
    def test_worker_quarantine_doesnt_affect_pause(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)
        self.assertFalse(worker._paused)

        # put worker into quarantine.
        # Check canStartBuild() is False, and paused state is not changed
        worker.putInQuarantine()
        self.assertFalse(worker._paused)
        self.assertFalse(worker.canStartBuild())
        self.assertIsNotNone(worker.quarantine_timer)

        # human manually pauses the worker
        worker.controlWorker(("worker", 1, "pause"), {"reason": "none"})
        self.assertTrue(worker._paused)
        self.assertFalse(worker.canStartBuild())

        # simulate wait for quarantine to end
        # Check canStartBuild() is still False, and paused state is not changed
        self.master.reactor.advance(10)
        self.assertTrue(worker._paused)
        self.assertFalse(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

    @defer.inlineCallbacks
    def test_worker_quarantine_unpausing_exits_quarantine(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

        # put worker into quarantine whilst unpaused.
        worker.putInQuarantine()
        self.assertFalse(worker._paused)
        self.assertFalse(worker.canStartBuild())

        # pause and unpause the worker
        worker.controlWorker(("worker", 1, "pause"), {"reason": "none"})
        self.assertFalse(worker.canStartBuild())
        worker.controlWorker(("worker", 1, "unpause"), {"reason": "none"})
        self.assertTrue(worker.canStartBuild())

        # put worker into quarantine whilst paused.
        worker.controlWorker(("worker", 1, "pause"), {"reason": "none"})
        worker.putInQuarantine()
        self.assertTrue(worker._paused)
        self.assertFalse(worker.canStartBuild())

        # unpause worker should start the build
        worker.controlWorker(("worker", 1, "unpause"), {"reason": "none"})
        self.assertFalse(worker._paused)
        self.assertTrue(worker.canStartBuild())

    @defer.inlineCallbacks
    def test_worker_quarantine_unpausing_doesnt_reset_timeout(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

        # pump up the quarantine wait time
        for quarantine_wait in (10, 20, 40, 80):
            worker.putInQuarantine()
            self.assertFalse(worker.canStartBuild())
            self.assertIsNotNone(worker.quarantine_timer)
            self.master.reactor.advance(quarantine_wait)
            self.assertTrue(worker.canStartBuild())
            self.assertIsNone(worker.quarantine_timer)

        # put worker into quarantine (160s)
        worker.putInQuarantine()
        self.assertFalse(worker._paused)
        self.assertFalse(worker.canStartBuild())

        # pause and unpause the worker to exit quarantine
        worker.controlWorker(("worker", 1, "pause"), {"reason": "none"})
        self.assertFalse(worker.canStartBuild())
        worker.controlWorker(("worker", 1, "unpause"), {"reason": "none"})
        self.assertFalse(worker._paused)
        self.assertTrue(worker.canStartBuild())

        # next build fails. check timeout is 320s
        worker.putInQuarantine()
        self.master.reactor.advance(319)
        self.assertFalse(worker.canStartBuild())
        self.assertIsNotNone(worker.quarantine_timer)
        self.master.reactor.advance(1)
        self.assertIsNone(worker.quarantine_timer)
        self.assertTrue(worker.canStartBuild())

    @defer.inlineCallbacks
    def test_worker_quarantine_wait_times(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

        for quarantine_wait in (10, 20, 40, 80, 160, 320, 640, 1280, 2560, 3600, 3600):
            # put worker into quarantine
            worker.putInQuarantine()
            self.assertFalse(worker.canStartBuild())
            self.assertIsNotNone(worker.quarantine_timer)

            # simulate wait just before quarantine ends
            self.master.reactor.advance(quarantine_wait - 1)
            self.assertFalse(worker.canStartBuild())
            self.assertIsNotNone(worker.quarantine_timer)

            # simulate wait to just after quarantine ends
            self.master.reactor.advance(1)
            self.assertTrue(worker.canStartBuild())
            self.assertIsNone(worker.quarantine_timer)

    @defer.inlineCallbacks
    def test_worker_quarantine_reset(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

        # pump up the quarantine wait time
        for quarantine_wait in (10, 20, 40, 80):
            worker.putInQuarantine()
            self.assertFalse(worker.canStartBuild())
            self.assertIsNotNone(worker.quarantine_timer)
            self.master.reactor.advance(quarantine_wait)
            self.assertTrue(worker.canStartBuild())
            self.assertIsNone(worker.quarantine_timer)

        # Now get a successful build
        worker.resetQuarantine()

        # the workers quarantine period should reset back to 10
        worker.putInQuarantine()
        self.master.reactor.advance(10)
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

    @defer.inlineCallbacks
    def test_worker_quarantine_whilst_quarantined(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

        # put worker in quarantine
        worker.putInQuarantine()
        self.assertFalse(worker.canStartBuild())
        self.assertIsNotNone(worker.quarantine_timer)

        # simulate wait for half the time, and put in quarantine again
        self.master.reactor.advance(5)
        worker.putInQuarantine()
        self.assertFalse(worker.canStartBuild())
        self.assertIsNotNone(worker.quarantine_timer)

        # simulate wait for another 5 seconds, and we should leave quarantine
        self.master.reactor.advance(5)
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

        # simulate wait for yet another 5 seconds, and ensure nothing changes
        self.master.reactor.advance(5)
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

    @defer.inlineCallbacks
    def test_worker_quarantine_stop_timer(self):
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

        # Call stopQuarantineTimer whilst not quarantined
        worker.stopQuarantineTimer()
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)

        # Call stopQuarantineTimer whilst quarantined
        worker.putInQuarantine()
        self.assertFalse(worker.canStartBuild())
        self.assertIsNotNone(worker.quarantine_timer)
        worker.stopQuarantineTimer()
        self.assertTrue(worker.canStartBuild())
        self.assertIsNone(worker.quarantine_timer)


class TestAbstractLatentWorker(TestReactorMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantDb=True, wantData=True)
        self.botmaster = self.master.botmaster
        yield self.master.workers.disownServiceParent()
        self.workers = self.master.workers = bworkermanager.FakeWorkerManager()
        yield self.workers.setServiceParent(self.master)

    @defer.inlineCallbacks
    def do_test_reconfigService(self, old, new, existingRegistration=True):
        old.parent = self.master
        if existingRegistration:
            old.registration = bworkermanager.FakeWorkerRegistration(old)
        old.missing_timer = mock.Mock(name='missing_timer')
        yield old.startService()

        yield old.reconfigServiceWithSibling(new)

    @defer.inlineCallbacks
    def test_reconfigService(self):
        old = AbstractLatentWorker(
            "name", "password", build_wait_timeout=10)
        new = AbstractLatentWorker(
            "name", "password", build_wait_timeout=30)

        yield self.do_test_reconfigService(old, new)

        self.assertEqual(old.build_wait_timeout, 30)
