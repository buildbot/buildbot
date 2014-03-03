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

from buildbot.process import remotecommand
from buildbot.status.results import SUCCESS
from buildbot.test.fake import remotecommand as fakeremotecommand
from buildbot.test.util import interfaces
from twisted.trial import unittest


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
                     decodeRC={0: SUCCESS},
                     stdioLogName='stdio'):
            pass

    def test_signature_RemoteShellCommand_constructor(self):
        @self.assertArgSpecMatches(self.remoteShellCommandClass.__init__)
        def __init__(self, workdir, command, env=None, want_stdout=1,
                     want_stderr=1, timeout=20 * 60, maxTime=None, sigtermTime=None, logfiles={},
                     usePTY="slave-config", logEnviron=True, collectStdout=False,
                     collectStderr=False, interruptSignal=None, initialStdin=None,
                     decodeRC={0: SUCCESS},
                     stdioLogName='stdio'):
            pass

    def test_signature_run(self):
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.run)
        def run(self, step, remote):
            pass

    def test_signature_useLog(self):
        cmd = self.makeRemoteCommand()

        @self.assertArgSpecMatches(cmd.useLog)
        def useLog(self, log, closeWhenFinished=False, logfileName=None):
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
        step = mock.Mock(name='step')
        step.logobservers = []
        log = fakeremotecommand.FakeLogFile(logname, step)
        cmd.useLog(log)
        cmd.addStdout('some stdout')
        self.failUnlessEqual(log.stdout, 'some stdout')
        cmd.addStderr('some stderr')
        self.failUnlessEqual(log.stderr, 'some stderr')
        cmd.addHeader('some header')
        self.failUnlessEqual(log.header, 'some header')


class TestFakeRunCommand(unittest.TestCase, Tests):

    remoteCommandClass = fakeremotecommand.FakeRemoteCommand
    remoteShellCommandClass = fakeremotecommand.FakeRemoteShellCommand
