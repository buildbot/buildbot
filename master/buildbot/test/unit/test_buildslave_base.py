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
from buildbot.test.fake import fakemaster, pbmanager, fakedb
from buildbot.test.fake.botmaster import FakeBotMaster

class TestAbstractBuildSlave(unittest.TestCase):

    class ConcreteBuildSlave(base.AbstractBuildSlave):
        pass

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, wantData=True,
                                                testcase=self)
        self.botmaster = FakeBotMaster(self.master)

        self.clock = task.Clock()
        self.patch(reactor, 'callLater', self.clock.callLater)
        self.patch(reactor, 'seconds', self.clock.seconds)

    def createBuildslave(self, name='bot', password='pass', **kwargs):
        slave = self.ConcreteBuildSlave(name, password, **kwargs)
        slave.master = self.master
        slave.botmaster = self.botmaster
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
        self.assertEqual(bs.keepalive_interval, 3600)

    def test_constructor_full(self):
        lock1, lock2 = mock.Mock(name='lock1'), mock.Mock(name='lock2')
        bs = self.ConcreteBuildSlave('bot', 'pass',
                max_builds=2,
                notify_on_missing=['me@me.com'],
                missing_timeout=120,
                properties={'a':'b'},
                locks=[lock1, lock2],
                keepalive_interval=60)
        self.assertEqual(bs.max_builds, 2)
        self.assertEqual(bs.notify_on_missing, ['me@me.com'])
        self.assertEqual(bs.missing_timeout, 120)
        self.assertEqual(bs.properties.getProperty('a'), 'b')
        self.assertEqual(bs.access, [lock1, lock2])
        self.assertEqual(bs.keepalive_interval, 60)

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
    def do_test_reconfigService(self, old, old_port, new, new_port):
        old.master = self.master
        if old_port:
            self.old_registration = old.registration = \
                    pbmanager.FakeRegistration(self.master.pbmanager, old_port, old.slavename)
            old.registered_port = old_port
        old.missing_timer = mock.Mock(name='missing_timer')
        yield old.startService()

        new_config = mock.Mock()
        new_config.slavePortnum = new_port
        new_config.slaves = [ new ]

        yield old.reconfigService(new_config)

    @defer.inlineCallbacks
    def test_reconfigService_attrs(self):
        old = self.ConcreteBuildSlave('bot', 'pass',
                max_builds=2,
                notify_on_missing=['me@me.com'],
                missing_timeout=120,
                properties={'a':'b'},
                keepalive_interval=60)
        new = self.ConcreteBuildSlave('bot', 'pass',
                max_builds=3,
                notify_on_missing=['her@me.com'],
                missing_timeout=121,
                properties={'a':'c'},
                keepalive_interval=61)

        old.updateSlave = mock.Mock(side_effect=lambda : defer.succeed(None))

        yield self.do_test_reconfigService(old, 'tcp:1234', new, 'tcp:1234')

        self.assertEqual(old.max_builds, 3)
        self.assertEqual(old.notify_on_missing, ['her@me.com'])
        self.assertEqual(old.missing_timeout, 121)
        self.assertEqual(old.properties.getProperty('a'), 'c')
        self.assertEqual(old.keepalive_interval, 61)
        self.assertEqual(self.master.pbmanager._registrations, [])
        self.assertTrue(old.updateSlave.called)

    @defer.inlineCallbacks
    def test_reconfigService_has_properties(self):
        old = self.ConcreteBuildSlave('bot', 'pass')
        yield self.do_test_reconfigService(old, 'tcp:1234', old, 'tcp:1234')
        self.assertTrue(old.properties.getProperty('slavename'), 'bot')

    @defer.inlineCallbacks
    def test_reconfigService_initial_registration(self):
        old = self.ConcreteBuildSlave('bot', 'pass')
        yield self.do_test_reconfigService(old, None, old, 'tcp:1234')
        self.assertEqual(self.master.pbmanager._registrations, [('tcp:1234', 'bot', 'pass')])

    @defer.inlineCallbacks
    def test_reconfigService_reregister_password(self):
        old = self.ConcreteBuildSlave('bot', 'pass')
        new = self.ConcreteBuildSlave('bot', 'newpass')

        yield self.do_test_reconfigService(old, 'tcp:1234', new, 'tcp:1234')

        self.assertEqual(old.password, 'newpass')
        self.assertEqual(self.master.pbmanager._unregistrations, [('tcp:1234', 'bot')])
        self.assertEqual(self.master.pbmanager._registrations, [('tcp:1234', 'bot', 'newpass')])

    @defer.inlineCallbacks
    def test_reconfigService_reregister_port(self):
        old = self.ConcreteBuildSlave('bot', 'pass')
        new = self.ConcreteBuildSlave('bot', 'pass')

        yield self.do_test_reconfigService(old, 'tcp:1234', new, 'tcp:5678')

        self.assertEqual(self.master.pbmanager._unregistrations, [('tcp:1234', 'bot')])
        self.assertEqual(self.master.pbmanager._registrations, [('tcp:5678', 'bot', 'pass')])

    @defer.inlineCallbacks
    def test_stopService(self):
        slave = self.createBuildslave()
        yield slave.startService()

        config = mock.Mock()
        config.slavePortnum = "tcp:1234"
        config.slaves = [ slave ]

        yield slave.reconfigService(config)
        yield slave.stopService()

        self.assertEqual(self.master.pbmanager._unregistrations, [('tcp:1234', 'bot')])
        self.assertEqual(self.master.pbmanager._registrations, [('tcp:1234', 'bot', 'pass')])

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

        # check that a new slave row was added for this buildslave
        bs = yield self.master.db.buildslaves.getBuildslave(name='bot')
        self.assertEqual(bs['name'], 'bot')

    @defer.inlineCallbacks
    def test_startService_getSlaveInfo_fromDb(self):
        self.master.db.insertTestData([
            fakedb.Buildslave(id=9292, name='bot', info={
                'admin': 'TheAdmin',
                'host': 'TheHost',
                'access_uri': 'TheURI',
                'version': 'TheVersion'
            })
        ])
        slave = self.createBuildslave()

        yield slave.startService()

        self.assertEqual(slave.buildslaveid, 9292)
        self.assertEqual(slave.slave_status.getAdmin(),   'TheAdmin')
        self.assertEqual(slave.slave_status.getHost(),    'TheHost')
        self.assertEqual(slave.slave_status.getAccessURI(),'TheURI')
        self.assertEqual(slave.slave_status.getVersion(), 'TheVersion')

    def createRemoteBot(self):
        class Bot():
            def __init__(self):
                self.commands = []
                self.response = {
                    'getSlaveInfo': mock.Mock(return_value=defer.succeed({}))
                }

            def callRemote(self, command, *args):
                self.commands.append((command,) + args)
                response = self.response.get(command)
                if response:
                    return response(*args)
                return defer.succeed(None)
        
        return Bot()

    @defer.inlineCallbacks
    def test_attached_checkRemoteCalls(self):
        slave = self.createBuildslave()
        yield slave.startService()

        bot = self.createRemoteBot()
        yield slave.attached(bot)

        self.assertEqual(True, slave.slave_status.isConnected())
        self.assertEqual(5, len(bot.commands))
        self.assertEqual(bot.commands[0], ('print', 'attached'))
        self.assertEqual(bot.commands[1], ('getSlaveInfo',))
        self.assertEqual(bot.commands[2], ('getVersion',))
        self.assertEqual(bot.commands[3], ('getCommands',))
        self.assertEqual(bot.commands[4], ('setBuilderList',[]))

    @defer.inlineCallbacks
    def test_attached_callRemote_print_raises(self):
        slave = self.createBuildslave()
        yield slave.startService()

        bot = self.createRemoteBot()
        bot.response['print'] = mock.Mock(return_value=defer.fail(ValueError()))
        yield slave.attached(bot)

        # just check that things still go on
        self.assertEqual(True, slave.slave_status.isConnected())
        self.assertEqual(5, len(bot.commands))

    @defer.inlineCallbacks
    def test_attached_callRemote_getSlaveInfo(self):
        slave = self.createBuildslave()
        yield slave.startService()

        ENVIRON = {}

        bot = self.createRemoteBot()
        bot.response['getSlaveInfo'] = mock.Mock(return_value=defer.succeed({
            'admin':   'TheAdmin',
            'host':    'TheHost',
            'access_uri': 'TheURI',
            'environ': ENVIRON,
            'basedir': 'TheBaseDir',
            'system': 'TheSlaveSystem'
        }))
        yield slave.attached(bot)

        # check that things were all good
        self.assertEqual(True, slave.slave_status.isConnected())
        self.assertEqual(5, len(bot.commands))

        # check the values get set right
        self.assertEqual(slave.slave_status.getAdmin(),     "TheAdmin")
        self.assertEqual(slave.slave_status.getHost(),      "TheHost")
        self.assertEqual(slave.slave_status.getAccessURI(), "TheURI")
        self.assertEqual(slave.slave_environ, ENVIRON)
        self.assertEqual(slave.slave_basedir, 'TheBaseDir')
        self.assertEqual(slave.slave_system,  'TheSlaveSystem')

    @defer.inlineCallbacks
    def test_attached_callRemote_getVersion(self):
        slave = self.createBuildslave()
        yield slave.startService()

        bot = self.createRemoteBot()
        bot.response['getVersion'] = mock.Mock(return_value=defer.succeed("TheVersion"))
        yield slave.attached(bot)

        # check that things were all good
        self.assertEqual(True, slave.slave_status.isConnected())
        self.assertEqual(5, len(bot.commands))

        # check the values get set right
        self.assertEqual(slave.slave_status.getVersion(), "TheVersion")

    @defer.inlineCallbacks
    def test_attached_callRemote_getCommands(self):
        slave = self.createBuildslave()
        yield slave.startService()

        COMMANDS = ['a','b']

        bot = self.createRemoteBot()
        bot.response['getCommands'] = mock.Mock(return_value=defer.succeed(COMMANDS))
        yield slave.attached(bot)

        # check that things were all good
        self.assertEqual(True, slave.slave_status.isConnected())
        self.assertEqual(5, len(bot.commands))

        # check the values get set right
        self.assertEqual(slave.slave_commands, COMMANDS)

    @defer.inlineCallbacks
    def test_attached_callsMaybeStartBuildsForSlave(self):
        slave = self.createBuildslave()
        yield slave.startService()

        bot = self.createRemoteBot()
        yield slave.attached(bot)

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

        bot = self.createRemoteBot()
        bot.response['getVersion'] = mock.Mock(return_value=defer.succeed("TheVersion"))
        bot.response['getSlaveInfo'] = mock.Mock(return_value=defer.succeed({
            'admin':   'TheAdmin',
            'host':    'TheHost',
            'access_uri': 'TheURI',
        }))
        yield slave.attached(bot)

        self.assertEqual(slave.slave_status.getAdmin(),   'TheAdmin')
        self.assertEqual(slave.slave_status.getHost(),    'TheHost')
        self.assertEqual(slave.slave_status.getAccessURI(),'TheURI')
        self.assertEqual(slave.slave_status.getVersion(), 'TheVersion')

        # and the db is updated too:
        buildslave = yield self.master.db.buildslaves.getBuildslave(name="bot")

        self.assertEqual(buildslave['slaveinfo']['admin'], 'TheAdmin')
        self.assertEqual(buildslave['slaveinfo']['host'], 'TheHost')
        self.assertEqual(buildslave['slaveinfo']['access_uri'], 'TheURI')
        self.assertEqual(buildslave['slaveinfo']['version'], 'TheVersion')

