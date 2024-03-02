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
import re
import stat
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.version import parse as parse_version
from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process.properties import Properties
from buildbot.steps.worker import CompositeStepMixin
from buildbot.util import ComparableMixin
from buildbot.util import bytes2unicode
from buildbot.util.misc import writeLocalFile

if TYPE_CHECKING:
    from buildbot.interfaces import IRenderable
    from buildbot.util.service import BuildbotService

RC_SUCCESS = 0


def getSshArgsForKeys(keyPath, knownHostsPath):
    args = ['-o', 'BatchMode=yes']
    if keyPath is not None:
        args += ['-i', keyPath]
    if knownHostsPath is not None:
        args += ['-o', f'UserKnownHostsFile={knownHostsPath}']
    return args


def escapeShellArgIfNeeded(arg):
    if re.match(r"^[a-zA-Z0-9_-]+$", arg):
        return arg
    return f'"{arg}"'


def getSshCommand(keyPath, knownHostsPath):
    command = ['ssh'] + getSshArgsForKeys(keyPath, knownHostsPath)
    command = [escapeShellArgIfNeeded(arg) for arg in command]
    return ' '.join(command)


def check_ssh_config(
    logname: str,
    ssh_private_key: IRenderable | None,
    ssh_host_key: IRenderable | None,
    ssh_known_hosts: IRenderable | None,
):
    if ssh_host_key is not None and ssh_private_key is None:
        config.error(f'{logname}: sshPrivateKey must be provided in order use sshHostKey')

    if ssh_known_hosts is not None and ssh_private_key is None:
        config.error(f'{logname}: sshPrivateKey must be provided in order use sshKnownHosts')

    if ssh_host_key is not None and ssh_known_hosts is not None:
        config.error(f'{logname}: only one of sshKnownHosts and sshHostKey can be provided')


class GitMixin:
    def setupGit(self):
        self.gitInstalled = False
        self.supportsBranch = False
        self.supportsProgress = False
        self.supportsSubmoduleForce = False
        self.supportsSubmoduleCheckout = False
        self.supportsSshPrivateKeyAsEnvOption = False
        self.supportsSshPrivateKeyAsConfigOption = False
        self.supportsFilters = False

    def parseGitFeatures(self, version_stdout):
        match = re.match(r"^git version (\d+(\.\d+)*)", version_stdout)
        if not match:
            return

        version = parse_version(match.group(1))

        self.gitInstalled = True
        if version >= parse_version("1.6.5"):
            self.supportsBranch = True
        if version >= parse_version("1.7.2"):
            self.supportsProgress = True
        if version >= parse_version("1.7.6"):
            self.supportsSubmoduleForce = True
        if version >= parse_version("1.7.8"):
            self.supportsSubmoduleCheckout = True
        if version >= parse_version("2.3.0"):
            self.supportsSshPrivateKeyAsEnvOption = True
        if version >= parse_version("2.10.0"):
            self.supportsSshPrivateKeyAsConfigOption = True
        if version >= parse_version("2.27.0"):
            self.supportsFilters = True

    def adjustCommandParamsForSshPrivateKey(
        self, command, env, keyPath, sshWrapperPath=None, knownHostsPath=None
    ):
        ssh_command = getSshCommand(keyPath, knownHostsPath)

        if self.supportsSshPrivateKeyAsConfigOption:
            command.append('-c')
            command.append(f'core.sshCommand={ssh_command}')
        elif self.supportsSshPrivateKeyAsEnvOption:
            env['GIT_SSH_COMMAND'] = ssh_command
        else:
            if sshWrapperPath is None:
                raise RuntimeError('Only SSH wrapper script is supported but path not given')
            env['GIT_SSH'] = sshWrapperPath


def getSshWrapperScriptContents(keyPath, knownHostsPath=None):
    ssh_command = getSshCommand(keyPath, knownHostsPath)

    # note that this works on windows if using git with MINGW embedded.
    return f'#!/bin/sh\n{ssh_command} "$@"\n'


def getSshKnownHostsContents(hostKey: str) -> str:
    host_name = '*'
    return f'{host_name} {hostKey}'


def ensureSshKeyNewline(privateKey: str) -> str:
    """Ensure key has trailing newline

    Providers can be configured to strip newlines from secrets. This feature
    breaks SSH key use within the Git module. This helper function ensures that
    when an ssh key is provided for a git step that is contains the trailing
    newline.
    """
    if privateKey.endswith("\n") or privateKey.endswith("\r") or privateKey.endswith("\r\n"):
        return privateKey
    return privateKey + "\n"


class GitStepMixin(GitMixin):
    _git_auth: GitStepAuth

    def setupGitStep(self):
        self.setupGit()

        if not self.repourl:
            config.error("Git: must provide repourl.")

        if not hasattr(self, '_git_auth'):
            self._git_auth = GitStepAuth(self)

    def setup_git_auth(
        self,
        ssh_private_key: IRenderable | None,
        ssh_host_key: IRenderable | None,
        ssh_known_hosts: IRenderable | None,
    ) -> None:
        self._git_auth = GitStepAuth(
            self,
            ssh_private_key,
            ssh_host_key,
            ssh_known_hosts,
        )

    def _get_auth_data_workdir(self) -> str:
        raise NotImplementedError()

    @defer.inlineCallbacks
    def _dovccmd(self, command, abandonOnFailure=True, collectStdout=False, initialStdin=None):
        full_command = ['git']
        full_env = self.env.copy() if self.env else {}

        if self.config is not None:
            for name, value in self.config.items():
                full_command.append('-c')
                full_command.append(f'{name}={value}')

        if command and self._git_auth.is_auth_needed_for_git_command(command[0]):
            self._git_auth.adjust_git_command_params_for_auth(
                full_command,
                full_env,
                self._get_auth_data_workdir(),
                self,
            )

        full_command.extend(command)

        # check for the interruptSignal flag
        sigtermTime = None
        interruptSignal = None

        # If possible prefer to send a SIGTERM to git before we send a SIGKILL.
        # If we send a SIGKILL, git is prone to leaving around stale lockfiles.
        # By priming it with a SIGTERM first we can ensure that it has a chance to shut-down
        # gracefully before getting terminated
        if not self.workerVersionIsOlderThan("shell", "2.16"):
            # git should shut-down quickly on SIGTERM.  If it doesn't don't let it
            # stick around for too long because this is on top of any timeout
            # we have hit.
            sigtermTime = 1
        else:
            # Since sigtermTime is unavailable try to just use SIGTERM by itself instead of
            # killing.  This should be safe.
            if self.workerVersionIsOlderThan("shell", "2.15"):
                log.msg(
                    "NOTE: worker does not allow master to specify "
                    "interruptSignal. This may leave a stale lockfile around "
                    "if the command is interrupted/times out\n"
                )
            else:
                interruptSignal = 'TERM'

        cmd = remotecommand.RemoteShellCommand(
            self.workdir,
            full_command,
            env=full_env,
            logEnviron=self.logEnviron,
            timeout=self.timeout,
            sigtermTime=sigtermTime,
            interruptSignal=interruptSignal,
            collectStdout=collectStdout,
            initialStdin=initialStdin,
        )
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if abandonOnFailure and cmd.didFail():
            log.msg(f"Source step failed while running command {cmd}")
            raise buildstep.BuildStepFailed()
        if collectStdout:
            return cmd.stdout
        return cmd.rc

    @defer.inlineCallbacks
    def checkFeatureSupport(self):
        stdout = yield self._dovccmd(['--version'], collectStdout=True)

        self.parseGitFeatures(stdout)

        return self.gitInstalled


class AbstractGitAuth(ComparableMixin):
    compare_attrs = (
        "ssh_private_key",
        "ssh_host_key",
        "ssh_known_hosts",
    )

    def __init__(
        self,
        ssh_private_key: IRenderable | None = None,
        ssh_host_key: IRenderable | None = None,
        ssh_known_hosts: IRenderable | None = None,
    ) -> None:
        self.did_download_auth_files = False

        self.ssh_private_key = ssh_private_key
        self.ssh_host_key = ssh_host_key
        self.ssh_known_hosts = ssh_known_hosts

        check_ssh_config('Git', self.ssh_private_key, self.ssh_host_key, self.ssh_known_hosts)

    def is_auth_needed_for_git_command(self, git_command: str) -> bool:
        if not git_command or self.ssh_private_key is None:
            return False

        git_commands_that_need_auth = [
            'clone',
            'fetch',
            'ls-remote',
            'push',
            'submodule',
        ]
        if git_command in git_commands_that_need_auth:
            return True
        return False

    @property
    def _path_module(self):
        raise NotImplementedError()

    @property
    def _master(self):
        raise NotImplementedError()

    def _get_ssh_private_key_path(self, ssh_data_path: str) -> str:
        return self._path_module.join(ssh_data_path, 'ssh-key')

    def _get_ssh_host_key_path(self, ssh_data_path: str) -> str:
        return self._path_module.join(ssh_data_path, 'ssh-known-hosts')

    def _get_ssh_wrapper_script_path(self, ssh_data_path: str) -> str:
        return self._path_module.join(ssh_data_path, 'ssh-wrapper.sh')

    def _adjust_command_params_for_ssh_private_key(
        self,
        full_command: list[str],
        full_env: dict[str, str],
        workdir: str,
        git_mixin: GitMixin,
    ) -> None:
        key_path = self._get_ssh_private_key_path(workdir)
        host_key_path = None
        if self.ssh_host_key is not None or self.ssh_known_hosts is not None:
            host_key_path = self._get_ssh_host_key_path(workdir)

        ssh_wrapper_path = self._get_ssh_wrapper_script_path(workdir)

        git_mixin.adjustCommandParamsForSshPrivateKey(
            full_command,
            full_env,
            key_path,
            ssh_wrapper_path,
            host_key_path,
        )

    def adjust_git_command_params_for_auth(
        self,
        full_command: list[str],
        full_env: dict[str, str],
        workdir: str,
        git_mixin: GitMixin,
    ) -> None:
        self._adjust_command_params_for_ssh_private_key(
            full_command,
            full_env,
            workdir=workdir,
            git_mixin=git_mixin,
        )

    def _download_file(
        self,
        path: str,
        content: str,
        mode: int,
        workdir: str | None = None,
    ) -> defer.Deferred[None]:
        raise NotImplementedError()

    @defer.inlineCallbacks
    def download_auth_files_if_needed(
        self,
        workdir: str,
        download_wrapper_script: bool = False,
    ):
        if self.ssh_private_key is None:
            return RC_SUCCESS

        p = Properties()
        p.master = self._master
        private_key = yield p.render(self.ssh_private_key)
        host_key = yield p.render(self.ssh_host_key)
        known_hosts = yield p.render(self.ssh_known_hosts)

        private_key_path = self._get_ssh_private_key_path(workdir)
        private_key = ensureSshKeyNewline(private_key)
        yield self._download_file(
            private_key_path,
            private_key,
            mode=stat.S_IRUSR,
            workdir=workdir,
        )

        known_hosts_path = None
        if self.ssh_host_key is not None or self.ssh_known_hosts is not None:
            known_hosts_path = self._get_ssh_host_key_path(workdir)

            if known_hosts is not None:
                known_hosts_contents = known_hosts
            else:
                known_hosts_contents = getSshKnownHostsContents(host_key)

            yield self._download_file(
                known_hosts_path,
                known_hosts_contents,
                mode=stat.S_IRUSR,
                workdir=workdir,
            )

        if download_wrapper_script:
            private_key_path = self._get_ssh_private_key_path(workdir)
            known_hosts_path = None
            if self.ssh_host_key is not None or self.ssh_known_hosts is not None:
                known_hosts_path = self._get_ssh_host_key_path(workdir)

            script_path = self._get_ssh_wrapper_script_path(workdir)
            script_contents = getSshWrapperScriptContents(private_key_path, known_hosts_path)

            yield self._download_file(
                script_path,
                script_contents,
                mode=stat.S_IRWXU,
                workdir=workdir,
            )

        self.did_download_auth_files = True
        return RC_SUCCESS

    def remove_auth_files_if_needed(self, workdir: str) -> defer.Deferred[int]:
        raise NotImplementedError()


class GitStepAuth(AbstractGitAuth):
    def __init__(
        self,
        # step must implement all these types
        step: buildstep.BuildStep | GitStepMixin | CompositeStepMixin,
        ssh_private_key: IRenderable | None = None,
        ssh_host_key: IRenderable | None = None,
        ssh_known_hosts: IRenderable | None = None,
    ) -> None:
        self.step = step

        super().__init__(ssh_private_key, ssh_host_key, ssh_known_hosts)

    def _get_auth_data_path(self, data_workdir: str) -> str:
        # we can't use the workdir for temporary ssh-related files, because
        # it's needed when cloning repositories and git does not like the
        # destination directory being non-empty. We have to use separate
        # temporary directory for that data to ensure the confidentiality of it.
        # So instead of
        # '{path}/{to}/{workerbuilddir}/{workdir}/.buildbot-ssh-key'
        # we put the key in
        # '{path}/{to}/.{workerbuilddir}.{workdir}.buildbot/ssh-key'.

        # basename and dirname interpret the last element being empty for paths
        # ending with a slash
        assert isinstance(self.step, buildstep.BuildStep) and self.step.build is not None

        workerbuilddir = bytes2unicode(self.step.build.builder.config.workerbuilddir)
        workdir = data_workdir.rstrip('/\\')

        if self._path_module.isabs(workdir):
            parent_path = self._path_module.dirname(workdir)
        else:
            assert self.step.worker is not None
            parent_path = self._path_module.join(
                self.step.worker.worker_basedir, self._path_module.dirname(workdir)
            )

        basename = f'.{workerbuilddir}.{self._path_module.basename(workdir)}.buildbot'
        return self._path_module.join(parent_path, basename)

    def adjust_git_command_params_for_auth(
        self,
        full_command: list[str],
        full_env: dict[str, str],
        workdir: str,
        git_mixin: GitMixin,
    ) -> None:
        auth_data_path = self._get_auth_data_path(workdir)
        super().adjust_git_command_params_for_auth(
            full_command,
            full_env,
            workdir=auth_data_path,
            git_mixin=git_mixin,
        )

    @property
    def _path_module(self):
        assert isinstance(self.step, buildstep.BuildStep) and self.step.build is not None
        return self.step.build.path_module

    @property
    def _master(self):
        assert isinstance(self.step, buildstep.BuildStep) and self.step.master is not None
        return self.step.master

    @defer.inlineCallbacks
    def _download_file(self, path: str, content: str, mode: int, workdir: str | None = None):
        assert isinstance(self.step, CompositeStepMixin)
        yield self.step.downloadFileContentToWorker(
            path,
            content,
            mode=mode,
            workdir=workdir,
        )

    @defer.inlineCallbacks
    def download_auth_files_if_needed(
        self,
        workdir: str,
        download_wrapper_script: bool = False,
    ):
        if self.ssh_private_key is None:
            return RC_SUCCESS

        assert isinstance(self.step, CompositeStepMixin) and isinstance(self.step, GitMixin)

        workdir = self._get_auth_data_path(workdir)
        yield self.step.runMkdir(workdir)

        return_code = yield super().download_auth_files_if_needed(
            workdir=workdir,
            download_wrapper_script=(
                download_wrapper_script or not self.step.supportsSshPrivateKeyAsEnvOption
            ),
        )
        return return_code

    @defer.inlineCallbacks
    def remove_auth_files_if_needed(self, workdir: str):
        if not self.did_download_auth_files:
            return RC_SUCCESS

        assert isinstance(self.step, CompositeStepMixin)
        yield self.step.runRmdir(self._get_auth_data_path(workdir))
        return RC_SUCCESS


class GitServiceAuth(AbstractGitAuth):
    def __init__(
        self,
        service: BuildbotService,
        ssh_private_key: IRenderable | None = None,
        ssh_host_key: IRenderable | None = None,
        ssh_known_hosts: IRenderable | None = None,
    ) -> None:
        self._service = service

        super().__init__(ssh_private_key, ssh_host_key, ssh_known_hosts)

    @property
    def _path_module(self):
        return os.path

    @property
    def _master(self):
        assert self._service.master is not None
        return self._service.master

    def _download_file(
        self,
        path: str,
        content: str,
        mode: int,
        workdir: str | None = None,
    ) -> defer.Deferred[None]:
        writeLocalFile(path, content, mode=mode)
        return defer.succeed(None)

    def remove_auth_files_if_needed(self, workdir: str) -> defer.Deferred[int]:
        if not self.did_download_auth_files:
            return defer.succeed(RC_SUCCESS)

        Path(self._get_ssh_private_key_path(workdir)).unlink(missing_ok=True)
        Path(self._get_ssh_host_key_path(workdir)).unlink(missing_ok=True)

        return defer.succeed(RC_SUCCESS)
