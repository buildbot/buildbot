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

import os

from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import LoggingBuildStep


class workerFileSecret():

    def __init__(self, path, secretvalue):
        self.path = path
        if not isinstance(self.path, str):
            raise ValueError("Secret path %s is not a string" % path)
        self.secretvalue = secretvalue
        if not os.path.exists(os.path.dirname(self.path)):
            raise ValueError("Path %s does not exist")

    def createSecretFile(self):
        file_path = os.path.join(self.path)
        with open(file_path, 'w') as filetmp:
            filetmp.write(self.secretvalue)


class PushSecretToWorker(LoggingBuildStep):

    def __init__(self, populated_secret_list, **kwargs):
        super(PushSecretToWorker, self).__init__(**kwargs)
        self.secret_to_be_populated = []
        for secretvalue, path in populated_secret_list:
            self.secret_to_be_populated.append(workerFileSecret(secretvalue, path))

    def runPopulateSecrets(self):
        for secret in self.secret_to_be_populated:
            secret.createSecretFile()
        return SUCCESS

    def run(self):
        return self.runPopulateSecrets()


class RemoveWorkerFileSecret(BuildStep):

    def __init__(self, paths, **kwargs):
        self.paths = paths
        super(RemoveWorkerFileSecret, self).__init__(**kwargs)

    def runRemoveWorkerFileSecret(self):
        for path in self.paths:
            if not os.path.exists(path):
                raise ValueError("Path %s does not exist")
            os.remove(path)
        return SUCCESS

    def run(self):
        return self.runRemoveWorkerFileSecret()
