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

from twisted.internet import defer

from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep
from buildbot.steps.worker import CompositeStepMixin


class WorkerFileSecret(object):

    def __init__(self, path, secretvalue):
        self.path = path
        if not isinstance(self.path, str):
            raise ValueError("Secret path %s is not a string" % path)
        self.secretvalue = secretvalue
        if not os.path.exists(os.path.dirname(self.path)):
            raise ValueError("Path %s does not exist")


class DownloadSecretsToWorker(BuildStep, CompositeStepMixin):

    def __init__(self, populated_secret_list, **kwargs):
        super(DownloadSecretsToWorker, self).__init__(**kwargs)
        self.secret_to_be_populated = []
        for path, secretvalue in populated_secret_list:
            self.secret_to_be_populated.append(WorkerFileSecret(path, secretvalue))

    @defer.inlineCallbacks
    def runPopulateSecrets(self):
        all_results = []
        for secret in self.secret_to_be_populated:
            res = yield self.downloadFileContentToWorker(secret.path, secret.secretvalue)
            all_results.append(res)
        if FAILURE in all_results:
            result = FAILURE
        else:
            result = SUCCESS
        defer.returnValue(result)

    @defer.inlineCallbacks
    def run(self):
        self._start_deferred = None
        res = yield self.runPopulateSecrets()
        defer.returnValue(res)


class RemoveWorkerFileSecret(BuildStep, CompositeStepMixin):

    def __init__(self, paths, logEnviron=False, **kwargs):
        self.paths = paths
        self.logEnviron = logEnviron
        super(RemoveWorkerFileSecret, self).__init__(**kwargs)

    @defer.inlineCallbacks
    def runRemoveWorkerFileSecret(self):
        all_results = []
        for path in self.paths:
            res = yield self.runRmFile(path, abandonOnFailure=False)
            all_results.append(res)
        if FAILURE in all_results:
            result = FAILURE
        else:
            result = SUCCESS
        defer.returnValue(result)

    @defer.inlineCallbacks
    def run(self):
        self._start_deferred = None
        res = yield self.runRemoveWorkerFileSecret()
        defer.returnValue(res)
