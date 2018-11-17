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

from __future__ import absolute_import
from __future__ import print_function

import os

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.scripts.logwatcher import BuildmasterTimeoutError
from buildbot.scripts.logwatcher import LogWatcher
from buildbot.test.fake.reactor import TestReactor


class TestLogWatcher(unittest.SynchronousTestCase):

    def setUp(self):
        self.reactor = TestReactor()
        self.addCleanup(self.reactor.stop)
        self.spawned_process = mock.Mock()
        self.reactor.spawnProcess = mock.Mock(return_value=self.spawned_process)

    def test_start(self):
        lw = LogWatcher('test.log', _reactor=self.reactor)
        lw._start = mock.Mock()

        lw.start()
        self.reactor.spawnProcess.assert_called()
        self.assertTrue(os.path.exists('test.log'))
        self.assertTrue(lw.running)
        os.remove('test.log')

    @defer.inlineCallbacks
    def test_success_before_timeout(self):
        lw = LogWatcher('test.log', timeout_delay=5, _reactor=self.reactor)
        d = lw.start()
        self.reactor.advance(4.9)
        lw.lineReceived(b'BuildMaster is running')
        res = yield d
        self.assertEqual(res, 'buildmaster')

    @defer.inlineCallbacks
    def test_failure_after_timeout(self):
        lw = LogWatcher('test.log', timeout_delay=5, _reactor=self.reactor)
        d = lw.start()
        self.reactor.advance(5.1)
        lw.lineReceived(b'BuildMaster is running')
        with self.assertRaises(BuildmasterTimeoutError):
            yield d

    @defer.inlineCallbacks
    def test_progress_restarts_timeout(self):
        lw = LogWatcher('test.log', timeout_delay=5, _reactor=self.reactor)
        d = lw.start()
        self.reactor.advance(4.9)
        lw.lineReceived(b'added builder')
        self.reactor.advance(4.9)
        lw.lineReceived(b'BuildMaster is running')
        res = yield d
        self.assertEqual(res, 'buildmaster')
