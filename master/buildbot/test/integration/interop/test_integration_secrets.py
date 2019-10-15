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

from twisted.internet import defer

from buildbot.process.properties import Interpolate
from buildbot.reporters.http import HttpStatusPush
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.util.integration import RunMasterBase


class FakeSecretReporter(HttpStatusPush):
    def send(self, build):
        assert self.auth == ('user', 'myhttppasswd')
        self.reported = True


class SecretsConfig(RunMasterBase):

    @parameterized.expand([
        ('with_interpolation', True),
        ('plain_command', False),
    ])
    @defer.inlineCallbacks
    def test_secret(self, name, use_interpolation):
        c = masterConfig(use_interpolation)
        yield self.setupConfig(c)
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
        self.assertNotIn("bar", repr(build))
        self.assertTrue(c['services'][0].reported)

    @parameterized.expand([
        ('with_interpolation', True),
        ('plain_command', False),
    ])
    @defer.inlineCallbacks
    def test_secretReconfig(self, name, use_interpolation):
        c = masterConfig(use_interpolation)
        yield self.setupConfig(c)
        c['secretsProviders'] = [FakeSecretStorage(
            secretdict={"foo": "different_value", "something": "more"})]
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


# master configuration
def masterConfig(use_interpolation):
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import schedulers, steps, util

    c['services'] = [FakeSecretReporter('http://example.com/hook',
                                        auth=('user', Interpolate('%(secret:httppasswd)s')))]
    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]

    c['secretsProviders'] = [FakeSecretStorage(
        secretdict={"foo": "bar", "something": "more", 'httppasswd': 'myhttppasswd'})]
    f = BuildFactory()

    if use_interpolation:
        if os.name == "posix":
            # on posix we can also check whether the password was passed to the command
            command = Interpolate('echo %(secret:foo)s | sed "s/bar/The password was there/"')
        else:
            command = Interpolate('echo %(secret:foo)s')
    else:
        command = ['echo', util.Secret('foo')]

    f.addStep(steps.ShellCommand(command=command))

    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
