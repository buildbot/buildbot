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

from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

from parameterized import parameterized
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

if TYPE_CHECKING:
    from collections.abc import Callable

    from buildbot.util.twisted import InlineCallbacksType


class ConcreteWorker(base.AbstractWorker):
    pass


class FakeBuilder:
    def getBuilderId(self) -> defer.Deferred[int]:
        return defer.succeed(1)


class WorkerInterfaceTests(interfaces.InterfaceTests):
    wrk: Any
    callAttached: Callable[..., Any]

    def test_attr_workername(self) -> None:
        self.assertTrue(hasattr(self.wrk, 'workername'))

    def test_attr_properties(self) -> None:
        self.assertTrue(hasattr(self.wrk, 'properties'))

    def test_attr_defaultProperties(self) -> None:
        self.assertTrue(hasattr(self.wrk, 'defaultProperties'))

    @defer.inlineCallbacks
    def test_attr_worker_basedir(self) -> InlineCallbacksType[None]:
        yield self.callAttached()
        self.assertIsInstance(self.wrk.worker_basedir, str)

    @defer.inlineCallbacks
    def test_attr_path_module(self) -> InlineCallbacksType[None]:
        yield self.callAttached()
        self.assertTrue(hasattr(self.wrk, 'path_module'))

    @defer.inlineCallbacks
    def test_attr_path_cls(self) -> InlineCallbacksType[None]:
        yield self.callAttached()
        path_cls = self.wrk.path_cls
        self.assertTrue(issubclass(path_cls, PurePath))

    @defer.inlineCallbacks
    def test_attr_worker_system(self) -> InlineCallbacksType[None]:
        yield self.callAttached()
        self.assertTrue(hasattr(self.wrk, 'worker_system'))

    def test_signature_acquireLocks(self) -> None:
        @self.assertArgSpecMatches(self.wrk.acquireLocks)
        def acquireLocks(self) -> None:  # type: ignore[no-untyped-def]
            pass

    def test_signature_releaseLocks(self) -> None:
        @self.assertArgSpecMatches(self.wrk.releaseLocks)
        def releaseLocks(self) -> None:  # type: ignore[no-untyped-def]
            pass

    def test_signature_attached(self) -> None:
        @self.assertArgSpecMatches(self.wrk.attached)
        def attached(self, conn: Any) -> None:  # type: ignore[no-untyped-def]
            pass

    def test_signature_detached(self) -> None:
        @self.assertArgSpecMatches(self.wrk.detached)
        def detached(self) -> None:  # type: ignore[no-untyped-def]
            pass

    def test_signature_addWorkerForBuilder(self) -> None:
        @self.assertArgSpecMatches(self.wrk.addWorkerForBuilder)
        def addWorkerForBuilder(self, wfb: Any) -> None:  # type: ignore[no-untyped-def]
            pass

    def test_signature_removeWorkerForBuilder(self) -> None:
        @self.assertArgSpecMatches(self.wrk.removeWorkerForBuilder)
        def removeWorkerForBuilder(self, wfb: Any) -> None:  # type: ignore[no-untyped-def]
            pass

    def test_signature_buildFinished(self) -> None:
        @self.assertArgSpecMatches(self.wrk.buildFinished)
        def buildFinished(self, wfb: Any) -> None:  # type: ignore[no-untyped-def]
            pass

    def test_signature_canStartBuild(self) -> None:
        @self.assertArgSpecMatches(self.wrk.canStartBuild)
        def canStartBuild(self) -> None:  # type: ignore[no-untyped-def]
            pass


class RealWorkerItfc(TestReactorMixin, WorkerInterfaceTests, unittest.TestCase):
    def setUp(self) -> None:
        self.setup_test_reactor()
        self.wrk = ConcreteWorker('wrk', 'pa')

    @defer.inlineCallbacks
    def callAttached(self) -> InlineCallbacksType[None]:
        self.master = yield fakemaster.make_master(self, wantData=True)
        yield self.master.workers.disownServiceParent()
        self.workers = bworkermanager.FakeWorkerManager()
        yield self.workers.setServiceParent(self.master)
        self.master.workers = self.workers
        yield self.wrk.setServiceParent(self.master.workers)
        yield self.master.startService()
        self.conn = fakeprotocol.FakeConnection(self.wrk)
        yield self.wrk.attached(self.conn)


class FakeWorkerItfc(TestReactorMixin, WorkerInterfaceTests, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self)
        self.wrk = worker.FakeWorker(self.master)

    def callAttached(self) -> defer.Deferred[None]:
        self.conn = fakeprotocol.FakeConnection(self.wrk)
        return self.wrk.attached(self.conn)


class TestAbstractWorker(logging.LoggingMixin, TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.setUpLogging()
        self.master = yield fakemaster.make_master(self, wantDb=True, wantData=True)
        self.botmaster = self.master.botmaster
        yield self.master.workers.disownServiceParent()
        self.workers = self.master.workers = bworkermanager.FakeWorkerManager()
        yield self.workers.setServiceParent(self.master)

    @defer.inlineCallbacks
    def createWorker(
        self,
        name: str = 'bot',
        password: str = 'pass',
        attached: bool = False,
        configured: bool = True,
        **kwargs: Any,
    ) -> InlineCallbacksType[ConcreteWorker]:
        worker = ConcreteWorker(name, password, **kwargs)
        if configured:
            yield worker.setServiceParent(self.workers)
        if attached:
            worker.conn = fakeprotocol.FakeConnection(worker)
        return worker

    @defer.inlineCallbacks
    def createMachine(
        self, name: str, configured: bool = True, **kwargs: Any
    ) -> InlineCallbacksType[Machine]:
        machine = Machine(name)
        if configured:
            yield machine.setServiceParent(self.master.machine_manager)
        return machine

    @defer.inlineCallbacks
    def test_constructor_minimal(self) -> InlineCallbacksType[None]:
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
    def test_constructor_secrets(self) -> InlineCallbacksType[None]:
        fake_storage_service = FakeSecretStorage()

        secret_service = SecretManager()
        secret_service.services = [fake_storage_service]
        yield secret_service.setServiceParent(self.master)

        fake_storage_service.reconfigService(secretdict={"passkey": "1234"})

        bs = yield self.createWorker('bot', util.Secret('passkey'))
        yield bs.startService()
        self.assertEqual(bs.password, '1234')

    @defer.inlineCallbacks
    def test_constructor_full(self) -> InlineCallbacksType[None]:
        lock1 = locks.MasterLock('lock1')
        lock2 = locks.MasterLock('lock2')
        access1 = lock1.access('counting')
        access2 = lock2.access('counting')

        bs = yield self.createWorker(
            'bot',
            'pass',
            max_builds=2,
            notify_on_missing=['me@me.com'],
            missing_timeout=120,
            properties={'a': 'b'},
            locks=[access1, access2],
        )
        yield bs.startService()

        self.assertEqual(bs.max_builds, 2)
        self.assertEqual(bs.notify_on_missing, ['me@me.com'])
        self.assertEqual(bs.missing_timeout, 120)
        self.assertEqual(bs.properties.getProperty('a'), 'b')
        self.assertEqual(bs.access, [access1, access2])

    @defer.inlineCallbacks
    def test_constructor_notify_on_missing_not_list(self) -> InlineCallbacksType[None]:
        bs = yield self.createWorker('bot', 'pass', notify_on_missing='foo@foo.com')
        yield bs.startService()
        # turned into a list:
        self.assertEqual(bs.notify_on_missing, ['foo@foo.com'])

    def test_constructor_notify_on_missing_not_string(self) -> None:
        with self.assertRaises(config.ConfigErrors):
            ConcreteWorker('bot', 'pass', notify_on_missing=['a@b.com', 13])

    @defer.inlineCallbacks
    def do_test_reconfigService(
        self, old: ConcreteWorker, new: ConcreteWorker, existingRegistration: bool = True
    ) -> InlineCallbacksType[None]:
        old.parent = self.master
        if existingRegistration:
            old.registration = bworkermanager.FakeWorkerRegistration(old)  # type: ignore[assignment]
        old.missing_timer = mock.Mock(name='missing_timer')

        if not old.running:
            yield old.startService()

        yield old.reconfigServiceWithSibling(new)

    @defer.inlineCallbacks
    def test_reconfigService_attrs(self) -> InlineCallbacksType[None]:
        old = yield self.createWorker(
            'bot',
            'pass',
            max_builds=2,
            notify_on_missing=['me@me.com'],
            missing_timeout=120,
            properties={'a': 'b'},
        )
        new = yield self.createWorker(
            'bot',
            'pass',
            configured=False,
            max_builds=3,
            notify_on_missing=['her@me.com'],
            missing_timeout=121,
            properties={'a': 'c'},
        )

        old.updateWorker = mock.Mock(side_effect=lambda: defer.succeed(None))

        yield self.do_test_reconfigService(old, new)

        self.assertEqual(old.max_builds, 3)
        self.assertEqual(old.notify_on_missing, ['her@me.com'])
        self.assertEqual(old.missing_timeout, 121)
        self.assertEqual(old.properties.getProperty('a'), 'c')
        self.assertEqual(old.registration.updates, ['bot'])
        self.assertTrue(old.updateWorker.called)

    @defer.inlineCallbacks
    def test_reconfigService_has_properties(self) -> InlineCallbacksType[None]:
        old = yield self.createWorker(name="bot", password="pass")

        yield self.do_test_reconfigService(old, old)
        self.assertTrue(old.properties.getProperty('workername'), 'bot')

    @defer.inlineCallbacks
    def test_setupProperties(self) -> InlineCallbacksType[None]:
        props = properties.Properties()
        props.setProperty('foo', 1, 'Scheduler')
        props.setProperty('bar', 'bleh', 'Change')
        props.setProperty('omg', 'wtf', 'Builder')

        wrkr = yield self.createWorker(
            'bot', 'passwd', defaultProperties={'bar': 'onoes', 'cuckoo': 42}
        )

        wrkr.setupProperties(props)

        self.assertEqual(props.getProperty('bar'), 'bleh')
        self.assertEqual(props.getProperty('cuckoo'), 42)

    @defer.inlineCallbacks
    def test_reconfigService_initial_registration(self) -> InlineCallbacksType[None]:
        old = yield self.createWorker('bot', 'pass')
        yield self.do_test_reconfigService(old, old, existingRegistration=False)
        self.assertIn('bot', self.master.workers.registrations)
        self.assertEqual(old.registration.updates, ['bot'])

    @defer.inlineCallbacks
    def test_reconfigService_builder(self) -> InlineCallbacksType[None]:
        old = yield self.createWorker('bot', 'pass')
        yield self.do_test_reconfigService(old, old)

        # initial configuration, there is no builder configured
        self.assertEqual(old._configured_builderid_list, [])
        workers = yield self.master.data.get(('workers',))
        self.assertEqual(len(workers[0]['configured_on']), 0)

        new = yield self.createWorker('bot', 'pass', configured=False)

        # we create a fake builder, and associate to the master
        self.botmaster.builders['bot'] = [FakeBuilder()]
        yield self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Builder(id=1, name='builder'),
            fakedb.BuilderMaster(builderid=1, masterid=fakedb.FakeDBConnector.MASTER_ID),
        ])
        # on reconfig, the db should see the builder configured for this worker
        yield old.reconfigServiceWithSibling(new)
        self.assertEqual(old._configured_builderid_list, [1])
        workers = yield self.master.data.get(('workers',))
        self.assertEqual(len(workers[0]['configured_on']), 1)
        self.assertEqual(workers[0]['configured_on'][0]['builderid'], 1)

    @defer.inlineCallbacks
    def test_reconfig_service_no_machine(self) -> InlineCallbacksType[None]:
        old = yield self.createWorker('bot', 'pass')
        self.assertIsNone(old.machine)

        yield self.do_test_reconfigService(old, old)
        self.assertIsNone(old.machine)

    @defer.inlineCallbacks
    def test_reconfig_service_with_machine_initial(self) -> InlineCallbacksType[None]:
        machine = yield self.createMachine('machine1')
        old = yield self.createWorker('bot', 'pass', machine_name='machine1')
        self.assertIsNone(old.machine)

        yield self.do_test_reconfigService(old, old)
        self.assertIs(old.machine, machine)

    @defer.inlineCallbacks
    def test_reconfig_service_with_unknown_machine(self) -> InlineCallbacksType[None]:
        old = yield self.createWorker('bot', 'pass', machine_name='machine1')
        self.assertIsNone(old.machine)

        yield self.do_test_reconfigService(old, old)
        self.assertLogged('Unknown machine')

    @parameterized.expand([
        ('None_to_machine_initial', False, None, None, 'machine1', 'machine1'),
        ('None_to_machine', True, None, None, 'machine1', 'machine1'),
        ('machine_to_None_initial', False, 'machine1', None, None, None),
        ('machine_to_None', True, 'machine1', 'machine1', None, None),
        ('machine_to_same_machine_initial', False, 'machine1', None, 'machine1', 'machine1'),
        ('machine_to_same_machine', True, 'machine1', 'machine1', 'machine1', 'machine1'),
        ('machine_to_another_machine_initial', False, 'machine1', None, 'machine2', 'machine2'),
        ('machine_to_another_machine', True, 'machine1', 'machine1', 'machine2', 'machine2'),
    ])
    @defer.inlineCallbacks
    def test_reconfig_service_machine(
        self,
        test_name: str,
        do_initial_self_reconfig: bool,
        old_machine_name: str | None,
        expected_old_machine_name: str | None,
        new_machine_name: str | None,
        expected_new_machine_name: str | None,
    ) -> InlineCallbacksType[None]:
        machine1 = yield self.createMachine('machine1')
        machine2 = yield self.createMachine('machine2')

        name_to_machine = {
            None: None,
            machine1.name: machine1,
            machine2.name: machine2,
        }

        expected_old_machine = name_to_machine[expected_old_machine_name]
        expected_new_machine = name_to_machine[expected_new_machine_name]

        old = yield self.createWorker('bot', 'pass', machine_name=old_machine_name)
        new = yield self.createWorker(
            'bot', 'pass', configured=False, machine_name=new_machine_name
        )

        if do_initial_self_reconfig:
            yield self.do_test_reconfigService(old, old)

        self.assertIs(old.machine, expected_old_machine)

        yield self.do_test_reconfigService(old, new)
        self.assertIs(old.machine, expected_new_machine)

    @defer.inlineCallbacks
    def test_stopService(self) -> InlineCallbacksType[None]:
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

    def test_startMissingTimer_no_parent(self) -> None:
        bs = ConcreteWorker('bot', 'pass', notify_on_missing=['abc'], missing_timeout=10)
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_startMissingTimer_no_timeout(self) -> None:
        bs = ConcreteWorker('bot', 'pass', notify_on_missing=['abc'], missing_timeout=0)
        bs.parent = mock.Mock()  # type: ignore[assignment]
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_startMissingTimer_no_notify(self) -> None:
        bs = ConcreteWorker('bot', 'pass', missing_timeout=3600)
        bs.parent = mock.Mock()  # type: ignore[assignment]
        bs.running = True
        bs.startMissingTimer()
        self.assertNotEqual(bs.missing_timer, None)

    def test_missing_timer(self) -> None:
        bs = ConcreteWorker('bot', 'pass', notify_on_missing=['abc'], missing_timeout=100)
        bs.parent = mock.Mock()  # type: ignore[assignment]
        bs.running = True
        bs.startMissingTimer()
        self.assertNotEqual(bs.missing_timer, None)
        bs.stopMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    @defer.inlineCallbacks
    def test_setServiceParent_started(self) -> InlineCallbacksType[None]:
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
    def test_setServiceParent_masterLocks(self) -> InlineCallbacksType[None]:
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
    def test_setServiceParent_workerLocks(self) -> InlineCallbacksType[None]:
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
    def test_startService_paused_true(self) -> InlineCallbacksType[None]:
        """Test that paused state is restored on a buildbot restart"""
        yield self.master.db.insert_test_data([fakedb.Worker(id=9292, name='bot', paused=1)])

        worker = yield self.createWorker()

        yield worker.startService()

        self.assertTrue(worker.isPaused())
        self.assertFalse(worker._graceful)

    @defer.inlineCallbacks
    def test_startService_graceful_true(self) -> InlineCallbacksType[None]:
        """Test that graceful state is NOT restored on a buildbot restart"""
        yield self.master.db.insert_test_data([fakedb.Worker(id=9292, name='bot', graceful=1)])

        worker = yield self.createWorker()

        yield worker.startService()

        self.assertFalse(worker.isPaused())
        self.assertFalse(worker._graceful)

    @defer.inlineCallbacks
    def test_startService_getWorkerInfo_empty(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker()
        yield worker.startService()

        self.assertEqual(len(worker.info.asDict()), 0)

        # check that a new worker row was added for this worker
        bs = yield self.master.db.workers.getWorker(name='bot')
        self.assertEqual(bs.name, 'bot')

    @defer.inlineCallbacks
    def test_startService_getWorkerInfo_fromDb(self) -> InlineCallbacksType[None]:
        yield self.master.db.insert_test_data([
            fakedb.Worker(
                id=9292,
                name='bot',
                info={
                    'admin': 'TheAdmin',
                    'host': 'TheHost',
                    'access_uri': 'TheURI',
                    'version': 'TheVersion',
                },
            )
        ])
        worker = yield self.createWorker()

        yield worker.startService()

        self.assertEqual(worker.workerid, 9292)

        self.assertEqual(
            worker.info.asDict(),
            {
                'version': ('TheVersion', 'Worker'),
                'admin': ('TheAdmin', 'Worker'),
                'host': ('TheHost', 'Worker'),
                'access_uri': ('TheURI', 'Worker'),
            },
        )

    @defer.inlineCallbacks
    def test_attached_remoteGetWorkerInfo(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker()
        yield worker.startService()

        ENVIRON: dict[str, str] = {}
        COMMANDS: dict[str, str] = {'cmd1': '1', 'cmd2': '1'}

        conn = fakeprotocol.FakeConnection(worker)
        info: dict[str, Any] = {
            'admin': 'TheAdmin',
            'host': 'TheHost',
            'access_uri': 'TheURI',
            'environ': ENVIRON,
            'basedir': 'TheBaseDir',
            'system': 'TheWorkerSystem',
            'version': 'TheVersion',
            'worker_commands': COMMANDS,
        }
        conn.info = info
        yield worker.attached(conn)

        self.assertEqual(
            worker.info.asDict(),
            {
                'version': ('TheVersion', 'Worker'),
                'admin': ('TheAdmin', 'Worker'),
                'host': ('TheHost', 'Worker'),
                'access_uri': ('TheURI', 'Worker'),
                'basedir': ('TheBaseDir', 'Worker'),
                'system': ('TheWorkerSystem', 'Worker'),
            },
        )

        self.assertEqual(worker.worker_environ, ENVIRON)
        self.assertEqual(worker.worker_basedir, 'TheBaseDir')
        self.assertEqual(worker.worker_system, 'TheWorkerSystem')
        self.assertEqual(worker.worker_commands, COMMANDS)

    @defer.inlineCallbacks
    def test_attached_callsMaybeStartBuildsForWorker(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker()
        yield worker.startService()
        yield worker.reconfigServiceWithSibling(worker)

        conn = fakeprotocol.FakeConnection(worker)
        conn.info = {}
        yield worker.attached(conn)

        self.assertEqual(self.botmaster.buildsStartedForWorkers, ["bot"])

    @defer.inlineCallbacks
    def test_attached_workerInfoUpdates(self) -> InlineCallbacksType[None]:
        # put in stale info:
        yield self.master.db.insert_test_data([
            fakedb.Worker(
                name='bot',
                info={
                    'admin': 'WrongAdmin',
                    'host': 'WrongHost',
                    'access_uri': 'WrongURI',
                    'version': 'WrongVersion',
                },
            )
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

        self.assertEqual(
            worker.info.asDict(),
            {
                'version': ('TheVersion', 'Worker'),
                'admin': ('TheAdmin', 'Worker'),
                'host': ('TheHost', 'Worker'),
                'access_uri': ('TheURI', 'Worker'),
            },
        )

        # and the db is updated too:
        db_worker = yield self.master.db.workers.getWorker(name="bot")

        self.assertEqual(db_worker.workerinfo['admin'], 'TheAdmin')
        self.assertEqual(db_worker.workerinfo['host'], 'TheHost')
        self.assertEqual(db_worker.workerinfo['access_uri'], 'TheURI')
        self.assertEqual(db_worker.workerinfo['version'], 'TheVersion')

    @defer.inlineCallbacks
    def test_double_attached(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker()
        yield worker.startService()

        conn = fakeprotocol.FakeConnection(worker)
        yield worker.attached(conn)
        conn = fakeprotocol.FakeConnection(worker)
        with self.assertRaisesRegex(
            AssertionError, "bot: fake_peer connecting, but we are already connected to: fake_peer"
        ):
            yield worker.attached(conn)

    @defer.inlineCallbacks
    def test_worker_shutdown(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker(attached=True)
        yield worker.startService()

        yield worker.shutdown()
        self.assertEqual(
            worker.conn.remoteCalls, [('remoteSetBuilderList', []), ('remoteShutdown',)]
        )

    @defer.inlineCallbacks
    def test_worker_shutdown_not_connected(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker(attached=False)
        yield worker.startService()

        # No exceptions should be raised here
        yield worker.shutdown()

    @defer.inlineCallbacks
    def test_shutdownRequested(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker(attached=False)
        yield worker.startService()

        yield worker.shutdownRequested()
        self.assertEqual(worker._graceful, True)

    @defer.inlineCallbacks
    def test_missing_timer_missing(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker(attached=False, missing_timeout=1)
        yield worker.startService()
        self.assertNotEqual(worker.missing_timer, None)
        yield self.reactor.advance(1)  # type: ignore[func-returns-value]
        self.assertEqual(worker.missing_timer, None)
        self.assertEqual(
            [key for key, _ in self.master.mq.productions], [('workers', '1', 'missing')]
        )

    @defer.inlineCallbacks
    def test_missing_timer_stopped(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker(attached=False, missing_timeout=1)
        yield worker.startService()
        self.assertNotEqual(worker.missing_timer, None)
        yield worker.stopService()
        self.assertEqual(worker.missing_timer, None)
        self.assertEqual([key for key, _ in self.master.mq.productions], [])

    @defer.inlineCallbacks
    def test_worker_actions_stop(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        worker.controlWorker(("worker", 1, "stop"), {'reason': "none"})
        self.assertEqual(worker._graceful, True)

    @defer.inlineCallbacks
    def test_worker_actions_kill(self) -> InlineCallbacksType[None]:
        worker = yield self.createWorker(attached=False)
        yield worker.startService()
        worker.controlWorker(("worker", 1, "kill"), {'reason': "none"})
        self.assertEqual(worker.conn, None)

    @defer.inlineCallbacks
    def test_worker_actions_pause(self) -> InlineCallbacksType[None]:
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
    def test_worker_quarantine_doesnt_affect_pause(self) -> InlineCallbacksType[None]:
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
    def test_worker_quarantine_unpausing_exits_quarantine(self) -> InlineCallbacksType[None]:
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
    def test_worker_quarantine_unpausing_doesnt_reset_timeout(self) -> InlineCallbacksType[None]:
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
    def test_worker_quarantine_wait_times(self) -> InlineCallbacksType[None]:
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
    def test_worker_quarantine_reset(self) -> InlineCallbacksType[None]:
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
    def test_worker_quarantine_whilst_quarantined(self) -> InlineCallbacksType[None]:
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
    def test_worker_quarantine_stop_timer(self) -> InlineCallbacksType[None]:
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
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True, wantData=True)
        self.botmaster = self.master.botmaster
        yield self.master.workers.disownServiceParent()
        self.workers = self.master.workers = bworkermanager.FakeWorkerManager()
        yield self.workers.setServiceParent(self.master)

    @defer.inlineCallbacks
    def do_test_reconfigService(
        self,
        old: AbstractLatentWorker,
        new: AbstractLatentWorker,
        existingRegistration: bool = True,
    ) -> InlineCallbacksType[None]:
        old.parent = self.master
        if existingRegistration:
            old.registration = bworkermanager.FakeWorkerRegistration(old)  # type: ignore[assignment]
        old.missing_timer = mock.Mock(name='missing_timer')
        yield old.startService()

        yield old.reconfigServiceWithSibling(new)

    @defer.inlineCallbacks
    def test_reconfigService(self) -> InlineCallbacksType[None]:
        old = AbstractLatentWorker("name", "password", build_wait_timeout=10)
        new = AbstractLatentWorker("name", "password", build_wait_timeout=30)

        yield self.do_test_reconfigService(old, new)

        self.assertEqual(old.build_wait_timeout, 30)
