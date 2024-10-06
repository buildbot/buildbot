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

import os

from parameterized import parameterized

from buildbot.process.properties import Interpolate
from buildbot.reporters.http import HttpStatusPush
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.util.integration import RunMasterBase


class FakeSecretReporter(HttpStatusPush):
    def sendMessage(self, reports):
        assert self.auth == ('user', 'myhttppasswd')
        self.reported = True


class SecretsConfig(RunMasterBase):
    async def setup_config(self, use_interpolation):
        c = {}
        from buildbot.config import BuilderConfig
        from buildbot.plugins import schedulers
        from buildbot.plugins import steps
        from buildbot.plugins import util
        from buildbot.process.factory import BuildFactory

        fake_reporter = FakeSecretReporter(
            'http://example.com/hook', auth=('user', Interpolate('%(secret:httppasswd)s'))
        )

        c['services'] = [fake_reporter]
        c['schedulers'] = [schedulers.ForceScheduler(name="force", builderNames=["testy"])]

        c['secretsProviders'] = [
            FakeSecretStorage(
                secretdict={"foo": "secretvalue", "something": "more", 'httppasswd': 'myhttppasswd'}
            )
        ]
        f = BuildFactory()

        if use_interpolation:
            if os.name == "posix":
                # on posix we can also check whether the password was passed to the command
                command = Interpolate(
                    'echo %(secret:foo)s | ' + 'sed "s/secretvalue/The password was there/"'
                )
            else:
                command = Interpolate('echo %(secret:foo)s')
        else:
            command = ['echo', util.Secret('foo')]

        f.addStep(steps.ShellCommand(command=command))

        c['builders'] = [BuilderConfig(name="testy", workernames=["local1"], factory=f)]
        await self.setup_master(c)

        return fake_reporter

    # Note that the secret name must be long enough so that it does not crash with random directory
    # or file names in the build dictionary.
    @parameterized.expand([
        ('with_interpolation', True),
        ('plain_command', False),
    ])
    async def test_secret(self, name, use_interpolation):
        fake_reporter = await self.setup_config(use_interpolation)
        build = await self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)

        # check the command line
        res = await self.checkBuildStepLogExist(build, "echo <foo>")

        # also check the secrets are replaced in argv
        await self.checkBuildStepLogExist(build, "argv:.*echo.*<foo>", regex=True)

        # also check that the correct value goes to the command
        if os.name == "posix" and use_interpolation:
            res &= await self.checkBuildStepLogExist(build, "The password was there")

        self.assertTrue(res)
        # at this point, build contains all the log and steps info that is in the db
        # we check that our secret is not in there!
        self.assertNotIn("secretvalue", repr(build))
        self.assertTrue(fake_reporter.reported)

    @parameterized.expand([
        ('with_interpolation', True),
        ('plain_command', False),
    ])
    async def test_secretReconfig(self, name, use_interpolation):
        await self.setup_config(use_interpolation)
        self.master_config_dict['secretsProviders'] = [
            FakeSecretStorage(secretdict={"foo": "different_value", "something": "more"})
        ]

        await self.master.reconfig()
        build = await self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        res = await self.checkBuildStepLogExist(build, "echo <foo>")
        self.assertTrue(res)
        # at this point, build contains all the log and steps info that is in the db
        # we check that our secret is not in there!
        self.assertNotIn("different_value", repr(build))


class SecretsConfigPB(SecretsConfig):
    proto = "pb"


class SecretsConfigMsgPack(SecretsConfig):
    proto = "msgpack"
