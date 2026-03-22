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

import os
from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.scripts.logwatcher import BuildmasterStartupError
from buildbot.scripts.logwatcher import BuildmasterTimeoutError
from buildbot.scripts.logwatcher import LogWatcher
from buildbot.scripts.logwatcher import ReconfigError
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import dirs
from buildbot.util import unicode2bytes

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class MockedLogWatcher(LogWatcher):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.printed_output: list[str] = []
        self.created_paths: list[str] = []

    def create_logfile(self, path: str) -> None:
        self.created_paths.append(path)

    def print_output(self, output: str) -> None:
        self.printed_output.append(output)


class TestLogWatcher(dirs.DirsMixin, TestReactorMixin, unittest.TestCase):
    delimiter = unicode2bytes(os.linesep)

    def setUp(self) -> None:
        self.setUpDirs('workdir')

        self.setup_test_reactor()
        self.spawned_process = mock.Mock()
        self.reactor.spawnProcess = mock.Mock(return_value=self.spawned_process)  # type: ignore[method-assign]

    def test_start(self) -> None:
        lw = MockedLogWatcher('workdir/test.log', _reactor=self.reactor)
        lw._start = mock.Mock()  # type: ignore[method-assign]

        lw.start()
        self.reactor.spawnProcess.assert_called()  # type: ignore[attr-defined]
        self.assertEqual(lw.created_paths, ['workdir/test.log'])
        self.assertTrue(lw.running)

    @defer.inlineCallbacks
    def test_success_before_timeout(self) -> InlineCallbacksType[None]:
        lw = MockedLogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
        d = lw.start()
        self.reactor.advance(4.9)
        lw.lineReceived(b'BuildMaster is running')
        res = yield d
        self.assertEqual(res, 'buildmaster')

    @defer.inlineCallbacks
    def test_failure_after_timeout(self) -> InlineCallbacksType[None]:
        lw = MockedLogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
        d = lw.start()
        self.reactor.advance(5.1)
        lw.lineReceived(b'BuildMaster is running')
        with self.assertRaises(BuildmasterTimeoutError):
            yield d

    @defer.inlineCallbacks
    def test_progress_restarts_timeout(self) -> InlineCallbacksType[None]:
        lw = MockedLogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
        d = lw.start()
        self.reactor.advance(4.9)
        lw.lineReceived(b'added builder')
        self.reactor.advance(4.9)
        lw.lineReceived(b'BuildMaster is running')
        res = yield d
        self.assertEqual(res, 'buildmaster')

    @defer.inlineCallbacks
    def test_handles_very_long_lines(self) -> InlineCallbacksType[None]:
        lw = MockedLogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
        d = lw.start()
        lw.dataReceived(
            b't' * lw.MAX_LENGTH * 2 + self.delimiter + b'BuildMaster is running' + self.delimiter
        )
        res = yield d
        self.assertEqual(
            lw.printed_output, ['Got an a very long line in the log (length 32768 bytes), ignoring']
        )
        self.assertEqual(res, 'buildmaster')

    @defer.inlineCallbacks
    def test_handles_very_long_lines_separate_packet(self) -> InlineCallbacksType[None]:
        lw = MockedLogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
        d = lw.start()
        lw.dataReceived(b't' * lw.MAX_LENGTH * 2)
        lw.dataReceived(self.delimiter + b'BuildMaster is running' + self.delimiter)
        res = yield d
        self.assertEqual(
            lw.printed_output, ['Got an a very long line in the log (length 32768 bytes), ignoring']
        )
        self.assertEqual(res, 'buildmaster')

    @defer.inlineCallbacks
    def test_handles_very_long_lines_separate_packet_with_newline(
        self,
    ) -> InlineCallbacksType[None]:
        lw = MockedLogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
        d = lw.start()
        lw.dataReceived(b't' * lw.MAX_LENGTH * 2 + self.delimiter)
        lw.dataReceived(b'BuildMaster is running' + self.delimiter)
        res = yield d
        self.assertEqual(
            lw.printed_output, ['Got an a very long line in the log (length 32768 bytes), ignoring']
        )
        self.assertEqual(res, 'buildmaster')

    @defer.inlineCallbacks
    def test_matches_lines(self) -> InlineCallbacksType[None]:
        lines_and_expected = [
            (b'configuration update aborted without making any changes', ReconfigError()),
            (
                b'WARNING: configuration update partially applied; master may malfunction',
                ReconfigError(),
            ),
            (b'Server Shut Down', ReconfigError()),
            (b'BuildMaster startup failed', BuildmasterStartupError()),
            (b'message from master: attached', 'worker'),
            (b'configuration update complete', 'buildmaster'),
            (b'BuildMaster is running', 'buildmaster'),
        ]

        for line, expected in lines_and_expected:
            lw = MockedLogWatcher('workdir/test.log', timeout=5, _reactor=self.reactor)
            d = lw.start()
            lw.lineReceived(line)

            if isinstance(expected, Exception):
                with self.assertRaises(type(expected)):
                    yield d
            else:
                res = yield d
                self.assertEqual(res, expected)
