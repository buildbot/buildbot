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

import base64
import subprocess
import time
from unittest.case import SkipTest

from twisted.internet import defer

from buildbot.process.properties import Interpolate
from buildbot.secrets.providers.vault_hvac import HashiCorpVaultKvSecretProvider
from buildbot.secrets.providers.vault_hvac import VaultAuthenticatorToken
from buildbot.steps.shell import ShellCommand
from buildbot.test.util.integration import RunMasterBase

# This integration test creates a master and worker environment,
# with one builders and a shellcommand step


class TestVaultHvac(RunMasterBase):
    def setUp(self):
        try:
            subprocess.check_call(['docker', 'pull', 'vault'])

            subprocess.check_call(['docker', 'run', '-d',
                                   '-e', 'SKIP_SETCAP=yes',
                                   '-e', 'VAULT_DEV_ROOT_TOKEN_ID=my_vaulttoken',
                                   '-e', 'VAULT_TOKEN=my_vaulttoken',
                                   '--name=vault_for_buildbot',
                                   '-p', '8200:8200', 'vault'])
            time.sleep(1)  # the container needs a little time to setup itself
            self.addCleanup(self.remove_container)

            subprocess.check_call(['docker', 'exec',
                                   '-e', 'VAULT_ADDR=http://127.0.0.1:8200/',
                                   'vault_for_buildbot',
                                   'vault', 'kv', 'put', 'secret/key', 'value=word'])

            subprocess.check_call(['docker', 'exec',
                                   '-e', 'VAULT_ADDR=http://127.0.0.1:8200/',
                                   'vault_for_buildbot',
                                   'vault', 'kv', 'put', 'secret/anykey', 'anyvalue=anyword'])

            subprocess.check_call(['docker', 'exec',
                                   '-e', 'VAULT_ADDR=http://127.0.0.1:8200/',
                                   'vault_for_buildbot',
                                   'vault', 'kv', 'put', 'secret/key1/key2', 'id=val'])
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            raise SkipTest("Vault integration needs docker environment to be setup") from e

    def remove_container(self):
        subprocess.call(['docker', 'rm', '-f', 'vault_for_buildbot'])

    @defer.inlineCallbacks
    def do_secret_test(self, secret_specifier, expected_obfuscation, expected_value):
        yield self.setupConfig(master_config(secret_specifier=secret_specifier))
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)

        patterns = [
            f"echo {expected_obfuscation}",
            base64.b64encode((expected_value + "\n").encode('utf-8')).decode('utf-8'),
        ]

        res = yield self.checkBuildStepLogExist(build, patterns)
        self.assertTrue(res)

    @defer.inlineCallbacks
    def test_key(self):
        yield self.do_secret_test('%(secret:key|value)s', '<key|value>', 'word')

    @defer.inlineCallbacks
    def test_key_any_value(self):
        yield self.do_secret_test('%(secret:anykey|anyvalue)s', '<anykey|anyvalue>', 'anyword')

    @defer.inlineCallbacks
    def test_nested_key(self):
        yield self.do_secret_test('%(secret:key1/key2|id)s', '<key1/key2|id>', 'val')


def master_config(secret_specifier):
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import schedulers

    c['schedulers'] = [
        schedulers.ForceScheduler(name="force", builderNames=["testy"])
    ]

    # note that as of August 2021, the vault docker image default to kv
    # version 2 to be enabled by default
    c['secretsProviders'] = [
        HashiCorpVaultKvSecretProvider(authenticator=VaultAuthenticatorToken('my_vaulttoken'),
                                       vault_server="http://localhost:8200",
                                       secrets_mount="secret")
    ]

    f = BuildFactory()
    f.addStep(ShellCommand(command=Interpolate(f'echo {secret_specifier} | base64')))

    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)
    ]

    return c
