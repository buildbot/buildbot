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


from twisted.internet import reactor
from twisted.internet import task

from buildbot.test.util.integration import RunMasterBase


# This integration test helps reproduce http://trac.buildbot.net/ticket/3024
# we make sure that we can reconfigure the master while build is running
class SetPropertyFromCommand(RunMasterBase):
    async def setup_config(self):
        c = {}
        from buildbot.plugins import schedulers
        from buildbot.plugins import steps
        from buildbot.plugins import util

        c['schedulers'] = [schedulers.ForceScheduler(name="force", builderNames=["testy"])]

        f = util.BuildFactory()
        f.addStep(steps.SetPropertyFromCommand(property="test", command=["echo", "foo"]))
        c['builders'] = [util.BuilderConfig(name="testy", workernames=["local1"], factory=f)]

        await self.setup_master(c)

    async def test_setProp(self):
        await self.setup_config()
        oldNewLog = self.master.data.updates.addLog

        async def newLog(*arg, **kw):
            # Simulate db delay. We usually don't test race conditions
            # with delays, but in integrations test, that would be pretty
            # tricky
            await task.deferLater(reactor, 0.1, lambda: None)
            res = await oldNewLog(*arg, **kw)
            return res

        self.master.data.updates.addLog = newLog
        build = await self.doForceBuild(wantProperties=True)

        self.assertEqual(build['properties']['test'], ('foo', 'SetPropertyFromCommand Step'))


class SetPropertyFromCommandPB(SetPropertyFromCommand):
    proto = "pb"


class SetPropertyFromCommandMsgPack(SetPropertyFromCommand):
    proto = "msgpack"
