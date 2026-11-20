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

from parameterized import parameterized

from buildbot.config import BuilderConfig
from buildbot.process import results
from buildbot.process.buildstep import BuildStep
from buildbot.process.factory import BuildFactory
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.steps.worker import CompositeStepMixin
from buildbot.test.util.integration import RunMasterBase
from buildbot.util import bytes2unicode
from buildbot.util.twisted import async_to_deferred


class DownloadThenReadBackStep(BuildStep, CompositeStepMixin):
    def __init__(self, content: str | bytes) -> None:
        super().__init__()
        self.content = content

    @async_to_deferred
    async def run(self) -> int:
        await self.downloadFileContentToWorker('file.txt', self.content, abandonOnFailure=True)
        read_back = await self.getFileContentFromWorker('file.txt', abandonOnFailure=True)
        self.setProperty('read_back', read_back, 'test')
        return results.SUCCESS


class DownloadFileContentMaster(RunMasterBase):
    async def setup_config(self, content: str | bytes) -> None:
        f = BuildFactory()
        f.addStep(DownloadThenReadBackStep(content))
        c = {
            'schedulers': [ForceScheduler(name="force", builderNames=["testy"])],
            'builders': [BuilderConfig(name="testy", workernames=["local1"], factory=f)],
        }
        await self.setup_master(c)

    @parameterized.expand([
        ('small_str', 'filecontent'),
        # spans two 32 KiB reader blocks
        ('multi_block_bytes', b'0123456789abcdef' * 2_500),
    ])
    async def test_download_file_content_round_trips(self, name: str, content: str | bytes) -> None:
        await self.setup_config(content)

        build = await self.doForceBuild(wantProperties=True)

        self.assertEqual(build['results'], results.SUCCESS)
        self.assertEqual(build['properties']['read_back'][0], bytes2unicode(content))


class DownloadFileContentMasterPb(DownloadFileContentMaster):
    proto = "pb"


class DownloadFileContentMasterMsgPack(DownloadFileContentMaster):
    proto = "msgpack"
