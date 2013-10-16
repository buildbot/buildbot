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
from twisted.trial import unittest
from twisted.internet import defer, task, reactor
from buildbot import config, locks
from buildbot.buildslave import base
from buildbot.test.fake import fakemaster, fakedb, bslavemanager, fakeprotocol
from buildbot.test.fake.botmaster import FakeBotMaster

class TestAbstractBuildSlave(unittest.TestCase):

    class ConcreteBuildSlave(base.AbstractBuildSlave):
        pass

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.botmaster = FakeBotMaster(self.master)

        self.clock = task.Clock()
        self.patch(reactor, 'callLater', self.clock.callLater)
        self.patch(reactor, 'seconds', self.clock.seconds)

    def createBuildslave(self, name='bot', password='pass', attached=False, **kwargs):
        slave = self.ConcreteBuildSlave(name, password, **kwargs)
        slave.master = self.master
        slave.botmaster = self.botmaster
        if attached:
            slave.conn = fakeprotocol.FakeConnection(self.master, slave)
        return slave

    def test_constructor_minimal(self):
        bs = self.ConcreteBuildSlave('bot', 'pass')
        self.assertEqual(bs.slavename, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.max_builds, None)
        self.assertEqual(bs.notify_on_missing, [])
        self.assertEqual(bs.missing_timeout, 3600)
        self.assertEqual(bs.properties.getProperty('slavename'), 'bot')
        self.assertEqual(bs.access, [])

    def test_constructor_full(self):
        lock1, lock2 = mock.Mock(name='lock1'), mock.Mock(name='lock2')
        bs = self.ConcreteBuildSlave('bot', 'pass',
                max_builds=2,
                notify_on_missing=['me@me.com'],
                missing_timeout=120,
                properties={'a':'b'},
                locks=[lock1, lock2])

        self.assertEqual(bs.max_builds, 2)
        self.assertEqual(bs.notify_on_missing, ['me@me.com'])
        self.assertEqual(bs.missing_timeout, 120)
        self.assertEqual(bs.properties.getProperty('a'), 'b')
        self.assertEqual(bs.access, [lock1, lock2])

    def test_constructor_notify_on_missing_not_list(self):
        bs = self.ConcreteBuildSlave('bot', 'pass',
                notify_on_missing='foo@foo.com')
        # turned into a list:
        self.assertEqual(bs.notify_on_missing, ['foo@foo.com'])

    def test_constructor_notify_on_missing_not_string(self):
        self.assertRaises(config.ConfigErrors, lambda :
            self.ConcreteBuildSlave('bot', 'pass',
                    notify_on_missing=['a@b.com', 13]))

    @defer.inlineCallbacks
    def do_test_reconfigService(self, old, new, existingRegistration=True):
        old.master = self.master
        if existingRegistration:
            old.registration = bslavemanager.FakeBuildslaveRegistration(old)
        old.missing_timer = mock.Mock(name='missing_timer')
        yield old.startService()

        new_config = mock.Mock()
        new_config.slaves = [ new ]

        yield old.reconfigService(new_config)

    @defer.inlineCallbacks
    def test_reconfigService_attrs(self):
        old = self.ConcreteBuildSlave('bot', 'pass',
                max_builds=2,
                notify_on_missing=['me@me.com'],
                missing_timeout=120,
                properties={'a':'b'})
        new = self.ConcreteBuildSlave('bot', 'pass',
                max_builds=3,
                notify_on_missing=['her@me.com'],
                missing_timeout=121,
                properties={'a':'c'})

        old.updateSlave = mock.Mock(side_effect=lambda : defer.succeed(None))

        yield self.do_test_reconfigService(old, new)

        self.assertEqual(old.max_builds, 3)
        self.assertEqual(old.notify_on_missing, ['her@me.com'])
        self.assertEqual(old.missing_timeout, 121)
        self.assertEqual(old.properties.getProperty('a'), 'c')
        self.assertEqual(old.registration.updates, ['bot'])
        self.assertTrue(old.updateSlave.called)

    @defer.inlineCallbacks
    def test_reconfigService_has_properties(self):
        old = self.ConcreteBuildSlave('bot', 'pass')
        yield self.do_test_reconfigService(old, old)
        self.assertTrue(old.properties.getProperty('slavename'), 'bot')

    @defer.inlineCallbacks
    def test_reconfigService_initial_registration(self):
        old = self.ConcreteBuildSlave('bot', 'pass')
        yield self.do_test_reconfigService(old, old,
                existingRegistration=False)
        self.assertIn('bot', self.master.buildslaves.registrations)
        self.assertEqual(old.registration.updates, ['bot'])

    @defer.inlineCallbacks
    def test_stopService(self):
        slave = self.createBuildslave()
        yield slave.startService()

        config = mock.Mock()
        config.protocols = {'pb': {'port': 'tcp:1234'}}
        config.slaves = [ slave ]

        yield slave.reconfigService(config)

        reg = slave.registration

        yield slave.stopService()

        self.assertTrue(reg.unregistered)
        self.assertEqual(slave.registration, None)

    # FIXME: Test that reconfig properly deals with
    #   1) locks
    #   2) telling slave about builder
    #   3) missing timer
    # in both the initial config and a reconfiguration.

    def test_startMissingTimer_no_parent(self):
        bs = self.ConcreteBuildSlave('bot', 'pass',
                notify_on_missing=['abc'],
                missing_timeout=10)
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_startMissingTimer_no_timeout(self):
        bs = self.ConcreteBuildSlave('bot', 'pass',
                notify_on_missing=['abc'],
                missing_timeout=0)
        bs.parent = mock.Mock()
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_startMissingTimer_no_notify(self):
        bs = self.ConcreteBuildSlave('bot', 'pass',
                missing_timeout=3600)
        bs.parent = mock.Mock()
        bs.startMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_missing_timer(self):
        bs = self.ConcreteBuildSlave('bot', 'pass',
                notify_on_missing=['abc'],
                missing_timeout=100)
        bs.parent = mock.Mock()
        bs.startMissingTimer()
        self.assertNotEqual(bs.missing_timer, None)
        bs.stopMissingTimer()
        self.assertEqual(bs.missing_timer, None)

    def test_setServiceParent_started(self):
        master = self.master
        botmaster = FakeBotMaster(master)
        botmaster.startService()
        bs = self.ConcreteBuildSlave('bot', 'pass')
        bs.setServiceParent(botmaster)
        self.assertEqual(bs.botmaster, botmaster)
        self.assertEqual(bs.master, master)

    def test_setServiceParent_masterLocks(self):
        """
        http://trac.buildbot.net/ticket/2278
        """
        master = self.master
        botmaster = FakeBotMaster(master)
        botmaster.startService()
        lock = locks.MasterLock('masterlock')
        bs = self.ConcreteBuildSlave('bot', 'pass', locks = [lock.access("counting")])
        bs.setServiceParent(botmaster)

    def test_setServiceParent_slaveLocks(self):
        """
        http://trac.buildbot.net/ticket/2278
        """
        master = self.master
        botmaster = FakeBotMaster(master)
        botmaster.startService()
        lock = locks.SlaveLock('lock')
        bs = self.ConcreteBuildSlave('bot', 'pass', locks = [lock.access("counting")])
        bs.setServiceParent(botmaster)

    @defer.inlineCallbacks
    def test_startService_getSlaveInfo_empty(self):
        slave = self.createBuildslave()
        yield slave.startService()

        self.assertEqual(slave.slave_status.getAdmin(), None)
        self.assertEqual(slave.slave_status.getHost(), None)
        self.assertEqual(slave.slave_status.getAccessURI(), None)
        self.assertEqual(slave.slave_status.getVersion(), None)

    @defer.inlineCallbacks
    def test_startService_getSlaveInfo_fromDb(self):
        self.master.db.insertTestData([
            fakedb.Buildslave(name='bot', info={ 
                'admin': 'TheAdmin',
                'host': 'TheHost',
                'access_uri': 'TheURI',
                'version': 'TheVersion'
            })
        ])
        slave = self.createBuildslave()

        yield slave.startService()

        self.assertEqual(slave.slave_status.getAdmin(),   'TheAdmin')
        self.assertEqual(slave.slave_status.getHost(),    'TheHost')
        self.assertEqual(slave.slave_status.getAccessURI(),'TheURI')
        self.assertEqual(slave.slave_status.getVersion(), 'TheVersion')

    @defer.inlineCallbacks
    def test_attached_remoteGetSlaveInfo(self):
        slave = self.createBuildslave()
        yield slave.startService()

        ENVIRON = {}
        COMMANDS = {'cmd1': '1', 'cmd2': '1'}

        conn = fakeprotocol.FakeConnection(slave.master, slave)
        conn.info = {
            'admin':   'TheAdmin',
            'host':    'TheHost',
            'access_uri': 'TheURI',
            'environ': ENVIRON,
            'basedir': 'TheBaseDir',
            'system': 'TheSlaveSystem',
            'version': 'version',
            'slave_commands': COMMANDS,
        }
        yield slave.attached(conn)

        # check the values get set right
        self.assertEqual(slave.slave_status.getAdmin(),     "TheAdmin")
        self.assertEqual(slave.slave_status.getHost(),      "TheHost")
        self.assertEqual(slave.slave_status.getAccessURI(), "TheURI")
        self.assertEqual(slave.slave_environ, ENVIRON)
        self.assertEqual(slave.slave_basedir, 'TheBaseDir')
        self.assertEqual(slave.slave_system,  'TheSlaveSystem')
        self.assertEqual(slave.slave_commands,  COMMANDS)

    @defer.inlineCallbacks
    def test_attached_callsMaybeStartBuildsForSlave(self):
        slave = self.createBuildslave()
        yield slave.startService()

        conn = fakeprotocol.FakeConnection(slave.master, slave)
        conn.info = {}
        yield slave.attached(conn)

        self.assertEqual(self.botmaster.buildsStartedForSlaves, ["bot"])

    @defer.inlineCallbacks
    def test_attached_slaveInfoUpdates(self):
        # put in stale info:
        self.master.db.insertTestData([
            fakedb.Buildslave(name='bot', info={ 
                'admin': 'WrongAdmin',
                'host': 'WrongHost',
                'access_uri': 'WrongURI',
                'version': 'WrongVersion'
            })
        ])
        slave = self.createBuildslave()
        yield slave.startService()

        conn = fakeprotocol.FakeConnection(slave.master, slave)
        conn.info = {
            'admin':   'TheAdmin',
            'host':    'TheHost',
            'access_uri': 'TheURI',
            'version': 'TheVersion',
        }
        yield slave.attached(conn)

        self.assertEqual(slave.slave_status.getAdmin(),   'TheAdmin')
        self.assertEqual(slave.slave_status.getHost(),    'TheHost')
        self.assertEqual(slave.slave_status.getAccessURI(),'TheURI')
        self.assertEqual(slave.slave_status.getVersion(), 'TheVersion')

        # and the db is updated too:
        buildslave = yield self.master.db.buildslaves.getBuildslaveByName("bot")

        self.assertEqual(buildslave['slaveinfo']['admin'], 'TheAdmin')
        self.assertEqual(buildslave['slaveinfo']['host'], 'TheHost')
        self.assertEqual(buildslave['slaveinfo']['access_uri'], 'TheURI')
        self.assertEqual(buildslave['slaveinfo']['version'], 'TheVersion')

    @defer.inlineCallbacks
    def test_slave_shutdown(self):
        slave = self.createBuildslave(attached=True)
        yield slave.startService()

        yield slave.shutdown()
        self.assertEqual(slave.conn.remoteCalls, [('remoteShutdown',)])

    @defer.inlineCallbacks
    def test_slave_shutdown_not_connected(self):
        slave = self.createBuildslave(attached=False)
        yield slave.startService()

        # No exceptions should be raised here
        yield slave.shutdown()

    @defer.inlineCallbacks
    def test_shutdownRequested(self):
        slave = self.createBuildslave(attached=False)
        yield slave.startService()

        yield slave.shutdownRequested()
        self.assertEqual(slave.slave_status.getGraceful(), True)
