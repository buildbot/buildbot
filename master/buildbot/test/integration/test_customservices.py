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

from buildbot.test.util.decorators import flaky
from buildbot.test.util.integration import RunMasterBase

# This integration test creates a master and worker environment,
# with one builder and a custom step
# The custom step is using a CustomService, in order to calculate its result
# we make sure that we can reconfigure the master while build is running


class CustomServiceMaster(RunMasterBase):

    @flaky(bugNumber=3340)
    @defer.inlineCallbacks
    def test_customService(self):
        yield self.setupConfig(masterConfig())

        build = yield self.doForceBuild(wantSteps=True)

        self.assertEqual(build['steps'][0]['state_string'], 'num reconfig: 1')

        myService = self.master.service_manager.namedServices['myService']
        self.assertEqual(myService.num_reconfig, 1)
        self.assertTrue(myService.running)

        # We do several reconfig, and make sure the service
        # are reconfigured as expected
        yield self.master.reconfig()

        build = yield self.doForceBuild(wantSteps=True)

        self.assertEqual(myService.num_reconfig, 2)
        self.assertEqual(build['steps'][0]['state_string'], 'num reconfig: 2')

        yield self.master.reconfig()

        myService2 = self.master.service_manager.namedServices['myService2']

        self.assertTrue(myService2.running)
        self.assertEqual(myService2.num_reconfig, 3)
        self.assertEqual(myService.num_reconfig, 3)

        yield self.master.reconfig()

        # second service removed
        self.assertNotIn(
            'myService2', self.master.service_manager.namedServices)
        self.assertFalse(myService2.running)
        self.assertEqual(myService2.num_reconfig, 3)
        self.assertEqual(myService.num_reconfig, 4)


# master configuration

num_reconfig = 0


def masterConfig():
    global num_reconfig
    num_reconfig += 1
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.schedulers.forcesched import ForceScheduler
    from buildbot.steps.shell import ShellCommand
    from buildbot.util.service import BuildbotService

    class MyShellCommand(ShellCommand):

        def getResultSummary(self):
            service = self.master.service_manager.namedServices['myService']
            return dict(step=u"num reconfig: %d" % (service.num_reconfig,))

    class MyService(BuildbotService):
        name = "myService"

        def reconfigService(self, num_reconfig):
            self.num_reconfig = num_reconfig
            return defer.succeed(None)

    c['schedulers'] = [
        ForceScheduler(
            name="force",
            builderNames=["testy"])]

    f = BuildFactory()
    f.addStep(MyShellCommand(command='echo hei'))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]

    c['services'] = [MyService(num_reconfig=num_reconfig)]
    if num_reconfig == 3:
        c['services'].append(
            MyService(name="myService2", num_reconfig=num_reconfig))
    return c
