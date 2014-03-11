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

from buildbot.status import slave
from buildbot.util import eventual
from twisted.trial import unittest


class TestSlaveStatus(unittest.TestCase):

    SLAVE_NAME = 'slavename'

    def makeStatus(self):
        s = slave.SlaveStatus(self.SLAVE_NAME)
        return s

    def test_getName(self):
        s = self.makeStatus()
        self.assertEqual(s.getName(), self.SLAVE_NAME)

    def test_getGraceful(self):
        s = self.makeStatus()
        self.assertFalse(s.getGraceful())

    def test_setGraceful(self):
        s = self.makeStatus()

        s.setGraceful(True)

        self.assertTrue(s.getGraceful())

    def test_addGracefulWatcher_noCallsWhenNotChanged(self):
        s = self.makeStatus()

        callbacks = []

        def callback(graceful):
            callbacks.append(graceful)
        s.addGracefulWatcher(callback)

        d = eventual.flushEventualQueue()

        @d.addCallback
        def check(_):
            self.assertEqual(callbacks, [])

        return d

    def test_addGracefulWatcher_called(self):
        s = self.makeStatus()

        callbacks = []

        def callback(graceful):
            callbacks.append(graceful)
        s.addGracefulWatcher(callback)

        s.setGraceful(True)

        d = eventual.flushEventualQueue()

        @d.addCallback
        def check(_):
            self.assertEqual(callbacks, [True])

        return d

    def test_removeGracefulWatcher_removeBadObject(self):
        s = self.makeStatus()

        BOGUS_OBJECT = object()
        s.removeGracefulWatcher(BOGUS_OBJECT)

    def test_removeGracefulWatcher(self):
        s = self.makeStatus()

        callbacks = []

        def callback(graceful):
            callbacks.append(graceful)

        s.addGracefulWatcher(callback)
        s.removeGracefulWatcher(callback)

        s.setGraceful(True)

        d = eventual.flushEventualQueue()

        @d.addCallback
        def check(_):
            # never called:
            self.assertEqual(callbacks, [])

        return d

    def test_getRunningBuilds_empty(self):
        s = self.makeStatus()

        builds = s.getRunningBuilds()

        self.assertEqual(builds, [])

    def test_getRunningBuilds_one(self):
        s = self.makeStatus()

        BUILD = 123

        s.buildStarted(BUILD)

        builds = s.getRunningBuilds()

        self.assertEqual(builds, [BUILD])

    def test_getRunningBuilds_removed(self):
        s = self.makeStatus()

        BUILD = 123

        s.buildStarted(BUILD)
        s.buildFinished(BUILD)

        builds = s.getRunningBuilds()

        self.assertEqual(builds, [])

    def test_getInfo_badKeyReturnsDefault(self):
        s = self.makeStatus()

        DEFAULT = object()
        value = s.getInfo('bogus_key', DEFAULT)

        self.assertTrue(value is DEFAULT)

    def test_hasInfo(self):
        s = self.makeStatus()

        s.updateInfo(number=123)

        self.assertTrue(s.hasInfo('number'))
        self.assertFalse(s.hasInfo('bogus'))

    def test_updateInfo_number(self):
        s = self.makeStatus()

        VALUE = 541
        s.updateInfo(key=VALUE)

        self.assertEqual(s.getInfo('key'), VALUE)

    def test_updateInfo_string(self):
        s = self.makeStatus()

        VALUE = 'abc'
        s.updateInfo(key=VALUE)

        self.assertEqual(s.getInfo('key'), VALUE)

    def test_updateInfo_None(self):
        s = self.makeStatus()

        VALUE = None
        s.updateInfo(key=VALUE)

        # tuples become lists due to JSON restriction
        self.assertEqual(s.getInfo('key'), VALUE)

    def test_updateInfo_list(self):
        s = self.makeStatus()

        VALUE = ['abc', None, 1]
        s.updateInfo(key=VALUE)

        self.assertEqual(s.getInfo('key'), VALUE)

    def test_updateInfo_tuple(self):
        s = self.makeStatus()

        VALUE = ('abc', None, 1)
        s.updateInfo(key=VALUE)

        # tuples become lists due to JSON restriction
        self.assertEqual(s.getInfo('key'), list(VALUE))

    def test_updateInfo_set_raises(self):
        s = self.makeStatus()

        FIRST_VALUE = 123
        s.updateInfo(key=FIRST_VALUE)

        SET_VALUE = set(['abc', None, 1])
        self.assertRaises(TypeError, s.updateInfo, ('key', SET_VALUE))

        # value didnt change
        self.assertEqual(s.getInfo('key'), FIRST_VALUE)

    def test_updateInfo_badType(self):
        s = self.makeStatus()

        FIRST_VALUE = 123
        s.updateInfo(key=FIRST_VALUE)

        BAD_VALUE = object()
        self.assertRaises(TypeError, s.updateInfo, ('key', BAD_VALUE))

        # value didnt change
        self.assertEqual(s.getInfo('key'), FIRST_VALUE)

    def test_addInfoWatcher_noCallsWhenNotChanged(self):
        s = self.makeStatus()
        FIRST_VALUE = 123
        s.updateInfo(key=FIRST_VALUE)

        callbacks = []

        def callback(info):
            callbacks.append(info)
        s.addInfoWatcher(callback)

        # set the same value again
        s.updateInfo(key=FIRST_VALUE)

        d = eventual.flushEventualQueue()

        @d.addCallback
        def check(_):
            self.assertEqual(callbacks, [])

        return d

    def test_addInfoWatcher_called(self):
        s = self.makeStatus()

        callbacks = []

        def callback(info):
            callbacks.append(info)
        s.addInfoWatcher(callback)

        s.updateInfo(key='value')

        d = eventual.flushEventualQueue()

        @d.addCallback
        def check(_):
            self.assertEqual(callbacks, [{'key': 'value'}])

        return d

    def test_addInfoWatcher_calledOnceForTwoKeys(self):
        s = self.makeStatus()

        callbacks = []

        def callback(info):
            callbacks.append(info)
        s.addInfoWatcher(callback)

        s.updateInfo(key='value', key2='value2')

        d = eventual.flushEventualQueue()

        @d.addCallback
        def check(_):
            self.assertEqual(callbacks, [{'key': 'value', 'key2': 'value2'}])

        return d

    def test_removeInfoWatcher_removeBadObject(self):
        s = self.makeStatus()

        BOGUS_OBJECT = object()
        s.removeInfoWatcher(BOGUS_OBJECT)

    def test_removeInfoWatcher(self):
        s = self.makeStatus()

        callbacks = []

        def callback(info):
            callbacks.append(info)

        s.addInfoWatcher(callback)
        s.removeInfoWatcher(callback)

        s.updateInfo(key='value')

        d = eventual.flushEventualQueue()

        @d.addCallback
        def check(_):
            # never called:
            self.assertEqual(callbacks, [])

        return d

    def test_asDict(self):
        s = self.makeStatus()

        s.setHost('TheHost')
        s.setVersion('TheVersion')
        s.setAccessURI('TheUri')
        s.setAdmin('TheAdmin')
        s.updateInfo(key='value')

        slaveDict = s.asDict()

        self.assertEqual(slaveDict, {
            'host': 'TheHost',
            'version': 'TheVersion',
            'access_uri': 'TheUri',
            'admin': 'TheAdmin',
            'runningBuilds': [],
            'name': self.SLAVE_NAME,
            'connected': False,
            'info': {
                'host': 'TheHost',
                'version': 'TheVersion',
                'access_uri': 'TheUri',
                'admin': 'TheAdmin',
                'key': 'value'
            },
        })
