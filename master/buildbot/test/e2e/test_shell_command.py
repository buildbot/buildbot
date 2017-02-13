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

from buildbot.test.e2e.base import DaemonMixin
from buildbot.test.e2e.base import E2ETestBase
from buildbot.test.e2e.base import buildbot_worker_executable
from buildbot.test.e2e.base import buildbot_worker_py3_executable
from buildbot.test.e2e.base import buildslave_executable
from buildbot.test.e2e.base import wait_for_completion
from buildbot.test.util.decorators import skipIf
from buildbot.test.util.decorators import skipUnlessPlatformIs


SHELL_COMMAND_TEST_CONFIG = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['buildbotNetUsageData'] = None

c['workers'] = [worker.Worker('example-worker', 'pass')]
c['protocols'] = {'pb': {'port': 9989}}
c['schedulers'] = [
    schedulers.ForceScheduler(
        name='force',
        builderNames=['runtests'])
]

factory = util.BuildFactory(
    [steps.ShellCommand(command=['echo', "Test echo"])])

c['builders'] = [
    util.BuilderConfig(name='runtests', workernames=['example-worker'],
        factory=factory),
]

c['buildbotURL'] = 'http://localhost:8010/'
c['www'] = dict(port=8010, plugins={})
c['db'] = {
    'db_url' : 'sqlite:///state.sqlite',
}
"""


WORKER_SLAVE_TEST_CONFIG = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['buildbotNetUsageData'] = None

c['workers'] = [
    # worker.Worker and buildslave.BuildSlave are synonims, there is no actual
    # need to use worker.Worker for buildbot-worker instances and
    # buildslave.BuildSlave for deprecated buildslave instances.
    worker.Worker('example-worker', 'pass'),
    buildslave.BuildSlave('example-slave', 'pass'),
]
c['protocols'] = {'pb': {'port': 9989}}
c['schedulers'] = [
    schedulers.ForceScheduler(
        name='worker-force',
        builderNames=['worker-builder']),
    schedulers.ForceScheduler(
        name='slave-force',
        builderNames=['slave-builder']),
]

worker_factory = util.BuildFactory(
    [steps.ShellCommand(command=['echo', "Test worker"])])
slave_factory = util.BuildFactory(
    [steps.ShellCommand(command=['echo', "Test slave"])])

c['builders'] = [
    util.BuilderConfig(name='worker-builder', workernames=['example-worker'],
        factory=worker_factory),
    util.BuilderConfig(name='slave-builder', workernames=['example-slave'],
        factory=slave_factory),
]

c['buildbotURL'] = 'http://localhost:8010/'
c['www'] = dict(port=8010, plugins={})
c['db'] = {
    'db_url' : 'sqlite:///state.sqlite',
}
"""


class ShellCommandTestMixin:

    @defer.inlineCallbacks
    def run_check(self):
        # Get builder ID.
        # TODO: maybe add endpoint to get builder by name?
        builders = yield self._get('builders')
        self.assertEqual(len(builders['builders']), 1)
        builder_id = builders['builders'][0]['builderid']

        # Start force build.
        # TODO: return result is not documented in RAML.
        buildset_id, buildrequests_ids = yield self._call_rpc(
            'forceschedulers/force', 'force', builderid=builder_id)

        @defer.inlineCallbacks
        def is_completed():
            # Query buildset completion status.
            buildsets = yield self._get('buildsets/{0}'.format(buildset_id))
            defer.returnValue(buildsets['buildsets'][0]['complete'])

        yield wait_for_completion(is_completed)

        # TODO: Looks like there is no easy way to get build identifier that
        # corresponds to buildrequest/buildset.
        buildnumber = 1

        # Get completed build info.
        builds = yield self._get(
            'builders/{builderid}/builds/{buildnumber}'.format(
                builderid=builder_id, buildnumber=buildnumber))

        self.assertEqual(builds['builds'][0]['state_string'], 'finished')

        log_row = yield self._get_raw(
            'builders/{builderid}/builds/{buildnumber}/steps/0/logs/stdio/raw'.format(
                builderid=builder_id, buildnumber=buildnumber))
        self.assertIn("echo 'Test echo'", log_row)


class ShellCommandOnWorkerNoDaemonTest(E2ETestBase, ShellCommandTestMixin):

    @defer.inlineCallbacks
    def check_shell_command_on_worker(
            self,
            master_executable=None,
            worker_executable=None):
        """Run simple ShellCommand on worker."""

        yield self.setupEnvironment({
            'masters': [
                ('master-dir', SHELL_COMMAND_TEST_CONFIG, master_executable),
            ],
            'workers': [
                ('worker-dir', 'example-worker', 'pass', worker_executable),
            ],
        })

        yield self.run_check()

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    def test_shell_command_on_worker(self):
        yield self.check_shell_command_on_worker()


@skipUnlessPlatformIs('posix')
class ShellCommandOnWorkerDaemonTest(
        ShellCommandOnWorkerNoDaemonTest, DaemonMixin):
    pass


class ShellCommandOnSlaveNoDaemonTest(E2ETestBase, ShellCommandTestMixin):

    @defer.inlineCallbacks
    def check_shell_command_on_slave(
            self,
            master_executable=None,
            slave_executable=None):
        """Run simple ShellCommand on slave."""

        yield self.setupEnvironment({
            'masters': [
                ('master-dir', SHELL_COMMAND_TEST_CONFIG, master_executable),
            ],
            'slaves': [
                ('worker-dir', 'example-worker', 'pass', slave_executable),
            ],
        })

        yield self.run_check()

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_shell_command_on__slave(self):
        yield self.check_shell_command_on_slave()


@skipUnlessPlatformIs('posix')
class ShellCommandOnSlaveDaemonTest(
        ShellCommandOnSlaveNoDaemonTest, DaemonMixin):
    pass


class ShellCommandOnWorkerAndSlaveNoDaemonTest(E2ETestBase):

    @defer.inlineCallbacks
    def check_shell_command_on_worker_and_slave(
            self,
            master_executable=None,
            worker_executable=None,
            slave_executable=None):

        yield self.setupEnvironment({
            'masters': [
                ('master-dir', WORKER_SLAVE_TEST_CONFIG, master_executable),
            ],
            'workers': [
                ('worker-dir', 'example-worker', 'pass', worker_executable),
            ],
            'slaves': [
                ('slave-dir', 'example-slave', 'pass', slave_executable),
            ]
        })

        # Get builder ID.
        # TODO: maybe add endpoint to get builder by name?
        builders = yield self._get('builders')
        self.assertEqual(len(builders['builders']), 2)

        if builders['builders'][0]['name'] == 'worker-builder':
            worker_idx = 0
            slave_idx = 1
        else:
            worker_idx = 1
            slave_idx = 0

        worker_builder_id = builders['builders'][worker_idx]['builderid']
        slave_builder_id = builders['builders'][slave_idx]['builderid']

        # Start worker force build.
        worker_buildset_id, worker_buildrequests_ids = yield self._call_rpc(
            'forceschedulers/worker-force', 'force',
            builderid=worker_builder_id)

        # Start slave force build.
        slave_buildset_id, slave_buildrequests_ids = yield self._call_rpc(
            'forceschedulers/slave-force', 'force',
            builderid=slave_builder_id)

        @defer.inlineCallbacks
        def is_builds_completed():
            # Query buildset completion status.
            worker_buildsets = yield self._get(
                'buildsets/{0}'.format(worker_buildset_id))
            slave_buildsets = yield self._get(
                'buildsets/{0}'.format(slave_buildset_id))

            worker_complete = worker_buildsets['buildsets'][0]['complete']
            slave_complete = slave_buildsets['buildsets'][0]['complete']

            defer.returnValue(worker_complete and slave_complete)

        yield wait_for_completion(is_builds_completed)

        # TODO: Looks like there is no easy way to get build identifier that
        # corresponds to buildrequest/buildset.
        buildnumber = 1

        # Get worker completed build info.
        worker_builds = yield self._get(
            'builders/{builderid}/builds/{buildnumber}'.format(
                builderid=worker_builder_id, buildnumber=buildnumber))

        self.assertEqual(
            worker_builds['builds'][0]['state_string'], 'finished')

        log_row = yield self._get_raw(
            'builders/{builderid}/builds/{buildnumber}/'
            'steps/0/logs/stdio/raw'.format(
                builderid=worker_builder_id, buildnumber=buildnumber))
        self.assertIn("echo 'Test worker'", log_row)

        # Get slave completed build info.
        slave_builds = yield self._get(
            'builders/{builderid}/builds/{buildnumber}'.format(
                builderid=slave_builder_id, buildnumber=buildnumber))

        self.assertEqual(
            slave_builds['builds'][0]['state_string'], 'finished')

        log_row = yield self._get_raw(
            'builders/{builderid}/builds/{buildnumber}/'
            'steps/0/logs/stdio/raw'.format(
                builderid=slave_builder_id, buildnumber=buildnumber))
        self.assertIn("echo 'Test slave'", log_row)

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_shell_command_on_worker_and_slave(self):
        yield self.check_shell_command_on_worker_and_slave()

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_py3_executable is None,
            "buildbot-worker on Python 3 is not specified")
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_shell_command_on_worker_py3_and_slave(self):
        yield self.check_shell_command_on_worker_and_slave(
            buildbot_worker_executable=buildbot_worker_py3_executable)


@skipUnlessPlatformIs('posix')
class ShellCommandOnWorkerAndSlaveDaemonTest(
        ShellCommandOnWorkerAndSlaveNoDaemonTest, DaemonMixin):
    pass
