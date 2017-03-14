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
import subprocess
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
        proc = subprocess.Popen(["docker run --cap-add=IPC_LOCK -e "
                                 "'VAULT_DEV_ROOT_TOKEN_ID=my_vaulttoken' -e"
                                 " 'VAULT_DEV_LISTEN_ADDRESS=127.0.0.1:8200'"
                                 " --name=vault_for_buildbot -p 8200:8200 vault"],
                                stdout=subprocess.PIPE,
                                shell=True)
        (out, err) = proc.communicate()
        if err is None:
            os.system("export BBTEST_VAULTTOKEN=my_vaulttoken")
        docker_commands = "docker exec vault_for_buildbot /bin/sh -c "\
                          "\"export VAULT_ADDR='http://localhost:8200'; "\
                          "vault write secret/key value=word\""
        os.system(docker_commands)
        if "BBTEST_VAULTTOKEN" not in os.environ:
            raise SkipTest(
                "Vault integration tests only run when environment variable "
                " BBTEST_VAULTTOKEN is set with a valid token to Vault server")

    def tearDown(self):
        image_list = subprocess.check_output("docker ps", shell=True)
        if "vault_for_buildbot" in image_list.decode():
            os.system("docker stop vault_for_buildbot")
            os.system("docker rm vault_for_buildbot")

    @defer.inlineCallbacks
    def test_secret(self):
        yield self.setupConfig(masterConfig())
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)


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
        vaultToken=os.environ.get("BBTEST_VAULTTOKEN"),
        vaultServer="http://localhost:8200"
    )]

    f = BuildFactory()
    f.addStep(ShellCommand(command=[Interpolate('echo %(secrets:key)s')]))

    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
