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


from buildbot.process import results
from buildbot.process.buildstep import BuildStep
from buildbot.steps.worker import CompositeStepMixin
from buildbot.test.util.integration import RunMasterBase


class TestCompositeMixinStep(BuildStep, CompositeStepMixin):
    def __init__(self, is_list_mkdir, is_list_rmdir):
        super().__init__()
        self.logEnviron = False
        self.is_list_mkdir = is_list_mkdir
        self.is_list_rmdir = is_list_rmdir

    async def run(self):
        contents = await self.runGlob('*')
        if contents != []:
            return results.FAILURE

        paths = ['composite_mixin_test_1', 'composite_mixin_test_2']
        for path in paths:
            has_path = await self.pathExists(path)

            if has_path:
                return results.FAILURE

        if self.is_list_mkdir:
            await self.runMkdir(paths)
        else:
            for path in paths:
                await self.runMkdir(path)

        for path in paths:
            has_path = await self.pathExists(path)
            if not has_path:
                return results.FAILURE

        contents = await self.runGlob('*')
        contents.sort()

        for i, path in enumerate(paths):
            if not contents[i].endswith(path):
                return results.FAILURE

        if self.is_list_rmdir:
            await self.runRmdir(paths)
        else:
            for path in paths:
                await self.runRmdir(path)

        for path in paths:
            has_path = await self.pathExists(path)
            if has_path:
                return results.FAILURE

        return results.SUCCESS


# This integration test creates a master and worker environment,
# and makes sure the composite step mixin is working.
class CompositeStepMixinMaster(RunMasterBase):
    async def setup_config(self, is_list_mkdir=True, is_list_rmdir=True):
        c = {}
        from buildbot.config import BuilderConfig
        from buildbot.plugins import schedulers
        from buildbot.process.factory import BuildFactory

        c['schedulers'] = [schedulers.AnyBranchScheduler(name="sched", builderNames=["testy"])]

        f = BuildFactory()
        f.addStep(TestCompositeMixinStep(is_list_mkdir=is_list_mkdir, is_list_rmdir=is_list_rmdir))
        c['builders'] = [BuilderConfig(name="testy", workernames=["local1"], factory=f)]

        await self.setup_master(c)

    async def test_compositemixin_rmdir_list(self):
        await self.do_compositemixin_test(is_list_mkdir=False, is_list_rmdir=True)

    async def test_compositemixin(self):
        await self.do_compositemixin_test(is_list_mkdir=False, is_list_rmdir=False)

    async def do_compositemixin_test(self, is_list_mkdir, is_list_rmdir):
        await self.setup_config(is_list_mkdir=is_list_mkdir, is_list_rmdir=is_list_rmdir)

        change = {
            "branch": "master",
            "files": ["foo.c"],
            "author": "me@foo.com",
            "committer": "me@foo.com",
            "comments": "good stuff",
            "revision": "HEAD",
            "project": "none",
        }
        build = await self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(build['results'], results.SUCCESS)


class CompositeStepMixinMasterPb(CompositeStepMixinMaster):
    proto = "pb"


class CompositeStepMixinMasterMsgPack(CompositeStepMixinMaster):
    proto = "msgpack"

    async def test_compositemixin_mkdir_rmdir_lists(self):
        await self.do_compositemixin_test(is_list_mkdir=True, is_list_rmdir=True)
