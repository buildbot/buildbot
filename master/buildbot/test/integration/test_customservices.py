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

from buildbot.test.util.integration import RunMasterBase
from twisted.internet import defer

# This integration test creates a master and slave environment,
# with one builder and a custom step
# The custom step is using a CustomService, in order to calculate its result
# we make sure that we can reconfigure the master while build is running

observed_num_reconfig = None

class CustomServiceMaster(RunMasterBase):

    @defer.inlineCallbacks
    def test_customService(self):
        global observed_num_reconfig

        observed_num_reconfig = None
        yield self.doForceBuild(wantSteps=True)

        self.assertEqual(observed_num_reconfig, 1)

        myService = self.master.namedServices['myService']
        self.assertEqual(myService.num_reconfig, 1)
        self.assertTrue(myService.running)

        # We do several reconfig, and make sure the service
        # are reconfigured as expected
        yield self.master.reconfig()

        observed_num_reconfig = None
        yield self.doForceBuild(wantSteps=True)

        self.assertEqual(myService.num_reconfig, 2)
        self.assertEqual(observed_num_reconfig, 2)

        yield self.master.reconfig()

        myService2 = self.master.namedServices['myService2']

        self.assertTrue(myService2.running)
        self.assertEqual(myService2.num_reconfig, 3)
        self.assertEqual(myService.num_reconfig, 3)

        yield self.master.reconfig()

        # second service removed
        self.assertNotIn('myService2', self.master.namedServices)
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
    from buildbot.status.results import SUCCESS
    from buildbot.schedulers.forcesched import ForceScheduler
    from buildbot.process.buildstep import BuildStep
    from buildbot.util.service import BuildbotService

    class MyShellCommand(BuildStep):

        def run(self):
            service = self.master.namedServices['myService']
            global observed_num_reconfig
            observed_num_reconfig = service.num_reconfig
            return SUCCESS

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
    f.addStep(MyShellCommand())
    c['builders'] = [
        BuilderConfig(name="testy",
                      slavenames=["local1"],
                      factory=f)]

    c['services'] = [MyService(num_reconfig=num_reconfig)]
    if num_reconfig == 3:
        c['services'].append(MyService(name="myService2", num_reconfig=num_reconfig))
    return c
