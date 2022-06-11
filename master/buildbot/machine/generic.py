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
import stat

from twisted.internet import defer
from twisted.python import log
from zope.interface import implementer

from buildbot import config
from buildbot.interfaces import IMachineAction
from buildbot.machine.latent import AbstractLatentMachine
from buildbot.util import misc
from buildbot.util import private_tempdir
from buildbot.util import runprocess
from buildbot.util.git import getSshArgsForKeys
from buildbot.util.git import getSshKnownHostsContents


class GenericLatentMachine(AbstractLatentMachine):

    def checkConfig(self, name, start_action, stop_action, **kwargs):
        super().checkConfig(name, **kwargs)

        for action, arg_name in [(start_action, 'start_action'),
                                 (stop_action, 'stop_action')]:
            if not IMachineAction.providedBy(action):
                msg = f"{arg_name} of {self.name} does not implement required interface"
                raise Exception(msg)

    @defer.inlineCallbacks
    def reconfigService(self, name, start_action, stop_action, **kwargs):
        yield super().reconfigService(name, **kwargs)
        self.start_action = start_action
        self.stop_action = stop_action

    def start_machine(self):
        return self.start_action.perform(self)

    def stop_machine(self):
        return self.stop_action.perform(self)


@defer.inlineCallbacks
def runProcessLogFailures(reactor, args, expectedCode=0):
    code, stdout, stderr = yield runprocess.run_process(reactor, args)
    if code != expectedCode:
        log.err(f'Got unexpected return code when running {args}: '
                f'code: {code}, stdout: {stdout}, stderr: {stderr}')
        return False
    return True


class _LocalMachineActionMixin:
    def setupLocal(self, command):
        if not isinstance(command, list):
            config.error('command parameter must be a list')
        self._command = command

    @defer.inlineCallbacks
    def perform(self, manager):
        args = yield manager.renderSecrets(self._command)
        return (yield runProcessLogFailures(manager.master.reactor, args))


class _SshActionMixin:
    def setupSsh(self, sshBin, host, remoteCommand, sshKey=None,
                 sshHostKey=None):
        if not isinstance(sshBin, str):
            config.error('sshBin parameter must be a string')
        if not isinstance(host, str):
            config.error('host parameter must be a string')
        if not isinstance(remoteCommand, list):
            config.error('remoteCommand parameter must be a list')

        self._sshBin = sshBin
        self._host = host
        self._remoteCommand = remoteCommand
        self._sshKey = sshKey
        self._sshHostKey = sshHostKey

    @defer.inlineCallbacks
    def _performImpl(self, manager, key_path, known_hosts_path):
        args = getSshArgsForKeys(key_path, known_hosts_path)
        args.append((yield manager.renderSecrets(self._host)))
        args.extend((yield manager.renderSecrets(self._remoteCommand)))
        return (yield runProcessLogFailures(manager.master.reactor, [self._sshBin] + args))

    @defer.inlineCallbacks
    def _prepareSshKeys(self, manager, temp_dir_path):
        key_path = None
        if self._sshKey is not None:
            ssh_key_data = yield manager.renderSecrets(self._sshKey)

            key_path = os.path.join(temp_dir_path, 'ssh-key')
            misc.writeLocalFile(key_path, ssh_key_data,
                                mode=stat.S_IRUSR)

        known_hosts_path = None
        if self._sshHostKey is not None:
            ssh_host_key_data = yield manager.renderSecrets(self._sshHostKey)
            ssh_host_key_data = getSshKnownHostsContents(ssh_host_key_data)

            known_hosts_path = os.path.join(temp_dir_path, 'ssh-known-hosts')
            misc.writeLocalFile(known_hosts_path, ssh_host_key_data)

        return (key_path, known_hosts_path)

    @defer.inlineCallbacks
    def perform(self, manager):
        if self._sshKey is not None or self._sshHostKey is not None:
            with private_tempdir.PrivateTemporaryDirectory(
                    prefix='ssh-', dir=manager.master.basedir) as temp_dir:

                key_path, hosts_path = yield self._prepareSshKeys(manager,
                                                                  temp_dir)

                ret = yield self._performImpl(manager, key_path, hosts_path)
        else:
            ret = yield self._performImpl(manager, None, None)
        return ret


@implementer(IMachineAction)
class LocalWakeAction(_LocalMachineActionMixin):
    def __init__(self, command):
        self.setupLocal(command)


class LocalWOLAction(LocalWakeAction):
    def __init__(self, wakeMac, wolBin='wakeonlan'):
        LocalWakeAction.__init__(self, [wolBin, wakeMac])


@implementer(IMachineAction)
class RemoteSshWakeAction(_SshActionMixin):
    def __init__(self, host, remoteCommand, sshBin='ssh',
                 sshKey=None, sshHostKey=None):
        self.setupSsh(sshBin, host, remoteCommand,
                      sshKey=sshKey, sshHostKey=sshHostKey)


class RemoteSshWOLAction(RemoteSshWakeAction):
    def __init__(self, host, wakeMac, wolBin='wakeonlan', sshBin='ssh',
                 sshKey=None, sshHostKey=None):
        RemoteSshWakeAction.__init__(self, host, [wolBin, wakeMac],
                                     sshBin=sshBin,
                                     sshKey=sshKey, sshHostKey=sshHostKey)


@implementer(IMachineAction)
class RemoteSshSuspendAction(_SshActionMixin):
    def __init__(self, host, remoteCommand=None, sshBin='ssh',
                 sshKey=None, sshHostKey=None):
        if remoteCommand is None:
            remoteCommand = ['systemctl', 'suspend']
        self.setupSsh(sshBin, host, remoteCommand,
                      sshKey=sshKey, sshHostKey=sshHostKey)
