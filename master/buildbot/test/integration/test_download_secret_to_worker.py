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
from twisted.trial.unittest import SkipTest

from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.steps.download_secret_to_worker import DownloadSecretsToWorker
from buildbot.steps.download_secret_to_worker import RemoveWorkerFileSecret
from buildbot.test.util.integration import RunMasterBase


class DownloadSecretsBase(RunMasterBase):
    def setUp(self):
        self.temp_dir = os.path.abspath(self.mktemp())
        os.mkdir(self.temp_dir)

    @defer.inlineCallbacks
    def setup_config(self, path, data, remove=False):
        c = {}

        c['schedulers'] = [ForceScheduler(name="force", builderNames=["testy"])]

        f = BuildFactory()
        f.addStep(DownloadSecretsToWorker([(path, data)]))
        if remove:
            f.addStep(RemoveWorkerFileSecret([(path, data)]))

        c['builders'] = [BuilderConfig(name="testy", workernames=["local1"], factory=f)]

        yield self.setup_master(c)

    def get_homedir(self):
        path = os.path.expanduser('~')
        if path == '~':
            return None
        return path

    @parameterized.expand([
        ('simple', False, True),
        ('relative_to_home', True, True),
        ('simple_remove', False, True),
        ('relative_to_home_remove', True, True),
    ])
    @defer.inlineCallbacks
    def test_transfer_secrets(self, name, relative_to_home, remove):
        bb_path = self.temp_dir
        if relative_to_home:
            homedir = self.get_homedir()
            if homedir is None:
                raise SkipTest("Home directory is not known")
            try:
                bb_path = os.path.join('~', os.path.relpath(bb_path, homedir))
            except ValueError as e:
                raise SkipTest("Can't get relative path from home directory to test files") from e
            if not os.path.isdir(os.path.expanduser(bb_path)):
                raise SkipTest("Unknown error preparing test paths")

        path = os.path.join(bb_path, 'secret_path')
        data = 'some data'

        yield self.setup_config(path, data, remove=remove)

        yield self.doForceBuild()

        if remove:
            self.assertFalse(os.path.exists(path))
        else:
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding='utf-8') as f:
                self.assertEqual(f.read(), data)


class DownloadSecretsBasePb(DownloadSecretsBase):
    proto = "pb"


class DownloadSecretsBaseMsgPack(DownloadSecretsBase):
    proto = "msgpack"
