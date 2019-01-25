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

import stat

from twisted.internet import defer

from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep
from buildbot.process.results import worst_status
from buildbot.steps.worker import CompositeStepMixin


class DownloadSecretsToWorker(BuildStep, CompositeStepMixin):

    renderables = ['secret_to_be_populated']

    def __init__(self, populated_secret_list, **kwargs):
        super(DownloadSecretsToWorker, self).__init__(**kwargs)
        self.secret_to_be_populated = populated_secret_list

    @defer.inlineCallbacks
    def runPopulateSecrets(self):
        result = SUCCESS
        for path, secretvalue in self.secret_to_be_populated:
            if not isinstance(path, str):
                raise ValueError("Secret path %s is not a string" % path)
            self.secret_to_be_interpolated = secretvalue
            res = yield self.downloadFileContentToWorker(path, self.secret_to_be_interpolated, mode=stat.S_IRUSR | stat.S_IWUSR)
            result = worst_status(result, res)
        return result

    @defer.inlineCallbacks
    def run(self):
        self._start_deferred = None
        res = yield self.runPopulateSecrets()
        return res


class RemoveWorkerFileSecret(BuildStep, CompositeStepMixin):

    def __init__(self, populated_secret_list, logEnviron=False, **kwargs):
        self.paths = []
        for path, secret in populated_secret_list:
            self.paths.append(path)
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
        return result

    @defer.inlineCallbacks
    def run(self):
        self._start_deferred = None
        res = yield self.runRemoveWorkerFileSecret()
        return res
