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
import stat
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log
from zope.interface import implementer

from buildbot import config
from buildbot.interfaces import IMachineAction
from buildbot.machine.latent import AbstractLatentMachine
from buildbot.util import httpclientservice
from buildbot.util import misc
from buildbot.util import private_tempdir
from buildbot.util import runprocess
from buildbot.util.git import getSshArgsForKeys
from buildbot.util.git import getSshKnownHostsContents

if TYPE_CHECKING:
    from twisted.internet.interfaces import IReactorCore

    from buildbot.util.twisted import InlineCallbacksType


class GenericLatentMachine(AbstractLatentMachine):
    def checkConfig(  # type: ignore[override]
        self, name: str, start_action: IMachineAction, stop_action: IMachineAction, **kwargs: Any
    ) -> None:
        super().checkConfig(name, **kwargs)

        for action, arg_name in [(start_action, 'start_action'), (stop_action, 'stop_action')]:
            if not IMachineAction.providedBy(action):
                msg = f"{arg_name} of {self.name} does not implement required interface"
                raise RuntimeError(msg)

    @defer.inlineCallbacks
    def reconfigService(  # type: ignore[override]
        self, name: str, start_action: IMachineAction, stop_action: IMachineAction, **kwargs: Any
    ) -> InlineCallbacksType[None]:
        yield super().reconfigService(name, **kwargs)
        self.start_action = start_action
        self.stop_action = stop_action

    def start_machine(self) -> defer.Deferred[bool]:
        return self.start_action.perform(self)

    def stop_machine(self) -> defer.Deferred[None]:
        return self.stop_action.perform(self)


@defer.inlineCallbacks
def runProcessLogFailures(
    reactor: IReactorCore, args: list[str], expectedCode: int = 0
) -> InlineCallbacksType[bool]:
    code, stdout, stderr = yield runprocess.run_process(reactor, args)
    if code != expectedCode:
        log.err(
            f'Got unexpected return code when running {args}: '
            f'code: {code}, stdout: {stdout}, stderr: {stderr}'
        )
        return False
    return True


class _LocalMachineActionMixin:
    def setupLocal(self, command: list[str]) -> None:
        if not isinstance(command, list):
            config.error('command parameter must be a list')
        self._command = command

    @defer.inlineCallbacks
    def perform(self, manager: Any) -> InlineCallbacksType[bool]:
        args = yield manager.renderSecrets(self._command)
        return (yield runProcessLogFailures(manager.master.reactor, args))


class _SshActionMixin:
    def setupSsh(
        self,
        sshBin: str,
        host: str,
        remoteCommand: list[str],
        sshKey: str | None = None,
        sshHostKey: str | None = None,
    ) -> None:
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
    def _performImpl(
        self, manager: Any, key_path: str | None, known_hosts_path: str | None
    ) -> InlineCallbacksType[bool]:
        args = getSshArgsForKeys(key_path, known_hosts_path)
        args.append((yield manager.renderSecrets(self._host)))
        args.extend((yield manager.renderSecrets(self._remoteCommand)))
        return (yield runProcessLogFailures(manager.master.reactor, [self._sshBin, *args]))

    @defer.inlineCallbacks
    def _prepareSshKeys(
        self, manager: Any, temp_dir_path: str
    ) -> InlineCallbacksType[tuple[str | None, str | None]]:
        key_path = None
        if self._sshKey is not None:
            ssh_key_data = yield manager.renderSecrets(self._sshKey)

            key_path = os.path.join(temp_dir_path, 'ssh-key')
            misc.writeLocalFile(key_path, ssh_key_data, mode=stat.S_IRUSR)

        known_hosts_path = None
        if self._sshHostKey is not None:
            ssh_host_key_data = yield manager.renderSecrets(self._sshHostKey)
            ssh_host_key_data = getSshKnownHostsContents(ssh_host_key_data)

            known_hosts_path = os.path.join(temp_dir_path, 'ssh-known-hosts')
            misc.writeLocalFile(known_hosts_path, ssh_host_key_data)

        return (key_path, known_hosts_path)

    @defer.inlineCallbacks
    def perform(self, manager: Any) -> InlineCallbacksType[bool]:
        if self._sshKey is not None or self._sshHostKey is not None:
            with private_tempdir.PrivateTemporaryDirectory(
                prefix='ssh-', dir=manager.master.basedir
            ) as temp_dir:
                key_path, hosts_path = yield self._prepareSshKeys(manager, temp_dir)

                ret = yield self._performImpl(manager, key_path, hosts_path)
        else:
            ret = yield self._performImpl(manager, None, None)
        return ret


@implementer(IMachineAction)
class LocalWakeAction(_LocalMachineActionMixin):
    def __init__(self, command: list[str]) -> None:
        self.setupLocal(command)


class LocalWOLAction(LocalWakeAction):
    def __init__(self, wakeMac: str, wolBin: str = 'wakeonlan') -> None:
        LocalWakeAction.__init__(self, [wolBin, wakeMac])


@implementer(IMachineAction)
class RemoteSshWakeAction(_SshActionMixin):
    def __init__(
        self,
        host: str,
        remoteCommand: list[str],
        sshBin: str = 'ssh',
        sshKey: str | None = None,
        sshHostKey: str | None = None,
    ) -> None:
        self.setupSsh(sshBin, host, remoteCommand, sshKey=sshKey, sshHostKey=sshHostKey)


class RemoteSshWOLAction(RemoteSshWakeAction):
    def __init__(
        self,
        host: str,
        wakeMac: str,
        wolBin: str = 'wakeonlan',
        sshBin: str = 'ssh',
        sshKey: str | None = None,
        sshHostKey: str | None = None,
    ) -> None:
        RemoteSshWakeAction.__init__(
            self, host, [wolBin, wakeMac], sshBin=sshBin, sshKey=sshKey, sshHostKey=sshHostKey
        )


@implementer(IMachineAction)
class RemoteSshSuspendAction(_SshActionMixin):
    def __init__(
        self,
        host: str,
        remoteCommand: list[str] | None = None,
        sshBin: str = 'ssh',
        sshKey: str | None = None,
        sshHostKey: str | None = None,
    ) -> None:
        if remoteCommand is None:
            remoteCommand = ['systemctl', 'suspend']
        self.setupSsh(sshBin, host, remoteCommand, sshKey=sshKey, sshHostKey=sshHostKey)


@implementer(IMachineAction)
class HttpAction:
    def __init__(
        self,
        url: str,
        method: str,
        params: Any = None,
        data: Any = None,
        json: Any = None,
        headers: Any = None,
        cookies: Any = None,
        files: Any = None,
        auth: Any = None,
        timeout: Any = None,
        allow_redirects: Any = None,
        proxies: Any = None,
    ) -> None:
        self.url = url
        self.method = method
        self.params = params
        self.data = data
        self.json = json
        self.headers = headers
        self.cookies = cookies
        self.files = files
        self.auth = auth
        self.timeout = timeout
        self.allow_redirects = allow_redirects
        self.proxies = proxies

    @defer.inlineCallbacks
    def perform(self, manager: Any) -> InlineCallbacksType[None]:
        (
            url,
            method,
            params,
            data,
            json,
            headers,
            cookies,
            files,
            auth,
            timeout,
            allow_redirects,
            proxies,
        ) = yield manager.renderSecrets((
            self.url,
            self.method,
            self.params,
            self.data,
            self.json,
            self.headers,
            self.cookies,
            self.files,
            self.auth,
            self.timeout,
            self.allow_redirects,
            self.proxies,
        ))

        http = httpclientservice.HTTPSession(manager.master.httpservice, base_url=url)
        if method == 'get':
            fn = http.get
        elif method == 'put':
            fn = http.put
        elif method == 'delete':
            fn = http.delete
        elif method == 'post':
            fn = http.post
        else:
            config.error(f'Invalid method {method}')

        yield fn(
            ep='',
            params=params,
            data=data,
            json=json,
            headers=headers,
            cookies=cookies,
            files=files,
            auth=auth,
            timeout=timeout,
            allow_redirects=allow_redirects,
            proxies=proxies,
        )
