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

from distutils.version import LooseVersion


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
                                            keyPath, sshWrapperPath=None):
        if self.supportsSshPrivateKeyAsConfigOption:
            command.append('-c')
            command.append('core.sshCommand=ssh -i "{0}"'.format(keyPath))
        elif self.supportsSshPrivateKeyAsEnvOption:
            env['GIT_SSH_COMMAND'] = 'ssh -i "{0}"'.format(keyPath)
        else:
            if sshWrapperPath is None:
                raise Exception('Only SSH wrapper script is supported but path '
                                'not given')
            env['GIT_SSH'] = sshWrapperPath
