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


import sys

from buildbot.config import BuilderConfig
from buildbot.plugins import schedulers
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.test.util.integration import RunMasterBase
from buildbot.util import asyncSleep


# This integration test creates a master and worker environment,
# with one builders and a shellcommand step
# meant to be a template for integration steps
class ShellMaster(RunMasterBase):
    async def setup_config_for_master_command(self, **kwargs):
        c = {}

        c['schedulers'] = [schedulers.AnyBranchScheduler(name="sched", builderNames=["testy"])]

        f = BuildFactory()
        f.addStep(steps.MasterShellCommand(**kwargs))
        c['builders'] = [BuilderConfig(name="testy", workernames=["local1"], factory=f)]
        await self.setup_master(c)

    def get_change(self):
        return {
            "branch": "master",
            "files": ["foo.c"],
            "author": "me@foo.com",
            "committer": "me@foo.com",
            "comments": "good stuff",
            "revision": "HEAD",
            "project": "none",
        }

    async def test_shell(self):
        await self.setup_config_for_master_command(command='echo hello')

        build = await self.doForceBuild(wantSteps=True, useChange=self.get_change(), wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(build['steps'][1]['state_string'], 'Ran')

    async def test_logs(self):
        await self.setup_config_for_master_command(command=[sys.executable, '-c', 'print("hello")'])

        build = await self.doForceBuild(wantSteps=True, useChange=self.get_change(), wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        res = await self.checkBuildStepLogExist(build, "hello")
        self.assertTrue(res)
        self.assertEqual(build['steps'][1]['state_string'], 'Ran')

    async def test_fails(self):
        await self.setup_config_for_master_command(command=[sys.executable, '-c', 'exit(1)'])

        build = await self.doForceBuild(wantSteps=True, useChange=self.get_change(), wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(build['steps'][1]['state_string'], 'failed (1) (failure)')

    async def test_interrupt(self):
        await self.setup_config_for_master_command(
            name='sleep', command=[sys.executable, '-c', "while True: pass"]
        )

        d = self.doForceBuild(wantSteps=True, useChange=self.get_change(), wantLogs=True)

        async def on_new_step(_, data):
            if data['name'] == 'sleep':
                # wait until the step really starts
                await asyncSleep(1)
                brs = await self.master.data.get(('buildrequests',))
                brid = brs[-1]['buildrequestid']
                self.master.data.control(
                    'cancel', {'reason': 'cancelled by test'}, ('buildrequests', brid)
                )

        await self.master.mq.startConsuming(on_new_step, ('steps', None, 'new'))

        build = await d
        self.assertEqual(build['buildid'], 1)
        if sys.platform == 'win32':
            self.assertEqual(build['steps'][1]['state_string'], 'failed (1) (exception)')
        else:
            self.assertEqual(build['steps'][1]['state_string'], 'killed (9) (exception)')
