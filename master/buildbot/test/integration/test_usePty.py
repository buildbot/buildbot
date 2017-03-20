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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer

from buildbot.test.util.decorators import skipUnlessPlatformIs
from buildbot.test.util.integration import RunMasterBase


# This integration test creates a master and worker environment,
# with one builder and a shellcommand step, which use usePTY
class ShellMaster(RunMasterBase):

    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_usePTY(self):
        yield self.setupConfig(masterConfig(usePTY=True))

        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        res = yield self.checkBuildStepLogExist(build, "in a terminal", onlyStdout=True)
        self.assertTrue(res)

    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_NOusePTY(self):
        yield self.setupConfig(masterConfig(usePTY=False))

        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        res = yield self.checkBuildStepLogExist(build, "not a terminal", onlyStdout=True)
        self.assertTrue(res)


# master configuration
def masterConfig(usePTY):
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]

    f = BuildFactory()
    f.addStep(steps.ShellCommand(
        command='if [ -t 1 ] ; then echo in a terminal; else echo "not a terminal"; fi',
        usePTY=usePTY))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
