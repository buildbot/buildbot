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
    @defer.inlineCallbacks
    def run(self):
        _log = yield self.addLog('xx')
        output_str = '\N{CENT SIGN}'
        yield _log.addStdout(output_str)
        yield _log.finish()
        return results.SUCCESS


class BuildStepWithFailingLogObserver(buildstep.BuildStep):
    @defer.inlineCallbacks
    def run(self):
        self.addLogObserver('xx', logobserver.LineConsumerLogObserver(self.log_consumer))

        _log = yield self.addLog('xx')
        yield _log.addStdout('line1\nline2\n')
        yield _log.finish()

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

    @defer.inlineCallbacks
    def run(self):
        yield defer.succeed(None)
        raise self.exception()


class RunSteps(RunFakeMasterTestCase):
    @defer.inlineCallbacks
    def create_config_for_step(self, step, builder_kwargs=None):
        config_dict = {
            'builders': [
                BuilderConfig(
                    name="builder",
                    workernames=["worker1"],
                    factory=BuildFactory([step]),
                    **(builder_kwargs or {}),
                ),
            ],
            'workers': [self.createLocalWorker('worker1')],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }

        yield self.setup_master(config_dict)
        builder_id = yield self.master.data.updates.findBuilderId('builder')
        return builder_id

    @defer.inlineCallbacks
    def create_config_for_step_project(self, step):
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

        yield self.setup_master(config_dict)
        builder_id = yield self.master.data.updates.findBuilderId('builder')
        return builder_id

    @defer.inlineCallbacks
    def test_step_raising_buildstepfailed_in_start(self):
        builder_id = yield self.create_config_for_step(FailingCustomStep())

        yield self.do_test_build(builder_id)
        yield self.assertBuildResults(1, results.FAILURE)

    @defer.inlineCallbacks
    def test_step_raising_exception_in_start(self):
        builder_id = yield self.create_config_for_step(FailingCustomStep(exception=ValueError))

        yield self.do_test_build(builder_id)
        yield self.assertBuildResults(1, results.EXCEPTION)
        self.assertEqual(len(self.flushLoggedErrors(ValueError)), 1)

    @defer.inlineCallbacks
    def test_step_raising_connectionlost_in_start(self):
        """Check whether we can recover from raising ConnectionLost from a step if the worker
        did not actually disconnect
        """
        step = FailingCustomStep(exception=error.ConnectionLost)
        builder_id = yield self.create_config_for_step(step)

        yield self.do_test_build(builder_id)
        yield self.assertBuildResults(1, results.EXCEPTION)

    test_step_raising_connectionlost_in_start.skip = "Results in infinite loop"  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_step_raising_in_log_observer(self):
        step = BuildStepWithFailingLogObserver()
        builder_id = yield self.create_config_for_step(step)

        yield self.do_test_build(builder_id)
        yield self.assertBuildResults(1, results.EXCEPTION)
        yield self.assertStepStateString(2, "finished (exception)")
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def test_Latin1ProducingCustomBuildStep(self):
        step = Latin1ProducingCustomBuildStep(logEncoding='latin-1')
        builder_id = yield self.create_config_for_step(step)

        yield self.do_test_build(builder_id)
        yield self.assertLogs(
            1,
            {
                'xx': 'o\N{CENT SIGN}\n',
            },
        )

    def _check_and_pop_dynamic_properties(self, properties):
        for property in ('builddir', 'basedir'):
            self.assertIn(property, properties)
            properties.pop(property)

    @defer.inlineCallbacks
    def test_all_properties(self):
        builder_id = yield self.create_config_for_step(SucceedingCustomStep())

        yield self.do_test_build(builder_id)

        properties = yield self.master.data.get(("builds", 1, "properties"))
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

    @defer.inlineCallbacks
    def test_all_properties_project(self):
        builder_id = yield self.create_config_for_step_project(SucceedingCustomStep())

        yield self.do_test_build(builder_id)

        properties = yield self.master.data.get(('builds', 1, 'properties'))
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

    @defer.inlineCallbacks
    def test_build_being_skipped_in_start(self):
        builder_id = yield self.create_config_for_step(
            SucceedingCustomStep(), builder_kwargs={"do_build_if": lambda x: False}
        )

        yield self.do_test_build(builder_id)
        yield self.assertBuildResults(1, results.SKIPPED)
