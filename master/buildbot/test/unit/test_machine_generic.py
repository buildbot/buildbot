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
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.machine.generic import LocalWakeAction
from buildbot.machine.generic import LocalWOLAction
from buildbot.machine.generic import RemoteSshSuspendAction
from buildbot.machine.generic import RemoteSshWakeAction
from buildbot.machine.generic import RemoteSshWOLAction
from buildbot.test.fake.private_tempdir import MockPrivateTemporaryDirectory
from buildbot.test.util import config
from buildbot.test.util import gpo


class FakeManager:

    def __init__(self, basedir=None):
        self.master = mock.Mock()
        self.master.basedir = basedir

    def renderSecrets(self, args):
        return defer.succeed(args)


class TestActions(unittest.TestCase, gpo.GetProcessOutputMixin,
                  config.ConfigErrorsMixin):
    def setUp(self):
        self.setUpGetProcessOutput()

    def tearDown(self):
        pass

    @defer.inlineCallbacks
    def test_local_wake_action(self):
        self.expectCommands(
            gpo.Expect('cmd', 'arg1', 'arg2')
            .exit(1),
            gpo.Expect('cmd', 'arg1', 'arg2')
            .exit(0),
        )

        manager = FakeManager()
        action = LocalWakeAction(['cmd', 'arg1', 'arg2'])
        self.assertFalse((yield action.perform(manager)))
        self.assertTrue((yield action.perform(manager)))
        self.assertAllCommandsRan()

    def test_local_wake_action_command_not_list(self):
        with self.assertRaisesConfigError('command parameter must be a list'):
            LocalWakeAction('not-list')

    @defer.inlineCallbacks
    def test_local_wol_action(self):
        self.expectCommands(
            gpo.Expect('wol', '00:11:22:33:44:55')
            .exit(1),
            gpo.Expect('wakeonlan', '00:11:22:33:44:55')
            .exit(0),
        )

        manager = FakeManager()
        action = LocalWOLAction('00:11:22:33:44:55', wolBin='wol')
        self.assertFalse((yield action.perform(manager)))

        action = LocalWOLAction('00:11:22:33:44:55')
        self.assertTrue((yield action.perform(manager)))
        self.assertAllCommandsRan()

    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory',
                new_callable=MockPrivateTemporaryDirectory)
    @mock.patch('buildbot.util.misc.writeLocalFile')
    @defer.inlineCallbacks
    def test_remote_ssh_wake_action_no_keys(self, write_local_file_mock,
                                            temp_dir_mock):
        self.expectCommands(
            gpo.Expect('ssh', 'remote_host', 'remotebin', 'arg1')
            .exit(1),
            gpo.Expect('ssh', 'remote_host', 'remotebin', 'arg1')
            .exit(0),
        )

        manager = FakeManager()
        action = RemoteSshWakeAction('remote_host', ['remotebin', 'arg1'])
        self.assertFalse((yield action.perform(manager)))
        self.assertTrue((yield action.perform(manager)))
        self.assertAllCommandsRan()

        self.assertEqual(temp_dir_mock.dirs, [])
        write_local_file_mock.assert_not_called()

    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory',
                new_callable=MockPrivateTemporaryDirectory)
    @mock.patch('buildbot.util.misc.writeLocalFile')
    @defer.inlineCallbacks
    def test_remote_ssh_wake_action_with_keys(self, write_local_file_mock,
                                              temp_dir_mock):
        temp_dir_path = os.path.join('path-to-master', 'ssh-@@@')
        ssh_key_path = os.path.join(temp_dir_path, 'ssh-key')
        ssh_known_hosts_path = os.path.join(temp_dir_path, 'ssh-known-hosts')

        self.expectCommands(
            gpo.Expect('ssh', '-i', ssh_key_path,
                       '-o', 'UserKnownHostsFile={0}'.format(ssh_known_hosts_path),
                       'remote_host', 'remotebin', 'arg1')
            .exit(0),
        )

        manager = FakeManager('path-to-master')
        action = RemoteSshWakeAction('remote_host', ['remotebin', 'arg1'],
                                     sshKey='ssh_key',
                                     sshHostKey='ssh_host_key')
        self.assertTrue((yield action.perform(manager)))

        self.assertAllCommandsRan()

        self.assertEqual(temp_dir_mock.dirs,
                         [(temp_dir_path, 0o700)])

        self.assertSequenceEqual(write_local_file_mock.call_args_list, [
            mock.call(ssh_key_path, 'ssh_key', mode=0o400),
            mock.call(ssh_known_hosts_path, '* ssh_host_key'),
        ])

    def test_remote_ssh_wake_action_sshBin_not_str(self):
        with self.assertRaisesConfigError('sshBin parameter must be a string'):
            RemoteSshWakeAction('host', ['cmd'], sshBin=123)

    def test_remote_ssh_wake_action_host_not_str(self):
        with self.assertRaisesConfigError('host parameter must be a string'):
            RemoteSshWakeAction(123, ['cmd'])

    def test_remote_ssh_wake_action_command_not_list(self):
        with self.assertRaisesConfigError(
                'remoteCommand parameter must be a list'):
            RemoteSshWakeAction('host', 'cmd')

    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory',
                new_callable=MockPrivateTemporaryDirectory)
    @mock.patch('buildbot.util.misc.writeLocalFile')
    @defer.inlineCallbacks
    def test_remote_ssh_wol_action_no_keys(self, write_local_file_mock,
                                           temp_dir_mock):
        self.expectCommands(
            gpo.Expect('ssh', 'remote_host', 'wakeonlan', '00:11:22:33:44:55')
            .exit(0),
            gpo.Expect('ssh', 'remote_host', 'wolbin', '00:11:22:33:44:55')
            .exit(0),
        )

        manager = FakeManager()
        action = RemoteSshWOLAction('remote_host', '00:11:22:33:44:55')
        self.assertTrue((yield action.perform(manager)))

        action = RemoteSshWOLAction('remote_host', '00:11:22:33:44:55',
                                    wolBin='wolbin')
        self.assertTrue((yield action.perform(manager)))
        self.assertAllCommandsRan()

        self.assertEqual(temp_dir_mock.dirs, [])
        write_local_file_mock.assert_not_called()

    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory',
                new_callable=MockPrivateTemporaryDirectory)
    @mock.patch('buildbot.util.misc.writeLocalFile')
    @defer.inlineCallbacks
    def test_remote_ssh_suspend_action_no_keys(self, write_local_file_mock,
                                               temp_dir_mock):
        self.expectCommands(
            gpo.Expect('ssh', 'remote_host', 'systemctl', 'suspend')
            .exit(0),
            gpo.Expect('ssh', 'remote_host', 'dosuspend', 'arg1')
            .exit(0),
        )

        manager = FakeManager()
        action = RemoteSshSuspendAction('remote_host')
        self.assertTrue((yield action.perform(manager)))

        action = RemoteSshSuspendAction('remote_host',
                                        remoteCommand=['dosuspend', 'arg1'])
        self.assertTrue((yield action.perform(manager)))
        self.assertAllCommandsRan()

        self.assertEqual(temp_dir_mock.dirs, [])
        write_local_file_mock.assert_not_called()
