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

import os

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.scripts.logwatcher import BuildmasterStartupError
from buildbot.scripts.logwatcher import BuildmasterTimeoutError
from buildbot.scripts.logwatcher import LogWatcher
from buildbot.scripts.logwatcher import ReconfigError
from buildbot.test.util import dirs
from buildbot.test.util.misc import TestReactorMixin


class TestLogWatcher(unittest.TestCase, dirs.DirsMixin, TestReactorMixin):

    def setUp(self):
        self.setUpDirs('workdir')
        self.addCleanup(self.tearDownDirs)

        self.setUpTestReactor()
        self.spawned_process = mock.Mock()
        self.reactor.spawnProcess = mock.Mock(return_value=self.spawned_process)

    def test_start(self):
        lw = LogWatcher('workdir/test.log', _reactor=self.reactor)
        lw._start = mock.Mock()

        lw.start()
        self.reactor.spawnProcess.assert_called()
        self.assertTrue(os.path.exists('workdir/test.log'))
        self.assertTrue(lw.running)

    @defer.inlineCallbacks
    def test_success_before_timeout(self):
        lw = LogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
        d = lw.start()
        self.reactor.advance(4.9)
        lw.lineReceived(b'BuildMaster is running')
        res = yield d
        self.assertEqual(res, 'buildmaster')

    @defer.inlineCallbacks
    def test_failure_after_timeout(self):
        lw = LogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
        d = lw.start()
        self.reactor.advance(5.1)
        lw.lineReceived(b'BuildMaster is running')
        with self.assertRaises(BuildmasterTimeoutError):
            yield d

    @defer.inlineCallbacks
    def test_progress_restarts_timeout(self):
        lw = LogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
        d = lw.start()
        self.reactor.advance(4.9)
        lw.lineReceived(b'added builder')
        self.reactor.advance(4.9)
        lw.lineReceived(b'BuildMaster is running')
        res = yield d
        self.assertEqual(res, 'buildmaster')

    @defer.inlineCallbacks
    def test_matches_lines(self):
        lines_and_expected = [
            (b'reconfig aborted without making any changes', ReconfigError()),
            (b'WARNING: reconfig partially applied; master may malfunction',
             ReconfigError()),
            (b'Server Shut Down', ReconfigError()),
            (b'BuildMaster startup failed', BuildmasterStartupError()),
            (b'message from master: attached', 'worker'),
            (b'configuration update complete', 'buildmaster'),
            (b'BuildMaster is running', 'buildmaster'),
        ]

        for line, expected in lines_and_expected:
            lw = LogWatcher('workdir/test.log', timeout=5,
                            _reactor=self.reactor)
            d = lw.start()
            lw.lineReceived(line)

            if isinstance(expected, Exception):
                with self.assertRaises(type(expected)):
                    yield d
            else:
                res = yield d
                self.assertEqual(res, expected)
