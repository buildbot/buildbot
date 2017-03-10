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
# To be run, the test use a Vault server instance.
# To easily run a Vault instance find the dockerfile dedictaed to Vault.
# command: docker-compose up
# Note the Vault docker image address and port.
# connect to the docker instance:
# command: docker exec -i -t ``docker_vault_image_name`` /bin/sh
# All the following commands will be done in the docker instance shell.
# Export the server address:
# command: export VAULT_SERVER = "http://vaultServeraddress:port"
# Then init Vault:
# command: vault init
# the command return 5 unseal keys and a Vault root token, please note them,
# they won't be given twice!
# Export the server address:
# command: export VAULT_TOKEN = "vault_token"
# Once initialized, unseal vault:
# command: vault unseal
# The command has to be done 3 times, 3 of the 5 unseal keys will be necessary.
# When Vault is ready, "unealed", you can add a new key/password.
# By default Vault stores password in the "secret" mount. Add a password:
# command: vault write secret/userp value=your_password

class SecretsConfig(RunMasterBase):

    def setUp(self):
        if "BBTEST_VAULTURL" not in os.environ and "BBTEST_VAULTTOKEN" not in os.environ:
            raise SkipTest(
                "Vault integration tests only run when environment variable "
                "BBTEST_VAULTURL is set with url to Vault api server and "
                "variable BBTEST_VAULTTOKEN is set with a valid token to Vault "
                "server")

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
        vaultServer=os.environ.get("BBTEST_VAULTURL")
    )]

    f = BuildFactory()
    f.addStep(ShellCommand(command=[Interpolate('echo %(secrets:userp)s')]))

    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
