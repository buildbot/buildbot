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

import mock

from twisted.trial import unittest

from buildbot.process import remotecommand
from buildbot.test.fake import remotecommand as fakeremotecommand
from buildbot.test.fake import logfile
from buildbot.test.util import interfaces
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


class TestRemoteShellCommand(unittest.TestCase):

    def test_obfuscated_arguments(self):
        command = ["echo",
                   ("obfuscated", "real", "fake"),
                   "test",
                   ("obfuscated", "real2", "fake2"),
                   ("not obfuscated", "a", "b"),
                   ("obfuscated"),  # not obfuscated
                   ("obfuscated", "test"),  # not obfuscated
                   ("obfuscated", "1", "2", "3"),  # not obfuscated)
                   ]
        cmd = remotecommand.RemoteShellCommand("build", command)
        self.assertEqual(cmd.command, command)
        self.assertEqual(cmd.fake_command, ["echo",
                                            "fake",
                                            "test",
                                            "fake2",
                                            ("not obfuscated", "a", "b"),
                                            ("obfuscated"),  # not obfuscated
                                            # not obfuscated
                                            ("obfuscated", "test"),
                                            # not obfuscated)
                                            ("obfuscated", "1", "2", "3"),
                                            ])

    def test_not_obfuscated_arguments(self):
        command = "echo test"
        cmd = remotecommand.RemoteShellCommand("build", command)
        self.assertEqual(cmd.command, command)
        self.assertEqual(cmd.fake_command, command)

# NOTE:
#
# This interface is considered private to Buildbot and may change without
# warning in future versions.


class Tests(interfaces.InterfaceTests):

    remoteCommandClass = None

    def makeRemoteCommand(self, stdioLogName='stdio'):
        return self.remoteCommandClass('ping', {'arg': 'val'},
                                       stdioLogName=stdioLogName)

    def test_signature_RemoteCommand_constructor(self):
        @self.assertArgSpecMatches(self.remoteCommandClass.__init__)
        def __init__(self, remote_command, args, ignore_updates=False,
                     collectStdout=False, collectStderr=False,
                     decodeRC=None,
                     stdioLogName='stdio'):
            pass

    def test_signature_RemoteShellCommand_constructor(self):
        @self.assertArgSpecMatches(self.remoteShellCommandClass.__init__)
        def __init__(self, workdir, command, env=None, want_stdout=1,
                     want_stderr=1, timeout=20 * 60, maxTime=None, sigtermTime=None, logfiles=None,
                     usePTY=None, logEnviron=True, collectStdout=False,
                     collectStderr=False, interruptSignal=None, initialStdin=None,
                     decodeRC=None,
                     stdioLogName='stdio'):
            pass

    def test_signature_run(self):
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.run)
        def run(self, step, conn, builder_name):
            pass

    def test_signature_useLog(self):
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.useLog)
        def useLog(self, log_, closeWhenFinished=False, logfileName=None):
            pass

    def test_signature_useLogDelayed(self):
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.useLogDelayed)
        def useLogDelayed(self, logfileName, activateCallBack,
                          closeWhenFinished=False):
            pass

    def test_signature_interrupt(self):
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.interrupt)
        def useLogDelayed(self, why):
            pass

    def test_signature_didFail(self):
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.didFail)
        def useLogDelayed(self):
            pass

    def test_signature_logs(self):
        cmd = self.makeRemoteCommand()
        self.assertIsInstance(cmd.logs, dict)

    def test_signature_active(self):
        cmd = self.makeRemoteCommand()
        self.assertIsInstance(cmd.active, bool)

    def test_RemoteShellCommand_constructor(self):
        self.remoteShellCommandClass('wkdir', 'some-command')


class TestRunCommand(unittest.TestCase, Tests):

    remoteCommandClass = remotecommand.RemoteCommand
    remoteShellCommandClass = remotecommand.RemoteShellCommand

    def test_notStdioLog(self):
        logname = 'notstdio'
        cmd = self.makeRemoteCommand(stdioLogName=logname)
        log = logfile.FakeLogFile(logname, 'dummy')
        cmd.useLog(log)
        cmd.addStdout('some stdout')
        self.assertEqual(log.stdout, 'some stdout')
        cmd.addStderr('some stderr')
        self.assertEqual(log.stderr, 'some stderr')
        cmd.addHeader('some header')
        self.assertEqual(log.header, 'some header')

    def test_RemoteShellCommand_usePTY_on_worker_2_16(self):
        cmd = remotecommand.RemoteShellCommand('workdir', 'shell')

        def workerVersion(command, oldversion=None):
            return '2.16'

        def workerVersionIsOlderThan(command, minversion):
            return ['2', '16'] < minversion.split('.')

        step = mock.Mock()
        step.workerVersionIsOlderThan = workerVersionIsOlderThan
        step.workerVersion = workerVersion
        conn = mock.Mock()
        conn.remoteStartCommand = mock.Mock(return_value=None)

        cmd.run(step, conn, 'builder')

        self.assertEqual(cmd.args['usePTY'], 'slave-config')


class TestFakeRunCommand(unittest.TestCase, Tests):

    remoteCommandClass = fakeremotecommand.FakeRemoteCommand
    remoteShellCommandClass = fakeremotecommand.FakeRemoteShellCommand


class TestWorkerTransition(unittest.TestCase):

    def test_worker_old_api(self):
        cmd = remotecommand.RemoteCommand('cmd', [])

        w = mock.Mock()
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertIdentical(cmd.worker, None)

            cmd.worker = w

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'buildslave' attribute is deprecated"):
            old = cmd.buildslave

        self.assertIdentical(old, w)

    def test_RemoteShellCommand_usePTY(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cmd = remotecommand.RemoteShellCommand(
                'workdir', 'command')

        self.assertTrue(cmd.args['usePTY'] is None)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cmd = remotecommand.RemoteShellCommand(
                'workdir', 'command', usePTY=True)

        self.assertTrue(cmd.args['usePTY'])

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cmd = remotecommand.RemoteShellCommand(
                'workdir', 'command', usePTY=False)

        self.assertFalse(cmd.args['usePTY'])

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slave-config' value of 'usePTY' "
                                "attribute is deprecated"):
            cmd = remotecommand.RemoteShellCommand(
                'workdir', 'command', usePTY='slave-config')

        self.assertTrue(cmd.args['usePTY'] is None)
