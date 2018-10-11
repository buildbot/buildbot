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
from future.utils import iteritems

from distutils.version import LooseVersion

from twisted.internet import defer
from twisted.python import log

from buildbot import config as bbconfig
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process.properties import Properties

RC_SUCCESS = 0


def getSshCommand(keyPath, knownHostsPath):
    command = ['ssh']
    if keyPath is not None:
        command += ['-i', '"{0}"'.format(keyPath)]
    if knownHostsPath is not None:
        command += ['-o', '"UserKnownHostsFile={0}"'.format(knownHostsPath)]
    return ' '.join(command)


class GitMixin(object):

    def setupGit(self):
        self.gitInstalled = False
        self.supportsBranch = False
        self.supportsSubmoduleForce = False
        self.supportsSubmoduleCheckout = False
        self.supportsSshPrivateKeyAsEnvOption = False
        self.supportsSshPrivateKeyAsConfigOption = False

    def parseGitFeatures(self, version_stdout):

        if 'git' not in version_stdout:
            return

        try:
            version = version_stdout.strip().split(' ')[2]
        except IndexError:
            return

        self.gitInstalled = True
        if LooseVersion(version) >= LooseVersion("1.6.5"):
            self.supportsBranch = True
        if LooseVersion(version) >= LooseVersion("1.7.6"):
            self.supportsSubmoduleForce = True
        if LooseVersion(version) >= LooseVersion("1.7.8"):
            self.supportsSubmoduleCheckout = True
        if LooseVersion(version) >= LooseVersion("2.3.0"):
            self.supportsSshPrivateKeyAsEnvOption = True
        if LooseVersion(version) >= LooseVersion("2.10.0"):
            self.supportsSshPrivateKeyAsConfigOption = True

    def adjustCommandParamsForSshPrivateKey(self, command, env,
                                            keyPath, sshWrapperPath=None,
                                            knownHostsPath=None):
        ssh_command = getSshCommand(keyPath, knownHostsPath)

        if self.supportsSshPrivateKeyAsConfigOption:
            command.append('-c')
            command.append('core.sshCommand={0}'.format(ssh_command))
        elif self.supportsSshPrivateKeyAsEnvOption:
            env['GIT_SSH_COMMAND'] = ssh_command
        else:
            if sshWrapperPath is None:
                raise Exception('Only SSH wrapper script is supported but path '
                                'not given')
            env['GIT_SSH'] = sshWrapperPath


def getSshWrapperScriptContents(keyPath, knownHostsPath=None):
    ssh_command = getSshCommand(keyPath, knownHostsPath)

    # note that this works on windows if using git with MINGW embedded.
    return '#!/bin/sh\n{0} "$@"\n'.format(ssh_command)


def getSshKnownHostsContents(hostKey):
    host_name = '*'
    return '{0} {1}'.format(host_name, hostKey)


class GitStepMixin(GitMixin):

    def setupGitStep(self):
        self.didDownloadSshPrivateKey = False
        self.setupGit()

        if self.sshHostKey is not None and self.sshPrivateKey is None:
            bbconfig.error('Git: sshPrivateKey must be provided in order '
                           'use sshHostKey')
            self.sshPrivateKey = None

        if not self.repourl:
            bbconfig.error("Git: must provide repourl.")

    def _isSshPrivateKeyNeededForGitCommand(self, command):
        if not command or self.sshPrivateKey is None:
            return False

        gitCommandsThatNeedSshKey = [
            'clone', 'submodule', 'fetch', 'push'
        ]
        if command[0] in gitCommandsThatNeedSshKey:
            return True
        return False

    def _getSshDataPath(self):
        # we can't use the workdir for temporary ssh-related files, because
        # it's needed when cloning repositories and git does not like the
        # destination directory being non-empty. We have to use separate
        # temporary directory for that data to ensure the confidentiality of it.
        # So instead of
        # '{path}/{to}/{workdir}/.buildbot-ssh-key' we put the key at
        # '{path}/{to}/.{workdir}.buildbot/ssh-key'.

        # basename and dirname interpret the last element being empty for paths
        # ending with a slash
        path_module = self.build.path_module

        workdir = self._getSshDataWorkDir().rstrip('/\\')
        if path_module.isabs(workdir):
            parent_path = path_module.dirname(workdir)
        else:
            parent_path = path_module.join(self.worker.worker_basedir,
                                           path_module.dirname(workdir))

        basename = '.{0}.buildbot'.format(path_module.basename(workdir))
        return path_module.join(parent_path, basename)

    def _getSshPrivateKeyPath(self):
        return self.build.path_module.join(self._getSshDataPath(), 'ssh-key')

    def _getSshHostKeyPath(self):
        return self.build.path_module.join(self._getSshDataPath(), 'ssh-known-hosts')

    def _getSshWrapperScriptPath(self):
        return self.build.path_module.join(self._getSshDataPath(), 'ssh-wrapper.sh')

    def _getSshWrapperScript(self):
        return getSshWrapperScriptContents(self._getSshPrivateKeyPath)

    def _adjustCommandParamsForSshPrivateKey(self, full_command, full_env):

        key_path = self._getSshPrivateKeyPath()
        ssh_wrapper_path = self._getSshWrapperScriptPath()
        host_key_path = None
        if self.sshHostKey is not None:
            host_key_path = self._getSshHostKeyPath()

        self.adjustCommandParamsForSshPrivateKey(full_command, full_env,
                                                 key_path, ssh_wrapper_path,
                                                 host_key_path)

    @defer.inlineCallbacks
    def _dovccmd(self, command, abandonOnFailure=True, collectStdout=False, initialStdin=None):
        full_command = ['git']
        full_env = self.env.copy() if self.env else {}

        if self.config is not None:
            for name, value in iteritems(self.config):
                full_command.append('-c')
                full_command.append('%s=%s' % (name, value))

        if self._isSshPrivateKeyNeededForGitCommand(command):
            self._adjustCommandParamsForSshPrivateKey(full_command, full_env)

        full_command.extend(command)

        # check for the interruptSignal flag
        sigtermTime = None
        interruptSignal = None

        # If possible prefer to send a SIGTERM to git before we send a SIGKILL.
        # If we send a SIGKILL, git is prone to leaving around stale lockfiles.
        # By priming it with a SIGTERM first we can ensure that it has a chance to shut-down gracefully
        # before getting terminated
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
                    "if the command is interrupted/times out\n")
            else:
                interruptSignal = 'TERM'

        cmd = remotecommand.RemoteShellCommand(self.workdir,
                                               full_command,
                                               env=full_env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout,
                                               sigtermTime=sigtermTime,
                                               interruptSignal=interruptSignal,
                                               collectStdout=collectStdout,
                                               initialStdin=initialStdin)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if abandonOnFailure and cmd.didFail():
            log.msg("Source step failed while running command %s" % cmd)
            raise buildstep.BuildStepFailed()
        if collectStdout:
            defer.returnValue(cmd.stdout)
            return
        defer.returnValue(cmd.rc)

    @defer.inlineCallbacks
    def checkBranchSupport(self):
        stdout = yield self._dovccmd(['--version'], collectStdout=True)

        self.parseGitFeatures(stdout)

        defer.returnValue(self.gitInstalled)

    @defer.inlineCallbacks
    def _downloadSshPrivateKeyIfNeeded(self):
        if self.sshPrivateKey is None:
            defer.returnValue(RC_SUCCESS)

        p = Properties()
        p.master = self.master
        private_key = yield p.render(self.sshPrivateKey)
        host_key = yield p.render(self.sshHostKey)

        # not using self.workdir because it may be changed depending on step
        # options
        workdir = self._getSshDataWorkDir()

        yield self.runMkdir(self._getSshDataPath())

        if not self.supportsSshPrivateKeyAsEnvOption:
            yield self.downloadFileContentToWorker(self._getSshWrapperScriptPath(),
                                                   self._getSshWrapperScript(),
                                                   workdir=workdir, mode=0o700)

        yield self.downloadFileContentToWorker(self._getSshPrivateKeyPath(),
                                               private_key,
                                               workdir=workdir, mode=0o400)

        if self.sshHostKey is not None:
            known_hosts_contents = getSshKnownHostsContents(host_key)
            yield self.downloadFileContentToWorker(self._getSshHostKeyPath(),
                                                   known_hosts_contents,
                                                   workdir=workdir, mode=0o400)

        self.didDownloadSshPrivateKey = True
        defer.returnValue(RC_SUCCESS)

    @defer.inlineCallbacks
    def _removeSshPrivateKeyIfNeeded(self):
        if not self.didDownloadSshPrivateKey:
            defer.returnValue(RC_SUCCESS)

        yield self.runRmdir(self._getSshDataPath())
        defer.returnValue(RC_SUCCESS)
