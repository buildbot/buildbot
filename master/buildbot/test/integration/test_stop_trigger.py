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
from twisted.internet import reactor

from buildbot.config import BuilderConfig
from buildbot.plugins import schedulers
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.process.results import CANCELLED
from buildbot.test.util.integration import RunMasterBase

# This integration test creates a master and slave environment,
# with two builders and a trigger step linking them. the triggered build never ends
# so that we can reliabily stop it recursively


# master configurations
def setupTriggerConfiguration(triggeredFactory, nextBuild=None):
    c = {}

    c['schedulers'] = [
        schedulers.Triggerable(
            name="trigsched",
            builderNames=["triggered"]),
        schedulers.AnyBranchScheduler(
            name="sched",
            builderNames=["main"])]

    f = BuildFactory()
    f.addStep(steps.Trigger(schedulerNames=['trigsched'],
                            waitForFinish=True,
                            updateSourceStamp=True))
    f.addStep(steps.ShellCommand(command='echo world'))

    mainBuilder = BuilderConfig(name="main",
                                slavenames=["local1"],
                                factory=f)

    triggeredBuilderKwargs = {'name': "triggered",
                              'slavenames': ["local1"],
                              'factory': triggeredFactory}

    if nextBuild is not None:
        triggeredBuilderKwargs['nextBuild'] = nextBuild

    triggeredBuilder = BuilderConfig(**triggeredBuilderKwargs)

    c['builders'] = [mainBuilder, triggeredBuilder]
    return c


def triggerRunsForever():
    f2 = BuildFactory()
    f2.addStep(steps.ShellCommand(command="\n".join(['while :',
                                                     'do',
                                                     ' echo "sleeping";',
                                                     ' sleep 1;'
                                                     'done'])))

    return setupTriggerConfiguration(f2)


def triggeredBuildIsNotCreated():
    f2 = BuildFactory()
    f2.addStep(steps.ShellCommand(command="echo 'hello'"))

    def nextBuild(*args, **kwargs):
        return defer.succeed(None)
    return setupTriggerConfiguration(f2, nextBuild=nextBuild)


class TriggeringMaster(RunMasterBase):
    testCasesHandleTheirSetup = True

    change = dict(branch="master",
                  files=["foo.c"],
                  author="me@foo.com",
                  comments="good stuff",
                  revision="HEAD",
                  project="none")

    def assertBuildIsCancelled(self, b):
        self.assertTrue(b['complete'])
        self.assertEquals(b['results'], CANCELLED)

    @defer.inlineCallbacks
    def runTest(self, newBuildCallback):
        newConsumer = yield self.master.mq.startConsuming(
            newBuildCallback,
            ('builds', None, 'new'))
        build = yield self.doForceBuild(wantSteps=True,
                                        useChange=self.change,
                                        wantLogs=True)
        self.assertBuildIsCancelled(build)
        newConsumer.stopConsuming()
        builds = yield self.master.data.get(("builds",))
        for b in builds:
            self.assertBuildIsCancelled(b)

    @defer.inlineCallbacks
    def testTriggerRunsForever(self):
        yield self.setupConfig("triggerRunsForever")
        self.higherBuild = None

        def newCallback(_, data):
            if self.higherBuild is None:
                self.higherBuild = data['buildid']
            else:
                self.master.data.control("stop", {}, ("builds", self.higherBuild))
                self.higherBuild = None
        yield self.runTest(newCallback)

    @defer.inlineCallbacks
    def testTriggerRunsForeverAfterCmdStarted(self):
        yield self.setupConfig("triggerRunsForever")
        self.higherBuild = None

        def newCallback(_, data):
            if self.higherBuild is None:
                self.higherBuild = data['buildid']
            else:

                def f():
                    self.master.data.control("stop", {}, ("builds", self.higherBuild))
                    self.higherBuild = None
                reactor.callLater(5.0, f)

        yield self.runTest(newCallback)

    @defer.inlineCallbacks
    def testTriggeredBuildIsNotCreated(self):
        yield self.setupConfig("triggeredBuildIsNotCreated")

        def newCallback(_, data):
            self.master.data.control("stop", {}, ("builds", data['buildid']))
        yield self.runTest(newCallback)
