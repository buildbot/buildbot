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
from twisted.internet import defer
from buildbot import buildslave, config
from buildbot.test.fake import fakemaster

class AbstractBuildSlave(unittest.TestCase):

    class ConcreteBuildSlave(buildslave.AbstractBuildSlave):
        pass

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

    @defer.deferredGenerator
    def do_test_reconfigService(self, old, old_port, new, new_port):
        master = self.master = fakemaster.make_master()
        old.master = master
        if old_port:
            self.old_registration = old.registration = \
                    mock.Mock(name='old_registration')
            old.registered_port = old_port
        old.missing_timer = mock.Mock(name='missing_timer')
        old.startService()

        self.new_registration = mock.Mock(name='new_registration')
        master.pbmanager.register = mock.Mock(
                side_effect=lambda *args : self.new_registration)

        new_config = mock.Mock()
        new_config.slavePortnum = new_port
        new_config.slaves = [ new ]

        wfd = defer.waitForDeferred(
            old.reconfigService(new_config))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
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

        wfd = defer.waitForDeferred(
            self.do_test_reconfigService(old, 'tcp:1234', new, 'tcp:1234'))
        yield wfd
        wfd.getResult()

        self.assertEqual(old.max_builds, 3)
        self.assertEqual(old.notify_on_missing, ['her@me.com'])
        self.assertEqual(old.missing_timeout, 121)
        self.assertEqual(old.properties.getProperty('a'), 'c')
        self.assertEqual(old.keepalive_interval, 61)
        self.assertFalse(self.master.pbmanager.register.called)
        self.assertTrue(old.updateSlave.called)

    @defer.deferredGenerator
    def test_reconfigService_has_properties(self):
        old = self.ConcreteBuildSlave('bot', 'pass')

        wfd = defer.waitForDeferred(
            self.do_test_reconfigService(old, 'tcp:1234', old, 'tcp:1234'))
        yield wfd
        wfd.getResult()

        self.assertTrue(old.properties.getProperty('slavename'), 'bot')

    @defer.deferredGenerator
    def test_reconfigService_initial_registration(self):
        old = self.ConcreteBuildSlave('bot', 'pass')

        wfd = defer.waitForDeferred(
            self.do_test_reconfigService(old, None, old, 'tcp:1234'))
        yield wfd
        wfd.getResult()

        self.assertTrue(self.master.pbmanager.register.called)

    @defer.deferredGenerator
    def test_reconfigService_reregister_password(self):
        old = self.ConcreteBuildSlave('bot', 'pass')
        new = self.ConcreteBuildSlave('bot', 'newpass')

        wfd = defer.waitForDeferred(
            self.do_test_reconfigService(old, 'tcp:1234', new, 'tcp:1234'))
        yield wfd
        wfd.getResult()

        self.assertEqual(old.password, 'newpass')
        self.assertTrue(self.old_registration.unregister.called)
        self.assertTrue(self.master.pbmanager.register.called)

    @defer.deferredGenerator
    def test_reconfigService_reregister_port(self):
        old = self.ConcreteBuildSlave('bot', 'pass')
        new = self.ConcreteBuildSlave('bot', 'pass')

        wfd = defer.waitForDeferred(
            self.do_test_reconfigService(old, 'tcp:1234', new, 'tcp:5678'))
        yield wfd
        wfd.getResult()

        self.assertTrue(self.old_registration.unregister.called)
        self.assertTrue(self.master.pbmanager.register.called)

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

