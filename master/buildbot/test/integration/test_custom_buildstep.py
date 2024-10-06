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
from twisted.internet import error

from buildbot.config import BuilderConfig
from buildbot.process import buildstep
from buildbot.process import logobserver
from buildbot.process import results
from buildbot.process.factory import BuildFactory
from buildbot.process.project import Project
from buildbot.test.util.integration import RunFakeMasterTestCase


class TestLogObserver(logobserver.LogObserver):
    def __init__(self):
        self.observed = []

    def outReceived(self, data):
        self.observed.append(data)


class Latin1ProducingCustomBuildStep(buildstep.BuildStep):
    async def run(self):
        _log = await self.addLog('xx')
        output_str = '\N{CENT SIGN}'
        await _log.addStdout(output_str)
        await _log.finish()
        return results.SUCCESS


class BuildStepWithFailingLogObserver(buildstep.BuildStep):
    async def run(self):
        self.addLogObserver('xx', logobserver.LineConsumerLogObserver(self.log_consumer))

        _log = await self.addLog('xx')
        await _log.addStdout('line1\nline2\n')
        await _log.finish()

        return results.SUCCESS

    def log_consumer(self):
        _, _ = yield
        raise RuntimeError('fail')


class SucceedingCustomStep(buildstep.BuildStep):
    flunkOnFailure = True

    def run(self):
        return defer.succeed(results.SUCCESS)


class FailingCustomStep(buildstep.BuildStep):
    flunkOnFailure = True

    def __init__(self, exception=buildstep.BuildStepFailed, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = exception

    async def run(self):
        await defer.succeed(None)
        raise self.exception()


class RunSteps(RunFakeMasterTestCase):
    async def create_config_for_step(self, step):
        config_dict = {
            'builders': [
                BuilderConfig(
                    name="builder", workernames=["worker1"], factory=BuildFactory([step])
                ),
            ],
            'workers': [self.createLocalWorker('worker1')],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }

        await self.setup_master(config_dict)
        builder_id = await self.master.data.updates.findBuilderId('builder')
        return builder_id

    async def create_config_for_step_project(self, step):
        config_dict = {
            'builders': [
                BuilderConfig(
                    name="builder",
                    workernames=["worker1"],
                    factory=BuildFactory([step]),
                    project='project1',
                ),
            ],
            'workers': [self.createLocalWorker('worker1')],
            'projects': [Project(name='project1')],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }

        await self.setup_master(config_dict)
        builder_id = await self.master.data.updates.findBuilderId('builder')
        return builder_id

    async def test_step_raising_buildstepfailed_in_start(self):
        builder_id = await self.create_config_for_step(FailingCustomStep())

        await self.do_test_build(builder_id)
        await self.assertBuildResults(1, results.FAILURE)

    async def test_step_raising_exception_in_start(self):
        builder_id = await self.create_config_for_step(FailingCustomStep(exception=ValueError))

        await self.do_test_build(builder_id)
        await self.assertBuildResults(1, results.EXCEPTION)
        self.assertEqual(len(self.flushLoggedErrors(ValueError)), 1)

    async def test_step_raising_connectionlost_in_start(self):
        """Check whether we can recover from raising ConnectionLost from a step if the worker
        did not actually disconnect
        """
        step = FailingCustomStep(exception=error.ConnectionLost)
        builder_id = await self.create_config_for_step(step)

        await self.do_test_build(builder_id)
        await self.assertBuildResults(1, results.EXCEPTION)

    test_step_raising_connectionlost_in_start.skip = "Results in infinite loop"

    async def test_step_raising_in_log_observer(self):
        step = BuildStepWithFailingLogObserver()
        builder_id = await self.create_config_for_step(step)

        await self.do_test_build(builder_id)
        await self.assertBuildResults(1, results.EXCEPTION)
        await self.assertStepStateString(2, "finished (exception)")
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    async def test_Latin1ProducingCustomBuildStep(self):
        step = Latin1ProducingCustomBuildStep(logEncoding='latin-1')
        builder_id = await self.create_config_for_step(step)

        await self.do_test_build(builder_id)
        await self.assertLogs(
            1,
            {
                'xx': 'o\N{CENT SIGN}\n',
            },
        )

    def _check_and_pop_dynamic_properties(self, properties):
        for property in ('builddir', 'basedir'):
            self.assertIn(property, properties)
            properties.pop(property)

    async def test_all_properties(self):
        builder_id = await self.create_config_for_step(SucceedingCustomStep())

        await self.do_test_build(builder_id)

        properties = await self.master.data.get(("builds", 1, "properties"))
        self._check_and_pop_dynamic_properties(properties)

        self.assertEqual(
            properties,
            {
                "buildername": ("builder", "Builder"),
                "builderid": (1, "Builder"),
                "workername": ("worker1", "Worker"),
                "buildnumber": (1, "Build"),
                "branch": (None, "Build"),
                "revision": (None, "Build"),
                "repository": ("", "Build"),
                "codebase": ("", "Build"),
                "project": ("", "Build"),
            },
        )

    async def test_all_properties_project(self):
        builder_id = await self.create_config_for_step_project(SucceedingCustomStep())

        await self.do_test_build(builder_id)

        properties = await self.master.data.get(('builds', 1, 'properties'))
        self._check_and_pop_dynamic_properties(properties)

        self.assertEqual(
            properties,
            {
                'buildername': ('builder', 'Builder'),
                'builderid': (1, 'Builder'),
                'workername': ('worker1', 'Worker'),
                'buildnumber': (1, 'Build'),
                'branch': (None, 'Build'),
                'projectid': (1, 'Builder'),
                'projectname': ('project1', 'Builder'),
                'revision': (None, 'Build'),
                'repository': ('', 'Build'),
                'codebase': ('', 'Build'),
                'project': ('', 'Build'),
            },
        )
