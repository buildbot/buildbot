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

from parameterized import parameterized

import mock

from twisted.internet import defer
from twisted.python import runtime
from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.logging import LoggingMixin
from buildbot.util.runprocess import RunProcess

# windows returns rc 1, because exit status cannot indicate "signalled";
# posix returns rc -1 for "signalled"
FATAL_RC = -1
if runtime.platformType == 'win32':
    FATAL_RC = 1


class TestRunProcess(TestReactorMixin, LoggingMixin, unittest.TestCase):

    FAKE_PID = 1234

    def setUp(self):
        self.setup_test_reactor()
        self.setUpLogging()
        self.process = None
        self.reactor.spawnProcess = self.fake_spawn_process

    def fake_spawn_process(self, pp, command, args, env, workdir, usePTY=False):
        self.assertIsNone(self.process)
        self.pp = pp
        self.pp.transport = mock.Mock()
        self.process = mock.Mock()
        self.process.pid = self.FAKE_PID
        self.process_spawned_args = (command, args, env, workdir)
        return self.process

    def run_process(self, command, override_kill_success=True, override_is_dead=True, **kwargs):
        self.run_process_obj = RunProcess(self.reactor, command, '/workdir', **kwargs)
        self.run_process_obj.get_os_env = lambda: {'OS_ENV': 'value'}
        self.run_process_obj.send_signal = mock.Mock(side_effect=lambda sig: override_kill_success)
        self.run_process_obj.is_dead = mock.Mock(side_effect=lambda: override_is_dead)
        return self.run_process_obj.start()

    def end_process(self, signal=None, rc=0):
        reason = mock.Mock()
        reason.value.signal = signal
        reason.value.exitCode = rc
        self.pp.processEnded(reason)

    @defer.inlineCallbacks
    def test_no_output(self):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=False)
        self.assertEqual(self.process_spawned_args,
                         ('cmd', ['cmd'], {'OS_ENV': 'value', 'PWD': os.path.abspath('/workdir')},
                          '/workdir'))

        self.pp.connectionMade()
        self.assertFalse(d.called)
        self.end_process()
        self.assertTrue(d.called)

        res = yield d
        self.assertEqual(res, (0, b''))

    @defer.inlineCallbacks
    def test_env_new_kv(self):
        d = self.run_process(['cmd'], collect_stdout=False, collect_stderr=False,
                             env={'custom': 'custom-value'})
        self.assertEqual(self.process_spawned_args,
                         ('cmd', ['cmd'], {'OS_ENV': 'value', 'PWD': os.path.abspath('/workdir'),
                                           'custom': 'custom-value'}, '/workdir'))

        self.pp.connectionMade()
        self.end_process()

        res = yield d
        self.assertEqual(res, 0)

    @defer.inlineCallbacks
    def test_env_overwrite_os_kv(self):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=False,
                             env={'OS_ENV': 'custom-value'})
        self.assertEqual(self.process_spawned_args,
                         ('cmd', ['cmd'], {'OS_ENV': 'custom-value',
                                           'PWD': os.path.abspath('/workdir')},
                          '/workdir'))

        self.pp.connectionMade()
        self.end_process()

        res = yield d
        self.assertEqual(res, (0, b''))

    @defer.inlineCallbacks
    def test_env_remove_os_kv(self):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=False,
                             env={'OS_ENV': None})
        self.assertEqual(self.process_spawned_args,
                         ('cmd', ['cmd'], {'PWD': os.path.abspath('/workdir')}, '/workdir'))

        self.pp.connectionMade()
        self.end_process()

        res = yield d
        self.assertEqual(res, (0, b''))

    @defer.inlineCallbacks
    def test_collect_nothing(self):
        d = self.run_process(['cmd'], collect_stdout=False, collect_stderr=False)

        self.pp.connectionMade()
        self.pp.transport.write.assert_not_called()
        self.pp.transport.closeStdin.assert_called()

        self.pp.outReceived(b'stdout_data')
        self.pp.errReceived(b'stderr_data')

        self.assertFalse(d.called)
        self.end_process()
        self.assertTrue(d.called)

        res = yield d
        self.assertEqual(res, 0)

    @defer.inlineCallbacks
    def test_collect_stdout_no_stderr(self):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=False)

        self.pp.connectionMade()
        self.pp.transport.write.assert_not_called()
        self.pp.transport.closeStdin.assert_called()

        self.pp.outReceived(b'stdout_data')
        self.pp.errReceived(b'stderr_data')

        self.assertFalse(d.called)
        self.end_process()
        self.assertTrue(d.called)

        res = yield d
        self.assertEqual(res, (0, b'stdout_data'))

    @defer.inlineCallbacks
    def test_collect_stdout_with_stdin(self):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=False,
                             initial_stdin=b'stdin')

        self.pp.connectionMade()
        self.pp.transport.write.assert_called_with(b'stdin')
        self.pp.transport.closeStdin.assert_called()

        self.pp.outReceived(b'stdout_data')
        self.pp.errReceived(b'stderr_data')
        self.end_process()

        res = yield d
        self.assertEqual(res, (0, b'stdout_data'))

    @defer.inlineCallbacks
    def test_collect_stdout_and_stderr(self):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=True)

        self.pp.connectionMade()
        self.pp.transport.write.assert_not_called()
        self.pp.transport.closeStdin.assert_called()

        self.pp.outReceived(b'stdout_data')
        self.pp.errReceived(b'stderr_data')
        self.end_process()

        res = yield d
        self.assertEqual(res, (0, b'stdout_data', b'stderr_data'))

    @defer.inlineCallbacks
    def test_process_failed_with_rc(self):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=True)

        self.pp.connectionMade()
        self.pp.outReceived(b'stdout_data')
        self.pp.errReceived(b'stderr_data')
        self.end_process(rc=1)

        res = yield d
        self.assertEqual(res, (1, b'stdout_data', b'stderr_data'))

    @defer.inlineCallbacks
    def test_process_failed_with_signal(self):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=True)

        self.pp.connectionMade()
        self.pp.outReceived(b'stdout_data')
        self.pp.errReceived(b'stderr_data')
        self.end_process(signal='SIGILL')

        res = yield d
        self.assertEqual(res, (-1, b'stdout_data', b'stderr_data'))

    @parameterized.expand([
        ('too_short_time_no_output', 0, 4.9, False, False, False),
        ('too_short_time_with_output', 0, 4.9, False, True, True),
        ('timed_out_no_output', 0, 5.1, True, False, False),
        ('timed_out_with_output', 0, 5.1, True, True, True),
        ('stdout_prevented_timeout', 1.0, 4.9, False, True, False),
        ('stderr_prevented_timeout', 1.0, 4.9, False, False, True),
        ('timed_out_after_extra_output', 1.0, 5.1, True, True, True),
    ])
    @defer.inlineCallbacks
    def test_io_timeout(self, name, wait1, wait2, timed_out, had_stdout, had_stderr):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=True, io_timeout=5)

        self.pp.connectionMade()
        self.reactor.advance(wait1)
        if had_stdout:
            self.pp.outReceived(b'stdout_data')
        if had_stderr:
            self.pp.errReceived(b'stderr_data')
        self.reactor.advance(wait2)

        self.assertFalse(d.called)
        self.end_process()
        self.assertTrue(d.called)

        if timed_out:
            self.run_process_obj.send_signal.assert_called_with('TERM')
        else:
            self.run_process_obj.send_signal.assert_not_called()

        res = yield d
        self.assertEqual(res, (FATAL_RC if timed_out else 0,
                               b'stdout_data' if had_stdout else b'',
                               b'stderr_data' if had_stderr else b''))

    @parameterized.expand([
        ('too_short_time', 4.9, False),
        ('timed_out', 5.1, True),
    ])
    @defer.inlineCallbacks
    def test_runtime_timeout(self, name, wait, timed_out):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=True, runtime_timeout=5)

        self.pp.connectionMade()
        self.reactor.advance(wait)

        self.assertFalse(d.called)
        self.end_process()
        self.assertTrue(d.called)

        if timed_out:
            self.run_process_obj.send_signal.assert_called_with('TERM')
        else:
            self.run_process_obj.send_signal.assert_not_called()

        res = yield d
        self.assertEqual(res, (FATAL_RC if timed_out else 0, b'', b''))

    @defer.inlineCallbacks
    def test_runtime_timeout_failing_to_kill(self):
        d = self.run_process(['cmd'], collect_stdout=True, collect_stderr=True, runtime_timeout=5,
                             sigterm_timeout=5, override_is_dead=False)

        self.pp.connectionMade()
        self.reactor.advance(5.1)
        self.run_process_obj.send_signal.assert_called_with('TERM')
        self.reactor.advance(5.1)
        self.run_process_obj.send_signal.assert_called_with('KILL')
        self.reactor.advance(5.1)

        self.assertTrue(d.called)
        self.end_process()

        with self.assertRaises(RuntimeError):
            yield d

        self.assertLogged("attempted to kill process, but it wouldn't die")
