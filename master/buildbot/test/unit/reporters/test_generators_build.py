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


import copy

from parameterized import parameterized

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.notifier import NotifierTestMixin


class TestBuildGenerator(ConfigErrorsMixin, TestReactorMixin,
                         unittest.TestCase, NotifierTestMixin):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    @parameterized.expand([
        ('tags', 'tag'),
        ('tags', 1),
        ('builders', 'builder'),
        ('builders', 1),
        ('schedulers', 'scheduler'),
        ('schedulers', 1),
        ('branches', 'branch'),
        ('branches', 1),
    ])
    def test_list_params_check_raises(self, arg_name, arg_value):
        kwargs = {arg_name: arg_value}
        g = BuildStatusGenerator(**kwargs)
        with self.assertRaisesConfigError('must be a list or None'):
            g.check()

    def test_subject_newlines_not_allowed(self):
        g = BuildStatusGenerator(subject='subject\nwith\nnewline')
        with self.assertRaisesConfigError('Newlines are not allowed'):
            g.check()

    @defer.inlineCallbacks
    def test_is_message_needed_ignores_unspecified_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        build['builder']['tags'] = ['slow']
        g = BuildStatusGenerator(tags=["fast"])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        build['builder']['tags'] = ['fast']
        g = BuildStatusGenerator(tags=["fast"])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_schedulers_sends_mail(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        g = BuildStatusGenerator(schedulers=['checkin'])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_schedulers_doesnt_send_mail(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        g = BuildStatusGenerator(schedulers=['some-random-scheduler'])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_branches_sends_mail(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        g = BuildStatusGenerator(branches=['master'])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_branches_doesnt_send_mail(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        g = BuildStatusGenerator(branches=['some-random-branch'])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def run_simple_test_sends_message_for_mode(self, mode, result, should_send=True):
        _, builds = yield self.setupBuildResults(result)

        g = BuildStatusGenerator(mode=mode)

        self.assertEqual(g.is_message_needed_by_results(builds[0]), should_send)

    def run_simple_test_ignores_message_for_mode(self, mode, result):
        return self.run_simple_test_sends_message_for_mode(mode, result, False)

    def test_is_message_needed_mode_all_for_success(self):
        return self.run_simple_test_sends_message_for_mode("all", SUCCESS)

    def test_is_message_needed_mode_all_for_failure(self):
        return self.run_simple_test_sends_message_for_mode("all", FAILURE)

    def test_is_message_needed_mode_all_for_warnings(self):
        return self.run_simple_test_sends_message_for_mode("all", WARNINGS)

    def test_is_message_needed_mode_all_for_exception(self):
        return self.run_simple_test_sends_message_for_mode("all", EXCEPTION)

    def test_is_message_needed_mode_all_for_cancelled(self):
        return self.run_simple_test_sends_message_for_mode("all", CANCELLED)

    def test_is_message_needed_mode_failing_for_success(self):
        return self.run_simple_test_ignores_message_for_mode("failing", SUCCESS)

    def test_is_message_needed_mode_failing_for_failure(self):
        return self.run_simple_test_sends_message_for_mode("failing", FAILURE)

    def test_is_message_needed_mode_failing_for_warnings(self):
        return self.run_simple_test_ignores_message_for_mode("failing", WARNINGS)

    def test_is_message_needed_mode_failing_for_exception(self):
        return self.run_simple_test_ignores_message_for_mode("failing", EXCEPTION)

    def test_is_message_needed_mode_exception_for_success(self):
        return self.run_simple_test_ignores_message_for_mode("exception", SUCCESS)

    def test_is_message_needed_mode_exception_for_failure(self):
        return self.run_simple_test_ignores_message_for_mode("exception", FAILURE)

    def test_is_message_needed_mode_exception_for_warnings(self):
        return self.run_simple_test_ignores_message_for_mode("exception", WARNINGS)

    def test_is_message_needed_mode_exception_for_exception(self):
        return self.run_simple_test_sends_message_for_mode("exception", EXCEPTION)

    def test_is_message_needed_mode_warnings_for_success(self):
        return self.run_simple_test_ignores_message_for_mode("warnings", SUCCESS)

    def test_is_message_needed_mode_warnings_for_failure(self):
        return self.run_simple_test_sends_message_for_mode("warnings", FAILURE)

    def test_is_message_needed_mode_warnings_for_warnings(self):
        return self.run_simple_test_sends_message_for_mode("warnings", WARNINGS)

    def test_is_message_needed_mode_warnings_for_exception(self):
        return self.run_simple_test_ignores_message_for_mode("warnings", EXCEPTION)

    def test_is_message_needed_mode_passing_for_success(self):
        return self.run_simple_test_sends_message_for_mode("passing", SUCCESS)

    def test_is_message_needed_mode_passing_for_failure(self):
        return self.run_simple_test_ignores_message_for_mode("passing", FAILURE)

    def test_is_message_needed_mode_passing_for_warnings(self):
        return self.run_simple_test_ignores_message_for_mode("passing", WARNINGS)

    def test_is_message_needed_mode_passing_for_exception(self):
        return self.run_simple_test_ignores_message_for_mode("passing", EXCEPTION)

    @defer.inlineCallbacks
    def run_sends_message_for_problems(self, mode, results1, results2, should_send=True):
        _, builds = yield self.setupBuildResults(results2)

        g = BuildStatusGenerator(mode=mode)

        build = builds[0]
        if results1 is not None:
            build['prev_build'] = copy.deepcopy(builds[0])
            build['prev_build']['results'] = results1
        else:
            build['prev_build'] = None
        self.assertEqual(g.is_message_needed_by_results(builds[0]), should_send)

    def test_is_message_needed_mode_problem_sends_on_problem(self):
        return self.run_sends_message_for_problems("problem", SUCCESS, FAILURE, True)

    def test_is_message_needed_mode_problem_ignores_successful_build(self):
        return self.run_sends_message_for_problems("problem", SUCCESS, SUCCESS, False)

    def test_is_message_needed_mode_problem_ignores_two_failed_builds_in_sequence(self):
        return self.run_sends_message_for_problems("problem", FAILURE, FAILURE, False)

    def test_is_message_needed_mode_change_sends_on_change(self):
        return self.run_sends_message_for_problems("change", FAILURE, SUCCESS, True)

    def test_is_message_needed_mode_change_sends_on_failure(self):
        return self.run_sends_message_for_problems("change", SUCCESS, FAILURE, True)

    def test_is_message_needed_mode_change_ignores_first_build(self):
        return self.run_sends_message_for_problems("change", None, FAILURE, False)

    def test_is_message_needed_mode_change_ignores_first_build2(self):
        return self.run_sends_message_for_problems("change", None, SUCCESS, False)

    def test_is_message_needed_mode_change_ignores_same_result_in_sequence(self):
        return self.run_sends_message_for_problems("change", SUCCESS, SUCCESS, False)

    def test_is_message_needed_mode_change_ignores_same_result_in_sequence2(self):
        return self.run_sends_message_for_problems("change", FAILURE, FAILURE, False)

    @defer.inlineCallbacks
    def setup_generator(self, results=SUCCESS, message=None, **kwargs):
        if message is None:
            message = {
                "body": "body",
                "type": "text",
                "subject": "subject"
            }

        _, builds = yield self.setupBuildResults(results)

        g = BuildStatusGenerator(**kwargs)

        g.formatter = Mock(spec=g.formatter)
        g.formatter.format_message_for_build.return_value = message

        return (g, builds)

    @defer.inlineCallbacks
    def build_message(self, g, builds, results=SUCCESS):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.build_message(self.master, reporter, "mybldr", builds, results)
        return report

    @defer.inlineCallbacks
    def generate(self, g, key, build):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.generate(self.master, reporter, key, build)
        return report

    @defer.inlineCallbacks
    def test_build_message_nominal(self):
        g, builds = yield self.setup_generator(mode=("change",))
        report = yield self.build_message(g, builds)

        build = builds[0]
        g.formatter.format_message_for_build.assert_called_with(
            ('change',), 'mybldr', build['buildset'], build, self.master, None, [])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'mybldr',
            'results': SUCCESS,
            'builds': builds,
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_no_result(self):
        g, builds = yield self.setup_generator(results=None, mode=("change",))
        report = yield self.build_message(g, builds, results=None)

        build = builds[0]
        g.formatter.format_message_for_build.assert_called_with(
            ('change',), 'mybldr', build['buildset'], build, self.master, None, [])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'mybldr',
            'results': None,
            'builds': builds,
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_no_result_default_subject(self):
        subject = 'result: %(result)s builder: %(builder)s title: %(title)s'
        message = {
            "body": "body",
            "type": "text"
        }

        g, builds = yield self.setup_generator(results=None, subject=subject,
                                               message=message, mode=("change",))
        report = yield self.build_message(g, builds, results=None)

        build = builds[0]
        g.formatter.format_message_for_build.assert_called_with(
            ('change',), 'mybldr', build['buildset'], build, self.master, None, [])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'result: not finished builder: mybldr title: Buildbot',
            'type': 'text',
            'builder_name': 'mybldr',
            'results': None,
            'builds': builds,
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_addLogs(self):
        g, builds = yield self.setup_generator(mode=("change",), add_logs=True)
        report = yield self.build_message(g, builds)

        self.assertEqual(report['logs'][0]['logid'], 60)
        self.assertIn("log with", report['logs'][0]['content']['content'])

    @defer.inlineCallbacks
    def test_build_message_add_patch(self):
        g, builds = yield self.setup_generator(mode=("change",), add_patch=True)
        report = yield self.build_message(g, builds)

        patch_dict = {
            'author': 'him@foo',
            'body': b'hello, world',
            'comment': 'foo',
            'level': 3,
            'patchid': 99,
            'subdir': '/foo'
        }
        self.assertEqual(report['patches'], [patch_dict])

    @defer.inlineCallbacks
    def test_build_message_add_patch_no_patch(self):
        SourceStamp = fakedb.SourceStamp

        class NoPatchSourcestamp(SourceStamp):
            def __init__(self, id, patchid):
                super().__init__(id=id)

        self.patch(fakedb, 'SourceStamp', NoPatchSourcestamp)
        g, builds = yield self.setup_generator(mode=("change",), add_patch=True)
        report = yield self.build_message(g, builds)
        self.assertEqual(report['patches'], [])

    @defer.inlineCallbacks
    def test_generate_finished(self):
        g, builds = yield self.setup_generator()
        report = yield self.generate(g, ('builds', 123, 'finished'), builds[0])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'Builder1',
            'results': SUCCESS,
            'builds': [builds[0]],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_generate_new(self):
        g, builds = yield self.setup_generator(results=None, mode=('failing',), report_new=True)
        report = yield self.generate(g, ('builds', 123, 'new'), builds[0])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'Builder1',
            'results': None,
            'builds': [builds[0]],
            'users': [],
            'patches': [],
            'logs': []
        })
