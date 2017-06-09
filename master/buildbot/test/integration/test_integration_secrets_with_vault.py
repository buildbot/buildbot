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
from unittest.case import SkipTest

from twisted.internet import defer

from buildbot.process.properties import Interpolate
from buildbot.secrets.providers.vault import HashiCorpVaultSecretProvider
from buildbot.steps.shell import ShellCommand
from buildbot.test.util.integration import RunMasterBase

# This integration test creates a master and worker environment,
# with one builders and a shellcommand step


class SecretsConfig(RunMasterBase):

    def setUp(self):
        rv = os.system("docker run -d -e SKIP_SETCAP=yes -e "
                       "'VAULT_DEV_ROOT_TOKEN_ID=my_vaulttoken' -e 'VAULT_TOKEN=my_vaulttoken'"
                       " --name=vault_for_buildbot -p 8200:8200 vault")

        if rv != 0:
            raise SkipTest(
                "Vault integration need docker environment to be setup")

        os.system("docker exec vault_for_buildbot "
                  "vault write -address 'http://localhost:8200' secret/key value=word")

    def tearDown(self):
        os.system("docker rm -f vault_for_buildbot")

    @defer.inlineCallbacks
    def test_secret(self):
        yield self.setupConfig(masterConfig())
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        res = yield self.checkBuildStepLogExist(build, "echo <key>")
        self.assertTrue(res)


def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import schedulers

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]

    c['secretsProviders'] = [HashiCorpVaultSecretProvider(
        vaultToken='my_vaulttoken',
        vaultServer="http://localhost:8200"
    )]

    f = BuildFactory()
    f.addStep(ShellCommand(command=[Interpolate('echo %(secret:key)s')]))

    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
