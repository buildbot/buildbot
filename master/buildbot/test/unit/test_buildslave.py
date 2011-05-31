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
from buildbot import buildslave

class AbstractBuildSlave(unittest.TestCase):

    class ConcreteBuildSlave(buildslave.AbstractBuildSlave):
        pass

    class ConcreteBuildSlaveTwo(buildslave.AbstractBuildSlave):
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
        self.assertRaises(AssertionError, lambda :
            self.ConcreteBuildSlave('bot', 'pass',
                    notify_on_missing=['a@b.com', 13]))

    def test_identity(self):
        bot = self.ConcreteBuildSlave('bot', 'pass').identity()
        bot2 = self.ConcreteBuildSlave('bot', 'pass').identity()
        boot = self.ConcreteBuildSlave('boot', 'pass').identity()
        two = self.ConcreteBuildSlaveTwo('bot', 'pass').identity()

        self.assertEqual(bot, bot2)
        self.assertNotEqual(bot2, boot)
        self.assertNotEqual(bot, two)

    def test_update(self):
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
        old.update(new)
        self.assertEqual(old.max_builds, 3)
        self.assertEqual(old.notify_on_missing, ['her@me.com'])
        self.assertEqual(old.missing_timeout, 121)
        self.assertEqual(old.properties.getProperty('a'), 'c')
        self.assertEqual(old.keepalive_interval, 61)

    def test_setBotmaster(self):
        bs = self.ConcreteBuildSlave('bot', 'pass')
        bm = mock.Mock(name='botmaster')

        # stub out the things that should be called
        bs.updateLocks = mock.Mock()
        bs.startMissingTimer = mock.Mock()

        bs.setBotmaster(bm)
        bs.updateLocks.assert_called_with()
        bs.startMissingTimer.assert_called_with()

        # re-setting the botmaster should fail
        self.assertRaises(AssertionError, lambda :
                bs.setBotmaster(mock.Mock()))

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

