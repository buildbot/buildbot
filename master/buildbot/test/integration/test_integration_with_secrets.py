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

from twisted.internet import defer

from buildbot.process.properties import Interpolate
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.util.integration import RunMasterBase


class SecretsConfig(RunMasterBase):

    @defer.inlineCallbacks
    def test_secret(self):
        yield self.setupConfig(masterConfig())
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        res = yield self.checkBuildStepLogExist(build, "<foo>")
        self.assertTrue(res)

    @defer.inlineCallbacks
    def test_withsecrets(self):
        yield self.setupConfig(masterConfig(use_with=True))
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        res = yield self.checkBuildStepLogExist(build, "<foo>")
        self.assertTrue(res)


# master configuration
def masterConfig(use_with=False):
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import schedulers, steps

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]

    c['secretsProviders'] = [FakeSecretStorage(
        secretdict={"foo": "bar", "something": "more"})]
    f = BuildFactory()
    if use_with:
        secrets_list = [("pathA", Interpolate('%(secret:something)s'))]
        with f.withSecrets(secrets_list):
            f.addStep(steps.ShellCommand(command=Interpolate('echo %(secret:foo)s')))
    else:
        f.addSteps([steps.ShellCommand(command=Interpolate('echo %(secret:foo)s'))],
                   withSecrets=[("pathA", Interpolate('%(secret:something)s'))])
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
