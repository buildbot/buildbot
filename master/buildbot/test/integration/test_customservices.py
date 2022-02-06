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

from buildbot.test.util.integration import RunFakeMasterTestCase

# This integration test creates a master and worker environment,
# with one builder and a custom step
# The custom step is using a CustomService, in order to calculate its result
# we make sure that we can reconfigure the master while build is running


class CustomServiceMaster(RunFakeMasterTestCase):

    def setUp(self):
        super().setUp()
        self.num_reconfig = 0

    def create_master_config(self):
        self.num_reconfig += 1
        from buildbot.config import BuilderConfig
        from buildbot.process.factory import BuildFactory
        from buildbot.steps.shell import ShellCommand
        from buildbot.util.service import BuildbotService

        class MyShellCommand(ShellCommand):

            def getResultSummary(self):
                service = self.master.service_manager.namedServices['myService']
                return dict(step=f"num reconfig: {service.num_reconfig}")

        class MyService(BuildbotService):
            name = "myService"

            def reconfigService(self, num_reconfig):
                self.num_reconfig = num_reconfig
                return defer.succeed(None)

        config_dict = {
            'builders': [
                BuilderConfig(name="builder", workernames=["worker1"],
                              factory=BuildFactory([MyShellCommand(command='echo hei')])),
            ],
            'workers': [self.createLocalWorker('worker1')],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
            'db_url': 'sqlite://',  # we need to make sure reconfiguration uses the same URL
            'services': [MyService(num_reconfig=self.num_reconfig)]
        }

        if self.num_reconfig == 3:
            config_dict['services'].append(MyService(name="myService2",
                                                     num_reconfig=self.num_reconfig))
        return config_dict

    @defer.inlineCallbacks
    def test_custom_service(self):
        yield self.setup_master(self.create_master_config())

        yield self.do_test_build_by_name('builder')

        self.assertStepStateString(1, 'worker worker1 ready')
        self.assertStepStateString(2, 'num reconfig: 1')

        myService = self.master.service_manager.namedServices['myService']
        self.assertEqual(myService.num_reconfig, 1)
        self.assertTrue(myService.running)

        # We do several reconfig, and make sure the service
        # are reconfigured as expected
        yield self.reconfig_master(self.create_master_config())

        yield self.do_test_build_by_name('builder')

        self.assertEqual(myService.num_reconfig, 2)
        self.assertStepStateString(1, 'worker worker1 ready')
        self.assertStepStateString(2, 'num reconfig: 1')

        yield self.reconfig_master(self.create_master_config())

        myService2 = self.master.service_manager.namedServices['myService2']

        self.assertTrue(myService2.running)
        self.assertEqual(myService2.num_reconfig, 3)
        self.assertEqual(myService.num_reconfig, 3)

        yield self.reconfig_master(self.create_master_config())

        # second service removed
        self.assertNotIn('myService2', self.master.service_manager.namedServices)
        self.assertFalse(myService2.running)
        self.assertEqual(myService2.num_reconfig, 3)
        self.assertEqual(myService.num_reconfig, 4)
