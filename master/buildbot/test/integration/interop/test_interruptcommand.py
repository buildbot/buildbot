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


from twisted.internet import defer

from buildbot.process.results import CANCELLED
from buildbot.test.util.decorators import flaky
from buildbot.test.util.integration import RunMasterBase
from buildbot.util import asyncSleep


class InterruptCommand(RunMasterBase):
    """Make sure we can interrupt a command"""

    @defer.inlineCallbacks
    def setup_config(self):
        c = {}
        from buildbot.plugins import schedulers
        from buildbot.plugins import steps
        from buildbot.plugins import util

        class SleepAndInterrupt(steps.ShellSequence):
            @defer.inlineCallbacks
            def run(self):
                if self.worker.worker_system == "nt":
                    sleep = "waitfor SomethingThatIsNeverHappening /t 100 >nul 2>&1"
                else:
                    sleep = ["sleep", "100"]
                d = self.runShellSequence([util.ShellArg(sleep)])
                yield asyncSleep(1)
                self.interrupt("just testing")
                res = yield d
                return res

        c['schedulers'] = [schedulers.ForceScheduler(name="force", builderNames=["testy"])]

        f = util.BuildFactory()
        f.addStep(SleepAndInterrupt())
        c['builders'] = [util.BuilderConfig(name="testy", workernames=["local1"], factory=f)]

        yield self.setup_master(c)

    @flaky(bugNumber=4404, onPlatform='win32')
    @defer.inlineCallbacks
    def test_interrupt(self):
        yield self.setup_config()
        build = yield self.doForceBuild(wantSteps=True)
        self.assertEqual(build['steps'][-1]['results'], CANCELLED)


class InterruptCommandPb(InterruptCommand):
    proto = "pb"


class InterruptCommandMsgPack(InterruptCommand):
    proto = "msgpack"
