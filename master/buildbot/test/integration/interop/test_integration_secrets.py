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

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from typing import Any

from parameterized import parameterized
from twisted.internet import defer

from buildbot.process.properties import Interpolate
from buildbot.reporters.http import HttpStatusPush
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.util.integration import RunMasterBase

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class FakeSecretReporter(HttpStatusPush):
    def sendMessage(self, reports: list[dict[str, Any]]) -> None:  # type: ignore[override]
        assert self.auth == ('user', 'myhttppasswd')  # type: ignore[attr-defined]
        self.reported = True


class SecretsConfig(RunMasterBase):
    @defer.inlineCallbacks
    def setup_config(self, use_interpolation: bool) -> InlineCallbacksType[FakeSecretReporter]:
        c = {}
        from buildbot.config import BuilderConfig  # noqa: PLC0415
        from buildbot.plugins import schedulers  # noqa: PLC0415
        from buildbot.plugins import steps  # noqa: PLC0415
        from buildbot.plugins import util  # noqa: PLC0415
        from buildbot.process.factory import BuildFactory  # noqa: PLC0415

        fake_reporter = FakeSecretReporter(
            'http://example.com/hook', auth=('user', Interpolate('%(secret:httppasswd)s'))
        )

        c['services'] = [fake_reporter]
        c['schedulers'] = [schedulers.ForceScheduler(name="force", builderNames=["testy"])]

        c['secretsProviders'] = [
            FakeSecretStorage(  # type: ignore[list-item]
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
            command = ['echo', util.Secret('foo')]  # type: ignore[assignment]

        f.addStep(steps.ShellCommand(command=command))

        c['builders'] = [BuilderConfig(name="testy", workernames=["local1"], factory=f)]  # type: ignore[list-item]
        yield self.setup_master(c)

        return fake_reporter

    # Note that the secret name must be long enough so that it does not crash with random directory
    # or file names in the build dictionary.
    @parameterized.expand([
        ('with_interpolation', True),
        ('plain_command', False),
    ])
    @defer.inlineCallbacks
    def test_secret(self, name: str, use_interpolation: bool) -> InlineCallbacksType[None]:
        fake_reporter = yield self.setup_config(use_interpolation)
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)

        # check the command line
        res = yield self.checkBuildStepLogExist(build, "echo <foo>")

        # also check the secrets are replaced in argv
        yield self.checkBuildStepLogExist(build, "argv:.*echo.*<foo>", regex=True)

        # also check that the correct value goes to the command
        if os.name == "posix" and use_interpolation:
            res &= yield self.checkBuildStepLogExist(build, "The password was there")

        self.assertTrue(res)
        # at this point, build contains all the log and steps info that is in the db
        # we check that our secret is not in there!
        self.assertNotIn("secretvalue", repr(build))
        self.assertTrue(fake_reporter.reported)

    @parameterized.expand([
        ('with_interpolation', True),
        ('plain_command', False),
    ])
    @defer.inlineCallbacks
    def test_secretReconfig(self, name: str, use_interpolation: bool) -> InlineCallbacksType[None]:
        yield self.setup_config(use_interpolation)
        self.master_config_dict['secretsProviders'] = [
            FakeSecretStorage(secretdict={"foo": "different_value", "something": "more"})
        ]

        yield self.master.reconfig()
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        res = yield self.checkBuildStepLogExist(build, "echo <foo>")
        self.assertTrue(res)
        # at this point, build contains all the log and steps info that is in the db
        # we check that our secret is not in there!
        self.assertNotIn("different_value", repr(build))


class SecretsConfigPB(SecretsConfig):
    proto = "pb"


class SecretsConfigMsgPack(SecretsConfig):
    proto = "msgpack"
